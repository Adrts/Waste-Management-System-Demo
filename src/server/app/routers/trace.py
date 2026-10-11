"""追溯查询：按流转单号 / 批次号 / 设施 / 类别 / 时间段（F-7）。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import connect

router = APIRouter(prefix="/api/trace", tags=["trace"])

TRANSFER_SQL = """
SELECT t.*, f1.facility_name AS from_name, f2.facility_name AS to_name,
       f1.facility_type AS from_type, f2.facility_type AS to_type,
       v.plate_no, v.vehicle_type, c.category_name
FROM txn_transfer t
JOIN dim_facility f1 ON f1.facility_id=t.from_facility_id
JOIN dim_facility f2 ON f2.facility_id=t.to_facility_id
JOIN dim_vehicle v ON v.vehicle_id=t.vehicle_id
JOIN dict_waste_category c ON c.category_code=t.category_code"""
STORAGE_SQL = """
SELECT s.*, f.facility_name, c.category_name
FROM txn_storage s
JOIN dim_facility f ON f.facility_id=s.facility_id
JOIN dict_waste_category c ON c.category_code=s.category_code"""


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _journey(conn, where, args):
    legs = [dict(r) for r in conn.execute(TRANSFER_SQL + f" WHERE {where} ORDER BY t.loaded_time, t.leg_seq", args)]
    nos = [t["transfer_no"] for t in legs]
    batches = sorted({t["batch_no"] for t in legs if t["batch_no"]})
    storages, disposals = [], []
    if nos:
        ph = ",".join("?" * len(nos))
        storages = [dict(r) for r in conn.execute(
            STORAGE_SQL + f" WHERE s.related_transfer_no IN ({ph}) ORDER BY s.io_time", nos)]
        disposals = [dict(r) for r in conn.execute(
            "SELECT d.*, f.facility_name FROM txn_disposal d "
            "JOIN dim_facility f ON f.facility_id=d.facility_id "
            f"WHERE d.transfer_no IN ({ph}) ORDER BY d.consume_time", nos)]
    for b in batches:                    # 批次口径的暂存/消耗一并纳入（有害全旅程）
        storages += [dict(r) for r in conn.execute(
            STORAGE_SQL + " WHERE s.batch_no=? AND (s.related_transfer_no IS NULL "
            "OR s.related_transfer_no NOT IN (%s)) ORDER BY s.io_time" % ",".join("?" * len(nos)),
            [b] + nos)]
        disposals += [dict(r) for r in conn.execute(
            "SELECT d.*, f.facility_name FROM txn_disposal d "
            "JOIN dim_facility f ON f.facility_id=d.facility_id "
            "WHERE d.batch_no=? AND d.transfer_no NOT IN (%s) ORDER BY d.consume_time"
            % ",".join("?" * len(nos)), [b] + nos)]
    timeline = []
    for t in legs:
        timeline.append({"time": t["loaded_time"], "event": "装运/建单" if t["leg_seq"] == 1 else "续段装运",
                         "facility": t["from_name"], "detail": f"{t['transfer_no']} · {t['category_name']} · "
                         f"{t['weight_kg']}kg · {t['plate_no']}"})
        if t["arrived_time"]:
            timeline.append({"time": t["arrived_time"], "event": "到达",
                             "facility": t["to_name"], "detail": t["transfer_no"]})
    for s in storages:
        timeline.append({"time": s["io_time"], "event": "入库" if s["io_type"] == "IN" else "出库",
                         "facility": s["facility_name"],
                         "detail": f"{s['storage_id']} · {s['category_name']} · {s['quantity']}{s['unit']}"
                                   f"{' · 批次 ' + s['batch_no'] if s['batch_no'] else ''}"
                                   f"{' · ' + s['reason'] if s['reason'] != 'NORMAL' else ''}"})
    for d in disposals:
        timeline.append({"time": d["consume_time"], "event": "拒收退回" if d["reject_reason"] else "末端消耗",
                         "facility": d["facility_name"],
                         "detail": f"{d['disposal_id']} · {d['weight_kg']}kg"
                                   f"{' · 拒收:' + d['reject_reason'] if d['reject_reason'] else ''}"})
    timeline.sort(key=lambda x: x["time"] or "")
    return {"legs": legs, "storages": storages, "disposals": disposals, "timeline": timeline}


@router.get("")
def trace(transfer_no: str = "", batch_no: str = "",
          facility_id: str = "", category_code: str = "",
          start: str = "", end: str = "", db=Depends(get_db)):
    if transfer_no:
        row = db.execute("SELECT 1 FROM txn_transfer WHERE transfer_no=?",
                         (transfer_no,)).fetchone()
        if not row:
            raise HTTPException(404, "流转单不存在")
        data = _journey(db, "t.transfer_no=?", [transfer_no])
        data["mode"] = "transfer"
        return {"code": 0, "data": data}
    if batch_no:
        data = _journey(db, "t.batch_no=?", [batch_no])
        if not data["legs"]:
            raise HTTPException(404, "批次不存在或无流转单据")
        data["mode"] = "batch"
        return {"code": 0, "data": data}
    if any([facility_id, category_code, start, end]):
        sql, args = TRANSFER_SQL + " WHERE 1=1", []
        if facility_id:
            sql += " AND (t.from_facility_id=? OR t.to_facility_id=? OR f1.facility_name LIKE ? OR f2.facility_name LIKE ?)"
            args += [facility_id] * 2 + [f"%{facility_id}%", f"%{facility_id}%"]
        if category_code:
            sql += " AND t.category_code=?"
            args.append(category_code)
        if start:
            sql += " AND t.loaded_time>=?"
            args.append(start)
        if end:
            sql += " AND t.loaded_time<date(?,'+1 day')"
            args.append(end)
        rows = [dict(r) for r in db.execute(
            sql + " ORDER BY t.loaded_time DESC LIMIT 200", args)]
        return {"code": 0, "data": {"mode": "list", "legs": rows}}
    raise HTTPException(400, "请提供 transfer_no / batch_no 或 设施/类别/时间段条件")
