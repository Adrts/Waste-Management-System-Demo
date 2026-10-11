"""数据汇总报表：设施出入库汇总 + 车辆工作量汇总，支持 日/月/年 粒度与 CSV 导出。

口径：
- 设施出入库：暂存台账按 设施×类别×周期 聚合 ΣIN / ΣOUT（建筑垃圾按 m³ 单位列出）；
- 车辆工作量：流转单按 车辆×周期 聚合 趟次 / 总载重 / 平均装载率（重载装载率口径）。
"""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..db import connect
from ..util import page_params

router = APIRouter(prefix="/api/reports", tags=["reports"])

GRAN_LEN = {"day": 10, "month": 7, "year": 4}
GRAN_NAME = {"day": "日", "month": "月", "year": "年"}


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _gran(granularity: str) -> int:
    if granularity not in GRAN_LEN:
        raise HTTPException(400, "granularity 仅支持 day / month / year")
    return GRAN_LEN[granularity]


# ---------------- 设施出入库汇总 ----------------

STORAGE_SQL = """
SELECT {period} AS period, s.facility_id, f.facility_name, f.facility_type,
       s.category_code, c.category_name, s.unit,
       ROUND(SUM(CASE WHEN s.io_type='IN'  THEN s.quantity ELSE 0 END), 2) AS in_qty,
       ROUND(SUM(CASE WHEN s.io_type='OUT' THEN s.quantity ELSE 0 END), 2) AS out_qty,
       COUNT(*) AS entries,
       COUNT(*) OVER() AS total
FROM txn_storage s
JOIN dim_facility f ON f.facility_id = s.facility_id
JOIN dict_waste_category c ON c.category_code = s.category_code
WHERE 1=1 {cond}
GROUP BY period, s.facility_id, s.category_code, s.unit
ORDER BY period DESC, s.facility_id, s.category_code, s.unit"""


def _storage_query(granularity, facility, category, start, end):
    n = _gran(granularity)
    period = f"substr(s.io_time, 1, {n})"
    cond, args = "", []
    if facility:
        cond += " AND s.facility_id = ?"
        args.append(facility)
    if category:
        cond += " AND s.category_code = ?"
        args.append(category)
    if start:
        cond += " AND s.io_time >= ?"
        args.append(start)
    if end:
        cond += " AND s.io_time < date(?, '+1 day')"
        args.append(end)
    sql = STORAGE_SQL.format(period=period, cond=cond)
    return sql, args


@router.get("/storage")
def storage_report(granularity: str = "month", facility: str = "", category: str = "",
                   start: str = "", end: str = "", page: int = 1, size: int = 20,
                   db=Depends(get_db)):
    sql, args = _storage_query(granularity, facility, category, start, end)
    _, _, off = page_params(page, size)
    rows = [dict(r) for r in db.execute(f"{sql} LIMIT ? OFFSET ?", args + [min(size, 200), off])]
    return {"code": 0, "data": {"total": rows[0]["total"] if rows else 0, "items": rows}}


# ---------------- 车辆工作量汇总 ----------------

VEHICLE_SQL = """
SELECT {period} AS period, t.vehicle_id, v.plate_no, v.vehicle_type,
       v.allowed_category AS category_code, c.category_name,
       v.enrollment_type, v.owner_org,
       COUNT(*) AS trips,
       ROUND(SUM(t.weight_kg), 2) AS total_kg,
       ROUND(SUM(v.load_ton) * 1000, 2) AS capacity_kg,
       ROUND(SUM(t.weight_kg) / (SUM(v.load_ton) * 1000), 4) AS load_rate,
       SUM(t.emergency_flag) AS emergency_trips,
       COUNT(*) OVER() AS total
FROM txn_transfer t
JOIN dim_vehicle v ON v.vehicle_id = t.vehicle_id
JOIN dict_waste_category c ON c.category_code = v.allowed_category
WHERE 1=1 {cond}
GROUP BY period, t.vehicle_id
ORDER BY period DESC, total_kg DESC, t.vehicle_id"""


