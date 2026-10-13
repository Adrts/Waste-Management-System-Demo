"""流转单：列表 / 建单四道校验 / 状态机（在途→到达→签收）/ 拒收回退 / 异常登记。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import connect
from ..util import page_params
from . import stats as _stats

router = APIRouter(prefix="/api/transfers", tags=["transfers"])

BATCHABLE = {"HAZARD", "BULK"}     # 可批次化品类
SELECT = """
SELECT t.*, f1.facility_name AS from_name, f2.facility_name AS to_name,
       f1.facility_type AS from_type, f2.facility_type AS to_type,
       f2.status AS to_status, v.plate_no, v.vehicle_type, v.load_ton,
       v.enrollment_type, c.category_name, d.disposal_id, d.reject_reason
FROM txn_transfer t
JOIN dim_facility f1 ON f1.facility_id=t.from_facility_id
JOIN dim_facility f2 ON f2.facility_id=t.to_facility_id
JOIN dim_vehicle v ON v.vehicle_id=t.vehicle_id
JOIN dict_waste_category c ON c.category_code=t.category_code
LEFT JOIN txn_disposal d ON d.transfer_no=t.transfer_no"""


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _get(conn, no):
    row = conn.execute(SELECT + " WHERE t.transfer_no=?", (no,)).fetchone()
    return dict(row) if row else None


@router.get("")
def list_transfers(no: str = "", batch: str = "", category: str = "",
                   facility: str = "", status: str = "", emergency: int | None = None,
                   start: str = "", end: str = "", page: int = 1, size: int = 20,
                   db=Depends(get_db)):
    sql, args = SELECT + " WHERE 1=1", []
    if no:
        sql += " AND t.transfer_no LIKE ?"
        args.append(f"%{no}%")
    if batch:
        sql += " AND t.batch_no LIKE ?"
        args.append(f"%{batch}%")
    if category:
        sql += " AND t.category_code=?"
        args.append(category)
    if facility:
        sql += " AND (t.from_facility_id=? OR t.to_facility_id=? OR f1.facility_name LIKE ? OR f2.facility_name LIKE ?)"
        args += [facility, facility, f"%{facility}%", f"%{facility}%"]
    if status:
        sql += " AND t.status=?"
        args.append(status)
    if emergency is not None and emergency >= 0:
        sql += " AND t.emergency_flag=?"
        args.append(emergency)
    if start:
        sql += " AND t.loaded_time >= ?"
        args.append(start)
    if end:
        sql += " AND t.loaded_time < date(?, '+1 day')"
        args.append(end)
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
    _, _, off = page_params(page, size)
    rows = [dict(r) for r in db.execute(
        sql + " ORDER BY t.loaded_time DESC, t.transfer_no DESC LIMIT ? OFFSET ?",
        args + [min(size, 200), off])]
    return {"code": 0, "data": {"total": total, "items": rows}}


@router.get("/{no}")
def get_transfer(no: str, db=Depends(get_db)):
    row = _get(db, no)
    if not row:
        raise HTTPException(404, "流转单不存在")
    return {"code": 0, "data": row}


class TransferBody(BaseModel):
    category_code: str
    vehicle_id: str
    from_facility_id: str
    to_facility_id: str
    weight_kg: float
    batch_no: str | None = None
    leg_seq: int = 1
    reclass_from: str | None = None
    loaded_time: str | None = None
    emergency_flag: bool = False


def validate_order(conn, b: TransferBody, loaded: str):
    """建单四道校验（F-2 专车专类 / F-4 批次 / F-5 借调时间窗 / F-8 关停设施）。"""
    cat = conn.execute("SELECT * FROM dict_waste_category WHERE category_code=?",
                       (b.category_code,)).fetchone()
    if not cat:
        raise HTTPException(400, f"类别 {b.category_code} 不存在")
    veh = conn.execute("SELECT * FROM dim_vehicle WHERE vehicle_id=?",
                       (b.vehicle_id,)).fetchone()
    if not veh:
        raise HTTPException(400, f"车辆 {b.vehicle_id} 不存在")
    if veh["status"] != "ACTIVE":
        raise HTTPException(400, f"车辆状态为 {veh['status']}，不可派单")
    if b.weight_kg <= 0:
        raise HTTPException(400, "装运重量必须大于 0")
    # F-8 关停设施
    for fid, tag in [(b.to_facility_id, "终点"), (b.from_facility_id, "起点")]:
        fac = conn.execute("SELECT facility_id,facility_name,status FROM dim_facility WHERE facility_id=?",
                           (fid,)).fetchone()
        if not fac:
            raise HTTPException(400, f"{tag}设施 {fid} 不存在")
        if fac["status"] == "SHUTDOWN":
            raise HTTPException(400, f"{tag}设施[{fac['facility_name']}]已关停，禁止新建流转单（F-8）")
    # F-2 专车专类
    if veh["allowed_category"] != b.category_code:
        cn = conn.execute("SELECT category_name FROM dict_waste_category WHERE category_code=?",
                          (veh["allowed_category"],)).fetchone()[0]
        raise HTTPException(400, f"专车专类校验失败：车辆[{veh['plate_no']}]仅允许运输 {veh['allowed_category']}({cn})，"
                                 f"本单类别为 {b.category_code}({cat['category_name']})，拒单（F-2）")
    # F-5 借调时间窗
    if veh["enrollment_type"] == "TEMP":
        if not (veh["valid_from"] <= loaded[:10] <= veh["valid_to"]):
            raise HTTPException(400, f"借调车辆[{veh['plate_no']}]时间窗 {veh['valid_from']}~{veh['valid_to']} "
                                     f"不覆盖装运日期 {loaded[:10]}，派单被拒（F-5）")
    # F-4 批次规则
    if b.category_code == "HAZARD" and not (b.batch_no or "").strip():
        raise HTTPException(400, "有害垃圾建单必须填写批次号（F-4）")
    if b.leg_seq > 1 and b.batch_no:
        if b.category_code not in BATCHABLE:
            raise HTTPException(400, "跨中转混装续段不允许填写批次号（F-4：散装品类靠设施节点+重量勾稽衔接）")
        if not conn.execute("SELECT 1 FROM txn_transfer WHERE batch_no=?",
                            (b.batch_no,)).fetchone():
            raise HTTPException(400, f"批次 {b.batch_no} 不存在：续段必须挂接已有批次")
    if b.reclass_from and not conn.execute(
            "SELECT 1 FROM dict_waste_category WHERE category_code=?", (b.reclass_from,)).fetchone():
        raise HTTPException(400, f"改道原类别 {b.reclass_from} 不存在")


@router.post("")
def create_transfer(body: TransferBody, db=Depends(get_db)):
    loaded = body.loaded_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    validate_order(db, body, loaded)
    day = loaded[:10].replace("-", "")
    seq = db.execute(
        "SELECT COUNT(*) FROM txn_transfer WHERE transfer_no LIKE ?",
        (f"HK-{day}-{body.category_code}-%",)).fetchone()[0]
    no = f"HK-{day}-{body.category_code}-{seq + 1:04d}"
    while db.execute("SELECT 1 FROM txn_transfer WHERE transfer_no=?", (no,)).fetchone():
        seq += 1
        no = f"HK-{day}-{body.category_code}-{seq + 1:04d}"
    carrier = db.execute("SELECT owner_org FROM dim_vehicle WHERE vehicle_id=?",
                         (body.vehicle_id,)).fetchone()[0]
    db.execute(
        "INSERT INTO txn_transfer (transfer_no,batch_no,leg_seq,category_code,reclass_from,"
        "weight_kg,from_facility_id,to_facility_id,vehicle_id,carrier_org,status,"
        "loaded_time,arrived_time,emergency_flag) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (no, body.batch_no or None, body.leg_seq, body.category_code,
         body.reclass_from or None, body.weight_kg, body.from_facility_id,
         body.to_facility_id, body.vehicle_id, carrier, "LOADED", loaded, None,
         1 if body.emergency_flag else 0))
    db.commit()
    _stats.invalidate_alerts_cache()
    return {"code": 0, "message": f"建单成功：{no}", "data": {"transfer_no": no}}


class ArriveBody(BaseModel):
    arrived_time: str | None = None


@router.post("/{no}/arrive")
def arrive(no: str, body: ArriveBody | None = None, db=Depends(get_db)):
    t = _get(db, no)
    if not t:
        raise HTTPException(404, "流转单不存在")
    if t["status"] != "LOADED":
        raise HTTPException(400, f"状态机校验失败：当前 {t['status']}，仅 LOADED 可登记到达")
    arrived = (body and body.arrived_time) or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("UPDATE txn_transfer SET status='ARRIVED', arrived_time=? WHERE transfer_no=?",
               (arrived, no))
    db.commit()
    return {"code": 0, "message": "已登记到达（过夜稽核时钟启动）"}


class ConfirmBody(BaseModel):
    weight_kg: float
    disposal_method: str
    consume_time: str | None = None


METHOD_BY_ROUTE = {
    "INCINERATION": ["OTHER", "WATER", "GARDEN"],
    "ANAEROBIC": ["KN_HOME", "KN_CANTEEN", "FECAL"],
    "COMPOST": ["GARDEN"],
    "DISASSEMBLE": ["BULK"],
    "RECYCLE": ["RECY", "CONSTR"],
    "HAZARD_TREAT": ["HAZARD"],
}


@router.post("/{no}/confirm")
def confirm(no: str, body: ConfirmBody, db=Depends(get_db)):
    t = _get(db, no)
    if not t:
        raise HTTPException(404, "流转单不存在")
    if t["status"] == "CONFIRMED":
        raise HTTPException(400, "该单已签收，请勿重复操作")
    if t["status"] != "ARRIVED":
        raise HTTPException(400, f"状态机校验失败：当前 {t['status']}，须先登记到达（LOADED→ARRIVED→CONFIRMED）")
    to_fac = db.execute("SELECT * FROM dim_facility WHERE facility_id=?",
                        (t["to_facility_id"],)).fetchone()
    if body.weight_kg <= 0:
        raise HTTPException(400, "实收重量必须大于 0")
    if body.disposal_method not in METHOD_BY_ROUTE:
        raise HTTPException(400, "消耗方式不合法")
    if t["category_code"] not in METHOD_BY_ROUTE[body.disposal_method]:
        raise HTTPException(400, f"类别 {t['category_code']} 不适用消耗方式 "
                                 f"{body.disposal_method}（该方式适用：{', '.join(METHOD_BY_ROUTE[body.disposal_method])}）")
    warnings = []
    if abs(body.weight_kg - t["weight_kg"]) / t["weight_kg"] > 0.03:
        warnings.append(f"终段实收与流转单重量偏差 {abs(body.weight_kg - t['weight_kg']) / t['weight_kg']:.1%}，"
                        f"超过 3% 容差，已自动计入勾稽异常")
    consume = body.consume_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = db.execute("SELECT * FROM txn_disposal WHERE transfer_no=?", (no,)).fetchone()
    if existing:                     # 拒收回退后的再次签收：更新原消耗行
        db.execute(
            "UPDATE txn_disposal SET facility_id=?, batch_no=?, category_code=?, weight_kg=?, "
            "disposal_method=?, consume_time=?, reject_reason=NULL WHERE disposal_id=?",
            (t["to_facility_id"], t["batch_no"], t["category_code"], body.weight_kg,
             body.disposal_method, consume, existing["disposal_id"]))
        did = existing["disposal_id"]
    else:
        did = _next_disposal_id(db, consume)
        db.execute(
            "INSERT INTO txn_disposal (disposal_id,facility_id,transfer_no,batch_no,"
            "category_code,weight_kg,disposal_method,consume_time,reject_reason) "
            "VALUES (?,?,?,?,?,?,?,?,NULL)",
            (did, t["to_facility_id"], no, t["batch_no"], t["category_code"],
             body.weight_kg, body.disposal_method, consume))
    db.execute("UPDATE txn_transfer SET status='CONFIRMED' WHERE transfer_no=?", (no,))
    db.commit()
    _stats.invalidate_alerts_cache()
    return {"code": 0, "message": f"签收完成，消耗记录 {did} 已生成（全生命周期闭环）",
            "data": {"disposal_id": did, "warnings": warnings}}


class RejectBody(BaseModel):
    reason: str


def _next_disposal_id(db, when: str) -> str:
    day = when[:10].replace("-", "")
    seq = db.execute("SELECT COUNT(*) FROM txn_disposal WHERE disposal_id LIKE ?",
                     (f"DSP-{day}-%",)).fetchone()[0]
    did = f"DSP-{day}-{seq + 1:04d}"
    while db.execute("SELECT 1 FROM txn_disposal WHERE disposal_id=?", (did,)).fetchone():
        seq += 1
        did = f"DSP-{day}-{seq + 1:04d}"
    return did


@router.post("/{no}/reject")
def reject(no: str, body: RejectBody, db=Depends(get_db)):
    t = _get(db, no)
    if not t:
        raise HTTPException(404, "流转单不存在")
    if t["status"] == "CONFIRMED":
        raise HTTPException(400, "已签收单据不可拒收")
    if not body.reason.strip():
        raise HTTPException(400, "必须填写拒收原因")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = db.execute("SELECT * FROM txn_disposal WHERE transfer_no=?", (no,)).fetchone()
    if existing:
        db.execute("UPDATE txn_disposal SET weight_kg=0, disposal_method=NULL, "
                   "consume_time=?, reject_reason=? WHERE disposal_id=?",
                   (now, body.reason, existing["disposal_id"]))
    else:
        did = _next_disposal_id(db, now)
        db.execute(
            "INSERT INTO txn_disposal (disposal_id,facility_id,transfer_no,batch_no,"
            "category_code,weight_kg,disposal_method,consume_time,reject_reason) "
            "VALUES (?,?,?,?,?,?,NULL,?,?)",
            (did, t["to_facility_id"], no, t["batch_no"], t["category_code"], 0,
             now, body.reason))
    db.execute("UPDATE txn_transfer SET status='LOADED' WHERE transfer_no=?", (no,))
    db.commit()
    _stats.invalidate_alerts_cache()
    return {"code": 0, "message": "已拒收：状态回退为 LOADED，拒收原因已登记"}


class PatchBody(BaseModel):
    weight_kg: float | None = None
    batch_no: str | None = None
    reclass_from: str | None = None
    emergency_flag: bool | None = None


@router.patch("/{no}")
def patch_transfer(no: str, body: PatchBody, db=Depends(get_db)):
    t = _get(db, no)
    if not t:
        raise HTTPException(404, "流转单不存在")
    if t["status"] != "LOADED":
        raise HTTPException(400, "仅 LOADED 状态可修改")
    sets, args = [], []
    if body.weight_kg is not None:
        if body.weight_kg <= 0:
            raise HTTPException(400, "重量必须大于 0")
        sets.append("weight_kg=?")
        args.append(body.weight_kg)
    if body.batch_no is not None:
        sets.append("batch_no=?")
        args.append(body.batch_no or None)
    if body.reclass_from is not None:
        sets.append("reclass_from=?")
        args.append(body.reclass_from or None)
    if body.emergency_flag is not None:
        sets.append("emergency_flag=?")
        args.append(1 if body.emergency_flag else 0)
    if not sets:
        raise HTTPException(400, "无可修改字段")
    if body.batch_no is not None or body.reclass_from is not None:
        nb = TransferBody(category_code=t["category_code"], vehicle_id=t["vehicle_id"],
                          from_facility_id=t["from_facility_id"],
                          to_facility_id=t["to_facility_id"],
                          weight_kg=body.weight_kg or t["weight_kg"],
                          batch_no=body.batch_no if body.batch_no is not None else t["batch_no"],
                          leg_seq=t["leg_seq"],
                          reclass_from=body.reclass_from if body.reclass_from is not None else t["reclass_from"])
        validate_order(db, nb, t["loaded_time"])
    args.append(no)
    db.execute(f"UPDATE txn_transfer SET {', '.join(sets)} WHERE transfer_no=?", args)
    db.commit()
    return {"code": 0, "message": "已修改"}


@router.delete("/{no}")
def delete_transfer(no: str, db=Depends(get_db)):
    t = _get(db, no)
    if not t:
        raise HTTPException(404, "流转单不存在")
    if t["status"] != "LOADED":
        raise HTTPException(400, "仅 LOADED 状态可作废（改用拒收/正常流转）")
    if db.execute("SELECT 1 FROM txn_storage WHERE related_transfer_no=?", (no,)).fetchone():
        raise HTTPException(400, "该单已关联暂存流水，不可作废")
    db.execute("DELETE FROM txn_disposal WHERE transfer_no=?", (no,))   # 仅可能是拒收行
    db.execute("DELETE FROM txn_transfer WHERE transfer_no=?", (no,))
    db.commit()
    _stats.invalidate_alerts_cache()
    return {"code": 0, "message": "已作废"}
