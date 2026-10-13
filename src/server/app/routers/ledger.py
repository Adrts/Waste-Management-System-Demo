"""暂存台账（出入库登记）与消耗记录。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import connect
from ..util import page_params, parse_json

router = APIRouter(prefix="/api", tags=["ledger"])

STORAGE_SQL = """
SELECT s.*, f.facility_name, f.facility_type, c.category_name
FROM txn_storage s
JOIN dim_facility f ON f.facility_id=s.facility_id
JOIN dict_waste_category c ON c.category_code=s.category_code"""


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/storage")
def list_storage(facility: str = "", category: str = "", io_type: str = "",
                 batch: str = "", reason: str = "", start: str = "", end: str = "",
                 page: int = 1, size: int = 20, db=Depends(get_db)):
    sql, args = STORAGE_SQL + " WHERE 1=1", []
    if facility:
        sql += " AND (s.facility_id=? OR f.facility_name LIKE ?)"
        args += [facility, f"%{facility}%"]
    if category:
        sql += " AND s.category_code=?"
        args.append(category)
    if io_type:
        sql += " AND s.io_type=?"
        args.append(io_type)
    if batch:
        sql += " AND s.batch_no LIKE ?"
        args.append(f"%{batch}%")
    if reason:
        sql += " AND s.reason=?"
        args.append(reason)
    if start:
        sql += " AND s.io_time >= ?"
        args.append(start)
    if end:
        sql += " AND s.io_time < date(?, '+1 day')"
        args.append(end)
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
    _, _, off = page_params(page, size)
    rows = [dict(r) for r in db.execute(
        sql + " ORDER BY s.io_time DESC, s.storage_id DESC LIMIT ? OFFSET ?",
        args + [min(size, 200), off])]
    return {"code": 0, "data": {"total": total, "items": rows}}


@router.get("/storage/stock")
def stock(facility: str = "", category: str = "", db=Depends(get_db)):
    sql = ("SELECT s.facility_id, f.facility_name, s.category_code, c.category_name, "
           "s.batch_no, s.unit, SUM(CASE WHEN s.io_type='IN' THEN s.quantity "
           "ELSE -s.quantity END) AS stock, MAX(s.io_time) AS last_io_time "
           "FROM txn_storage s JOIN dim_facility f ON f.facility_id=s.facility_id "
           "JOIN dict_waste_category c ON c.category_code=s.category_code WHERE 1=1")
    args = []
    if facility:
        sql += " AND s.facility_id=?"
        args.append(facility)
    if category:
        sql += " AND s.category_code=?"
        args.append(category)
    rows = [dict(r) for r in db.execute(
        sql + " GROUP BY s.facility_id, s.category_code, s.batch_no, s.unit "
              "HAVING stock > 0 ORDER BY s.facility_id, s.category_code", args)]
    return {"code": 0, "data": rows}


class StorageBody(BaseModel):
    facility_id: str
    category_code: str
    io_type: str
    quantity: float
    unit: str = "吨"
    batch_no: str | None = None
    reason: str = "NORMAL"
    related_transfer_no: str | None = None
    io_time: str | None = None


@router.post("/storage")
def create_storage(body: StorageBody, db=Depends(get_db)):
    fac = db.execute("SELECT * FROM dim_facility WHERE facility_id=?",
                     (body.facility_id,)).fetchone()
    if not fac:
        raise HTTPException(400, "设施不存在")
    if fac["facility_type"] not in ("TRANSFER", "STORAGE", "TERMINAL"):
        raise HTTPException(400, "暂存台账仅支持 转运站/暂存点/末端设施")
    if body.io_type not in ("IN", "OUT"):
        raise HTTPException(400, "io_type 必须为 IN/OUT")
    if body.quantity <= 0:
        raise HTTPException(400, "数量必须大于 0")
    if body.reason not in ("NORMAL", "PROCESS", "EMERGENCY"):
        raise HTTPException(400, "reason 必须为 NORMAL/PROCESS/EMERGENCY")
    # 限收品类（type_attrs.limit_categories）
    attrs = parse_json(fac["type_attrs"]) or {}
    limit = attrs.get("限收品类") or attrs.get("limit_categories")
    if limit and body.category_code not in limit:
        raise HTTPException(400, f"设施[{fac['facility_name']}]限收品类 {limit}，拒收 {body.category_code}")
    if body.category_code == "HAZARD" and not (body.batch_no or "").strip():
        raise HTTPException(400, "有害垃圾出入库必须填写批次号")
    if body.related_transfer_no and not db.execute(
            "SELECT 1 FROM txn_transfer WHERE transfer_no=?",
            (body.related_transfer_no,)).fetchone():
        raise HTTPException(400, "关联流转单不存在")
    io_time = body.io_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if body.io_type == "OUT":        # 出库后库存不可为负（按批次或设施+类别口径）
        cond, args = "facility_id=? AND category_code=?", [body.facility_id, body.category_code]
        if body.batch_no:
            cond += " AND batch_no=?"
            args.append(body.batch_no)
        stock = db.execute(
            f"SELECT COALESCE(SUM(CASE WHEN io_type='IN' THEN quantity ELSE -quantity END),0) "
            f"FROM txn_storage WHERE {cond}", args).fetchone()[0]
        if stock < body.quantity:
            raise HTTPException(400, f"出库后库存为负（当前库存 {stock:.2f} {body.unit}），请核对数量")
    sid = db.execute("SELECT COUNT(*) FROM txn_storage WHERE storage_id LIKE ?",
                     (f"STO-{io_time[:10].replace('-', '')}-%",)).fetchone()[0]
    sid = f"STO-{io_time[:10].replace('-', '')}-{sid + 1:04d}"
    while db.execute("SELECT 1 FROM txn_storage WHERE storage_id=?", (sid,)).fetchone():
        n = int(sid[-4:])
        sid = f"STO-{io_time[:10].replace('-', '')}-{n + 1:04d}"
    db.execute(
        "INSERT INTO txn_storage (storage_id,facility_id,category_code,io_type,quantity,"
        "unit,io_time,batch_no,reason,related_transfer_no) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, body.facility_id, body.category_code, body.io_type, body.quantity,
         body.unit, io_time, body.batch_no or None, body.reason,
         body.related_transfer_no or None))
    db.commit()
    from . import stats as _stats
    _stats.invalidate_alerts_cache()
    return {"code": 0, "message": f"已登记 {'入库' if body.io_type == 'IN' else '出库'}：{sid}",
            "data": {"storage_id": sid}}


DISPOSAL_SQL = """
SELECT d.*, f.facility_name, c.category_name, t.batch_no AS t_batch,
       t.weight_kg AS transfer_weight, t.to_facility_id
