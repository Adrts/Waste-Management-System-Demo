"""主数据 CRUD：类别字典 / 设施 / 车辆（含借调管理）。"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..db import connect
from ..util import page_params, ref_count

router = APIRouter(prefix="/api", tags=["master"])


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


# ---------------- 垃圾类别字典 ----------------

@router.get("/categories")
def list_categories(keyword: str = "", db=Depends(get_db)):
    sql = ("SELECT c.*, "
           "(SELECT COUNT(*) FROM txn_transfer t WHERE t.category_code=c.category_code) AS transfer_count "
           "FROM dict_waste_category c WHERE 1=1")
    args = []
    if keyword:
        sql += " AND (c.category_code LIKE ? OR c.category_name LIKE ?)"
        args += [f"%{keyword}%", f"%{keyword}%"]
    rows = [dict(r) for r in db.execute(sql + " ORDER BY c.category_code", args)]
    return {"code": 0, "data": rows}


class CategoryBody(BaseModel):
    category_code: str
    category_name: str
    default_route: str = ""
    is_market_line: bool = False


@router.post("/categories")
def create_category(body: CategoryBody, db=Depends(get_db)):
    if ref_count(db, "dict_waste_category", "category_code", body.category_code):
        raise HTTPException(400, "类别编码已存在（编码不可复用）")
    db.execute("INSERT INTO dict_waste_category VALUES (?,?,?,?)",
               (body.category_code, body.category_name, body.default_route,
                1 if body.is_market_line else 0))
    db.commit()
    return {"code": 0, "message": "已新增"}


@router.put("/categories/{code}")
def update_category(code: str, body: CategoryBody, db=Depends(get_db)):
    row = db.execute("SELECT * FROM dict_waste_category WHERE category_code=?",
                     (code,)).fetchone()
    if not row:
        raise HTTPException(404, "类别不存在")
    if ref_count(db, "txn_transfer", "category_code", code) and body.category_name != row["category_name"]:
        raise HTTPException(400, "该编码已有历史单据，禁止改名（编码一经使用不可改名/复用）")
    if body.category_code != code and ref_count(db, "txn_transfer", "category_code", code):
        raise HTTPException(400, "该编码已有历史单据，禁止改码")
    db.execute("UPDATE dict_waste_category SET category_code=?, category_name=?, "
               "default_route=?, is_market_line=? WHERE category_code=?",
               (body.category_code, body.category_name, body.default_route,
                1 if body.is_market_line else 0, code))
    db.commit()
    return {"code": 0, "message": "已保存"}


@router.delete("/categories/{code}")
def delete_category(code: str, db=Depends(get_db)):
    for table, col in [("txn_transfer", "category_code"),
                       ("txn_storage", "category_code"),
                       ("txn_disposal", "category_code"),
                       ("dim_vehicle", "allowed_category")]:
        if ref_count(db, table, col, code):
            raise HTTPException(400, f"该类别已被 {table} 引用，禁止删除")
    db.execute("DELETE FROM dict_waste_category WHERE category_code=?", (code,))
    db.commit()
    return {"code": 0, "message": "已删除"}


# ---------------- 设施 ----------------

FAC_SQL = ("SELECT f.*, "
           "(SELECT COUNT(*) FROM txn_transfer t WHERE t.from_facility_id=f.facility_id "
           " OR t.to_facility_id=f.facility_id) AS transfer_count "
           "FROM dim_facility f")


@router.get("/facilities")
def list_facilities(type: str = "", region: str = "", status: str = "",
                    keyword: str = "", page: int = 1, size: int = 20, db=Depends(get_db)):
    sql, args = FAC_SQL + " WHERE 1=1", []
    if type:
        sql += " AND f.facility_type=?"
        args.append(type)
    if region:
        sql += " AND f.region_code=?"
        args.append(region)
    if status:
        sql += " AND f.status=?"
        args.append(status)
    if keyword:
        sql += " AND (f.facility_id LIKE ? OR f.facility_name LIKE ?)"
        args += [f"%{keyword}%", f"%{keyword}%"]
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
    _, _, off = page_params(page, size)
    rows = [dict(r) for r in db.execute(sql + " ORDER BY f.facility_id LIMIT ? OFFSET ?",
                                        args + [min(size, 200), off])]
    return {"code": 0, "data": {"total": total, "items": rows}}


class FacilityBody(BaseModel):
    facility_id: str
    facility_name: str
    facility_type: str
    region_code: str = ""
    address: str = ""
    longitude: float
    latitude: float
    capacity_ton_day: float = 0
    operator: str = ""
    type_attrs: str | None = "{}"
    status: str = "RUNNING"


@router.post("/facilities")
def create_facility(body: FacilityBody, db=Depends(get_db)):
    if ref_count(db, "dim_facility", "facility_id", body.facility_id):
        raise HTTPException(400, "设施编码已存在")
    db.execute(
        "INSERT INTO dim_facility (facility_id,facility_name,facility_type,region_code,"
        "address,longitude,latitude,capacity_ton_day,operator,type_attrs,status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (body.facility_id, body.facility_name, body.facility_type, body.region_code,
         body.address, body.longitude, body.latitude, body.capacity_ton_day,
         body.operator, body.type_attrs, body.status))
    db.commit()
    return {"code": 0, "message": "已新增"}


@router.put("/facilities/{fid}")
def update_facility(fid: str, body: FacilityBody, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM dim_facility WHERE facility_id=?", (fid,)).fetchone():
        raise HTTPException(404, "设施不存在")
    db.execute(
        "UPDATE dim_facility SET facility_name=?, facility_type=?, region_code=?, "
        "address=?, longitude=?, latitude=?, capacity_ton_day=?, operator=?, "
        "type_attrs=?, status=? WHERE facility_id=?",
        (body.facility_name, body.facility_type, body.region_code, body.address,
         body.longitude, body.latitude, body.capacity_ton_day, body.operator,
         body.type_attrs, body.status, fid))
    db.commit()
    return {"code": 0, "message": "已保存"}


@router.delete("/facilities/{fid}")
def delete_facility(fid: str, db=Depends(get_db)):
    if ref_count(db, "txn_transfer", "from_facility_id", fid) or \
       ref_count(db, "txn_transfer", "to_facility_id", fid) or \
       ref_count(db, "txn_storage", "facility_id", fid) or \
       ref_count(db, "txn_disposal", "facility_id", fid):
        raise HTTPException(400, "设施已有历史单据，禁止删除；请置为 SHUTDOWN 关停")
    db.execute("DELETE FROM dim_facility WHERE facility_id=?", (fid,))
    db.commit()
    return {"code": 0, "message": "已删除"}


# ---------------- 车辆 ----------------

VEH_SQL = ("SELECT v.*, c.category_name, "
           "(SELECT COUNT(*) FROM txn_transfer t WHERE t.vehicle_id=v.vehicle_id) AS transfer_count "
           "FROM dim_vehicle v JOIN dict_waste_category c ON c.category_code=v.allowed_category")


@router.get("/vehicles")
def list_vehicles(type: str = "", status: str = "", enrollment: str = "",
                  keyword: str = "", page: int = 1, size: int = 20, db=Depends(get_db)):
    sql, args = VEH_SQL + " WHERE 1=1", []
    if type:
        sql += " AND v.vehicle_type=?"
        args.append(type)
    if status:
        sql += " AND v.status=?"
        args.append(status)
    if enrollment:
        sql += " AND v.enrollment_type=?"
        args.append(enrollment)
    if keyword:
        sql += " AND (v.vehicle_id LIKE ? OR v.plate_no LIKE ? OR v.owner_org LIKE ?)"
        args += [f"%{keyword}%"] * 3
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
    _, _, off = page_params(page, size)
    rows = [dict(r) for r in db.execute(sql + " ORDER BY v.vehicle_id LIMIT ? OFFSET ?",
                                        args + [min(size, 200), off])]
    return {"code": 0, "data": {"total": total, "items": rows}}


class VehicleBody(BaseModel):
    vehicle_id: str
    plate_no: str
    vehicle_type: str
    allowed_category: str
    load_ton: float
    owner_org: str = ""
    enrollment_type: str = "REGULAR"
    lender_org: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    status: str = "ACTIVE"


@router.post("/vehicles")
def create_vehicle(body: VehicleBody, db=Depends(get_db)):
    if ref_count(db, "dim_vehicle", "vehicle_id", body.vehicle_id):
        raise HTTPException(400, "车辆编号已存在")
    if ref_count(db, "dim_vehicle", "plate_no", body.plate_no):
        raise HTTPException(400, "车牌号已存在")
    _validate_temp(body)
    db.execute(
        "INSERT INTO dim_vehicle (vehicle_id,plate_no,vehicle_type,allowed_category,"
        "load_ton,owner_org,enrollment_type,lender_org,valid_from,valid_to,status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (body.vehicle_id, body.plate_no, body.vehicle_type, body.allowed_category,
         body.load_ton, body.owner_org, body.enrollment_type, body.lender_org,
         body.valid_from, body.valid_to, body.status))
    db.commit()
    return {"code": 0, "message": "已登记（临时车辆即借即登）" if body.enrollment_type == "TEMP"
            else "已新增"}


def _validate_temp(body: VehicleBody):
    if body.enrollment_type == "TEMP":
        if not (body.lender_org and body.valid_from and body.valid_to):
            raise HTTPException(400, "临时借调车辆必须填写借调单位与借调时间窗")
        if body.valid_from > body.valid_to:
            raise HTTPException(400, "借调时间窗无效：valid_from 晚于 valid_to")
    else:
        body.lender_org = body.valid_from = body.valid_to = None


@router.put("/vehicles/{vid}")
def update_vehicle(vid: str, body: VehicleBody, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM dim_vehicle WHERE vehicle_id=?", (vid,)).fetchone():
        raise HTTPException(404, "车辆不存在")
    if db.execute("SELECT 1 FROM dim_vehicle WHERE plate_no=? AND vehicle_id<>?",
                  (body.plate_no, vid)).fetchone():
        raise HTTPException(400, "车牌号已存在")
    _validate_temp(body)
    db.execute(
        "UPDATE dim_vehicle SET plate_no=?, vehicle_type=?, allowed_category=?, "
        "load_ton=?, owner_org=?, enrollment_type=?, lender_org=?, valid_from=?, "
        "valid_to=?, status=? WHERE vehicle_id=?",
        (body.plate_no, body.vehicle_type, body.allowed_category, body.load_ton,
         body.owner_org, body.enrollment_type, body.lender_org, body.valid_from,
         body.valid_to, body.status, vid))
    db.commit()
    return {"code": 0, "message": "已保存"}


@router.post("/vehicles/{vid}/release")
def release_vehicle(vid: str, db=Depends(get_db)):
    row = db.execute("SELECT * FROM dim_vehicle WHERE vehicle_id=?", (vid,)).fetchone()
    if not row:
        raise HTTPException(404, "车辆不存在")
    if row["enrollment_type"] != "TEMP":
        raise HTTPException(400, "仅临时借调车辆可执行退场")
    db.execute("UPDATE dim_vehicle SET status='RELEASED', valid_to=? WHERE vehicle_id=?",
               (date.today().isoformat(), vid))
    db.commit()
    return {"code": 0, "message": "已退场（置 RELEASED，历史单据仍可追溯）"}


@router.delete("/vehicles/{vid}")
def delete_vehicle(vid: str, db=Depends(get_db)):
    if ref_count(db, "txn_transfer", "vehicle_id", vid):
        raise HTTPException(400, "车辆已有历史单据，禁止删除；临时车请退场（RELEASED），常规车可置 RETIRED")
    db.execute("DELETE FROM dim_vehicle WHERE vehicle_id=?", (vid,))
    db.commit()
    return {"code": 0, "message": "已删除"}