def _vehicle_query(granularity, vehicle, category, enrollment, emergency, start, end):
    n = _gran(granularity)
    period = f"substr(t.loaded_time, 1, {n})"
    cond, args = "", []
    if vehicle:
        cond += " AND t.vehicle_id = ?"
        args.append(vehicle)
    if category:
        cond += " AND v.allowed_category = ?"
        args.append(category)
    if enrollment:
        cond += " AND v.enrollment_type = ?"
        args.append(enrollment)
    if emergency is not None and emergency >= 0:
        cond += " AND t.emergency_flag = ?"
        args.append(emergency)
    if start:
        cond += " AND t.loaded_time >= ?"
        args.append(start)
    if end:
        cond += " AND t.loaded_time < date(?, '+1 day')"
        args.append(end)
    sql = VEHICLE_SQL.format(period=period, cond=cond)
    return sql, args


@router.get("/vehicle")
def vehicle_report(granularity: str = "month", vehicle: str = "", category: str = "",
                   enrollment: str = "", emergency: int | None = None,
                   start: str = "", end: str = "", page: int = 1, size: int = 20,
                   db=Depends(get_db)):
    sql, args = _vehicle_query(granularity, vehicle, category, enrollment, emergency, start, end)
    _, _, off = page_params(page, size)
    rows = [dict(r) for r in db.execute(f"{sql} LIMIT ? OFFSET ?", args + [min(size, 200), off])]
    return {"code": 0, "data": {"total": rows[0]["total"] if rows else 0, "items": rows}}


# ---------------- CSV 导出 ----------------

STORAGE_HEADERS = ["周期", "粒度", "设施编码", "设施名称", "设施类型", "类别编码", "类别名称",
                   "单位", "入库量", "出库量", "流水条数"]
VEHICLE_HEADERS = ["周期", "粒度", "车辆编号", "车牌", "车型", "专类编码", "专类名称",
                   "编制", "所属单位", "趟次", "总载重(kg)", "核定运能(kg)", "装载率", "应急趟次"]

FAC_TYPES = {"SOURCE": "产生源", "DROP": "投放点", "COLLECT": "收集点",
             "TRANSFER": "转运站", "STORAGE": "暂存点", "TERMINAL": "末端设施"}
VEH_TYPES = {"OTHER_TRUCK": "其他垃圾车", "KITCHEN_TRUCK": "厨余车", "HAZARD_TRUCK": "有害车",
             "BULK_TRUCK": "大件车", "TRANSFER_TRUCK": "大型转运车",
             "RECY_TRUCK": "可回收物回收车", "CONSTR_TRUCK": "建筑垃圾车"}


@router.get("/export")
def export(type: str = "storage", granularity: str = "month", facility: str = "",
           vehicle: str = "", category: str = "", enrollment: str = "",
           emergency: int | None = None, start: str = "", end: str = "",
           db=Depends(get_db)):
    if type not in ("storage", "vehicle"):
        raise HTTPException(400, "type 仅支持 storage / vehicle")
    gran = granularity if granularity in GRAN_NAME else "month"
    buf = io.StringIO()
    writer = csv.writer(buf)
    if type == "storage":
        sql, args = _storage_query(gran, facility, category, start, end)
        writer.writerow(STORAGE_HEADERS)
        for r in db.execute(sql, args):
            writer.writerow([r["period"], GRAN_NAME[gran], r["facility_id"], r["facility_name"],
                             FAC_TYPES.get(r["facility_type"], r["facility_type"]),
                             r["category_code"], r["category_name"], r["unit"],
                             r["in_qty"], r["out_qty"], r["entries"]])
        fname = f"设施出入库汇总_{gran}_{date.today().isoformat()}.csv"
    else:
        sql, args = _vehicle_query(gran, vehicle, category, enrollment, emergency, start, end)
        writer.writerow(VEHICLE_HEADERS)
        for r in db.execute(sql, args):
            writer.writerow([r["period"], GRAN_NAME[gran], r["vehicle_id"], r["plate_no"],
                             VEH_TYPES.get(r["vehicle_type"], r["vehicle_type"]),
                             r["category_code"], r["category_name"],
                             "借调" if r["enrollment_type"] == "TEMP" else "常规",
                             r["owner_org"], r["trips"], r["total_kg"], r["capacity_kg"],
                             f"{r['load_rate'] * 100:.1f}%", r["emergency_trips"]])
        fname = f"车辆工作量汇总_{gran}_{date.today().isoformat()}.csv"
    # UTF-8 BOM（encode("utf-8-sig") 自带 BOM）：Excel 直接打开中文不乱码
    content = buf.getvalue()
    from urllib.parse import quote
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f"attachment; filename=report_{type}_{gran}.csv; "
                 f"filename*=UTF-8''{quote(fname)}"})