FROM txn_disposal d
JOIN dim_facility f ON f.facility_id=d.facility_id
JOIN dict_waste_category c ON c.category_code=d.category_code
JOIN txn_transfer t ON t.transfer_no=d.transfer_no"""


@router.get("/disposal")
def list_disposal(facility: str = "", category: str = "", method: str = "",
                  start: str = "", end: str = "", keyword: str = "",
                  page: int = 1, size: int = 20, db=Depends(get_db)):
    sql, args = DISPOSAL_SQL + " WHERE 1=1", []
    if facility:
        sql += " AND (d.facility_id=? OR f.facility_name LIKE ?)"
        args += [facility, f"%{facility}%"]
    if category:
        sql += " AND d.category_code=?"
        args.append(category)
    if method:
        sql += " AND d.disposal_method=?"
        args.append(method)
    if start:
        sql += " AND d.consume_time >= ?"
        args.append(start)
    if end:
        sql += " AND d.consume_time < date(?, '+1 day')"
        args.append(end)
    if keyword:
        sql += " AND (d.disposal_id LIKE ? OR d.transfer_no LIKE ? OR d.batch_no LIKE ?)"
        args += [f"%{keyword}%"] * 3
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
    _, _, off = page_params(page, size)
    rows = [dict(r) for r in db.execute(
        sql + " ORDER BY d.consume_time DESC, d.disposal_id DESC LIMIT ? OFFSET ?",
        args + [min(size, 200), off])]
    return {"code": 0, "data": {"total": total, "items": rows}}


class DisposalBody(BaseModel):
    weight_kg: float | None = None
    disposal_method: str | None = None
    consume_time: str | None = None


@router.put("/disposal/{did}")
def update_disposal(did: str, body: DisposalBody, db=Depends(get_db)):
    row = db.execute("SELECT * FROM txn_disposal WHERE disposal_id=?", (did,)).fetchone()
    if not row:
        raise HTTPException(404, "消耗记录不存在")
    sets, args = [], []
    for col, val in [("weight_kg", body.weight_kg), ("disposal_method", body.disposal_method),
                     ("consume_time", body.consume_time)]:
        if val is not None:
            sets.append(f"{col}=?")
            args.append(val)
    if not sets:
        raise HTTPException(400, "无可修改字段")
    args.append(did)
    db.execute(f"UPDATE txn_disposal SET {', '.join(sets)} WHERE disposal_id=?", args)
    db.commit()
    return {"code": 0, "message": "已保存"}


@router.delete("/disposal/{did}")
def delete_disposal(did: str, db=Depends(get_db)):
    row = db.execute("SELECT * FROM txn_disposal WHERE disposal_id=?", (did,)).fetchone()
    if not row:
        raise HTTPException(404, "消耗记录不存在")
    if row["reject_reason"]:
        raise HTTPException(400, "拒收记录不可删除（随流转单作废）")
    db.execute("DELETE FROM txn_disposal WHERE disposal_id=?", (did,))
    db.execute("UPDATE txn_transfer SET status='ARRIVED' WHERE transfer_no=? AND status='CONFIRMED'",
               (row["transfer_no"],))
    db.commit()
    from . import stats as _stats
    _stats.invalidate_alerts_cache()
    return {"code": 0, "message": "已撤销消耗记录，关联流转单回退为 ARRIVED"}
