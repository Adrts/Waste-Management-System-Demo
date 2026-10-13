"""统计聚合（展板数据源）与预警中心。口径与数据库派生视图一致。"""
import json
import os
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends

from ..db import connect

router = APIRouter(prefix="/api/stats", tags=["stats"])

META_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "meta.json")
HUBS = ("TR-001", "TR-002", "TR-003")


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _meta():
    try:
        with open(META_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"events": {"cny": [], "typhoons": []}}


def _day(d: str | None) -> str:
    return d or date.today().isoformat()


@router.get("/kpi")
def kpi(day: str = "", db=Depends(get_db)):
    day = _day(day)
    q = db.execute
    collected = q("SELECT COALESCE(SUM(weight_kg),0) FROM txn_transfer "
                  "WHERE leg_seq=1 AND substr(loaded_time,1,10)=?", (day,)).fetchone()[0]
    disposal = q("SELECT COALESCE(SUM(weight_kg),0) FROM txn_disposal "
                 "WHERE reject_reason IS NULL AND substr(consume_time,1,10)=?", (day,)).fetchone()[0]
    in_transit = q("SELECT COUNT(*) FROM txn_transfer WHERE status='LOADED' "
                   "AND substr(loaded_time,1,10) >= date('now','-1 day')").fetchone()[0]
    emergency = q("SELECT COALESCE(SUM(weight_kg),0) FROM txn_transfer "
                  "WHERE emergency_flag=1 AND substr(loaded_time,1,10)=?", (day,)).fetchone()[0]
    # 无害化处置率（累计口径）：非拒收消耗 / 已签收(终段 CONFIRMED)流转单重量
    d_sum, t_sum = q("SELECT COALESCE(SUM(d.weight_kg),0), "
                     "COALESCE((SELECT SUM(t.weight_kg) FROM txn_transfer t "
                     "JOIN dim_facility f ON f.facility_id=t.to_facility_id "
                     "WHERE f.facility_type='TERMINAL' AND t.status='CONFIRMED'),0) "
                     "FROM txn_disposal d WHERE d.reject_reason IS NULL").fetchone()
    haz_rate = round(d_sum / t_sum * 100, 2) if t_sum else 100.0
    util = q("SELECT COALESCE(SUM(loaded_kg)/SUM(capacity_kg),0) FROM v_vehicle_utilization "
             "WHERE stat_date=?", (day,)).fetchone()[0]
    alerts = len(alerts_data(db))
    yest = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    prev = q("SELECT COALESCE(SUM(weight_kg),0) FROM txn_transfer "
             "WHERE leg_seq=1 AND substr(loaded_time,1,10)=?", (yest,)).fetchone()[0]
    return {"code": 0, "data": {
        "day": day, "collected_kg": round(collected), "disposal_kg": round(disposal),
        "in_transit": in_transit, "emergency_kg": round(emergency),
        "hazard_free_rate": haz_rate, "vehicle_utilization": round(util, 4),
        "alert_count": alerts, "collected_prev_day": round(prev),
        "trips": q("SELECT COUNT(*) FROM txn_transfer WHERE leg_seq=1 AND substr(loaded_time,1,10)=?",
                   (day,)).fetchone()[0],
    }}


@router.get("/category")
def category(start: str = "", end: str = "", region: str = "", db=Depends(get_db)):
    start, end = _day(start), _day(end)
    sql = ("SELECT t.category_code, c.category_name, SUM(t.weight_kg) AS kg, COUNT(*) AS legs "
           "FROM txn_transfer t JOIN dict_waste_category c ON c.category_code=t.category_code "
           "JOIN dim_facility f ON f.facility_id=t.from_facility_id "
           "WHERE t.leg_seq=1 AND substr(t.loaded_time,1,10) BETWEEN ? AND ?")
    args = [start, end]
    if region:
        sql += " AND f.region_code=?"
        args.append(region)
    rows = [dict(r) for r in db.execute(
        sql + " GROUP BY t.category_code ORDER BY kg DESC", args)]
    return {"code": 0, "data": rows}


@router.get("/trend")
def trend(start: str = "", end: str = "", category: str = "", db=Depends(get_db)):
    end = end or date.today().isoformat()
    start = start or (date.fromisoformat(end) - timedelta(days=90)).isoformat()
    cat_cond = " AND t.category_code=?" if category else ""
    args = [start, end] + ([category] if category else [])
    gen = db.execute(
        f"SELECT substr(t.loaded_time,1,10) d, SUM(t.weight_kg) kg, COUNT(*) trips "
        f"FROM txn_transfer t WHERE t.leg_seq=1 AND substr(t.loaded_time,1,10) BETWEEN ? AND ?{cat_cond} "
        f"GROUP BY d", args).fetchall()
    dsp_args = [start, end] + ([category] if category else [])
    dsp = db.execute(
        f"SELECT substr(d.consume_time,1,10) d, SUM(d.weight_kg) kg FROM txn_disposal d "
        f"WHERE d.reject_reason IS NULL AND substr(d.consume_time,1,10) BETWEEN ? AND ?{cat_cond} "
        f"GROUP BY d", dsp_args).fetchall()
    dsp_map = {r[0]: r[1] for r in dsp}
    days = [{"date": r[0], "generated_kg": round(r[1]), "trips": r[2],
             "disposal_kg": round(dsp_map.get(r[0], 0))} for r in gen]
    m = _meta()
    events = [{"type": "cny", "name": e["name"], "date": e["date"]} for e in m["events"]["cny"]]
    events += [{"type": "typhoon", "name": e["name"], "date": e["landfall"],
                "window": [e["window_start"], e["window_end"]]} for e in m["events"]["typhoons"]]
    return {"code": 0, "data": {"days": days, "events": events, "prediction": []}}


@router.get("/facilities")
def facilities(days: int = 7, db=Depends(get_db)):
    end = date.today()
    start = end - timedelta(days=max(1, min(days, 90)))
    rows = db.execute(
        """SELECT f.facility_id, f.facility_name, f.facility_type, f.capacity_ton_day,
                  f.longitude, f.latitude, f.region_code, f.status,
                  COALESCE(SUM(t.weight_kg),0) AS received_kg
           FROM dim_facility f
           LEFT JOIN txn_transfer t ON t.to_facility_id=f.facility_id
                AND substr(t.loaded_time,1,10) BETWEEN ? AND ?
           WHERE f.facility_type IN ('TRANSFER','TERMINAL') AND f.status='RUNNING'
           GROUP BY f.facility_id ORDER BY received_kg DESC""", (start.isoformat(), end.isoformat())).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        cap = (r["capacity_ton_day"] or 0) * max(1, min(days, 90))
        d["load_rate"] = round(d["received_kg"] / 1000 / cap, 4) if cap else 0
        out.append(d)
    return {"code": 0, "data": out}


@router.get("/sankey")
def sankey(start: str = "", end: str = "", category: str = "", db=Depends(get_db)):
    end = end or date.today().isoformat()
    start = start or (date.fromisoformat(end) - timedelta(days=30)).isoformat()
    cond = " AND t.category_code=?" if category else ""
    args = [start, end] + ([category] if category else [])
    # 产生段：leg1 → 中转/末端
    src = db.execute(
        f"""SELECT t.to_facility_id, f.facility_name, f.facility_type, SUM(t.weight_kg) kg
            FROM txn_transfer t JOIN dim_facility f ON f.facility_id=t.to_facility_id
            WHERE t.leg_seq=1 AND substr(t.loaded_time,1,10) BETWEEN ? AND ?{cond}
            GROUP BY t.to_facility_id""", args).fetchall()
    # 中转段：枢纽/小站 → 末端
    mid = db.execute(
        f"""SELECT t.from_facility_id, f1.facility_name, t.to_facility_id, f2.facility_name,
                   SUM(t.weight_kg) kg
            FROM txn_transfer t JOIN dim_facility f1 ON f1.facility_id=t.from_facility_id
            JOIN dim_facility f2 ON f2.facility_id=t.to_facility_id
            WHERE substr(t.loaded_time,1,10) BETWEEN ? AND ?{cond}
              AND f1.facility_type='TRANSFER' AND f2.facility_type='TERMINAL'
            GROUP BY t.from_facility_id, t.to_facility_id""", args).fetchall()
    nodes, links = [{"name": "全市产生"}], []
    for r in src:
        kg = round(r["kg"])
        if r["facility_type"] == "TRANSFER":
            nodes.append({"name": r["facility_name"]})
            links.append({"source": "全市产生", "target": r["facility_name"], "value": kg})
        else:
            links.append({"source": "全市产生", "target": r["facility_name"], "value": kg})
    for r in mid:
        links.append({"source": r[1], "target": r[3], "value": round(r["kg"])})
    names = {n["name"] for n in nodes} | {l["target"] for l in links} | {l["source"] for l in links}
    nodes = [{"name": n} for n in sorted(names)]
    return {"code": 0, "data": {"nodes": nodes, "links": links, "range": [start, end]}}


@router.get("/utilization")
def utilization(start: str = "", end: str = "", db=Depends(get_db)):
    end = end or date.today().isoformat()
    start = start or (date.fromisoformat(end) - timedelta(days=7)).isoformat()
    rows = db.execute(
        """SELECT v.category_code, c.category_name, v.enrollment_type,
                  SUM(v.trips) AS trips, SUM(v.loaded_kg) AS loaded_kg, SUM(v.capacity_kg) AS capacity_kg,
                  ROUND(SUM(v.loaded_kg)/SUM(v.capacity_kg),4) AS utilization
           FROM v_vehicle_utilization v
           JOIN dict_waste_category c ON c.category_code=v.category_code
           WHERE v.stat_date BETWEEN ? AND ?
           GROUP BY v.category_code, c.category_name, v.enrollment_type ORDER BY loaded_kg DESC""",
        (start, end)).fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


@router.get("/stock")
def stock(db=Depends(get_db)):
    rows = db.execute(
        """SELECT s.facility_id, f.facility_name, f.facility_type, s.category_code,
                  c.category_name, s.batch_no, s.unit, SUM(CASE WHEN s.io_type='IN'
                  THEN s.quantity ELSE -s.quantity END) AS stock, MAX(s.io_time) AS last_io
           FROM txn_storage s JOIN dim_facility f ON f.facility_id=s.facility_id
           JOIN dict_waste_category c ON c.category_code=s.category_code
           GROUP BY s.facility_id, s.category_code, s.batch_no, s.unit
           HAVING stock > 0 ORDER BY stock DESC LIMIT 100""").fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


# ================= 预警中心 =================

_alerts_cache = {"ts": 0.0, "data": None}

import time as _time


def alerts_data(db) -> list[dict]:
    """60s 进程内缓存：展板轮询不重复全表扫描。"""
    if _alerts_cache["data"] is not None and _time.time() - _alerts_cache["ts"] < 60:
        return _alerts_cache["data"]
    data = _compute_alerts(db)
    _alerts_cache["ts"] = _time.time()
    _alerts_cache["data"] = data
    return data


def invalidate_alerts_cache():
    """写操作（建单/签收/拒收/出入库等）后调用，保证预警即时性。"""
    _alerts_cache["ts"] = 0.0


def _compute_alerts(db) -> list[dict]:
    alerts = []
    # 1. 有害垃圾批次超期滞留 >365 天
    for r in db.execute(
            """SELECT s.facility_id, f.facility_name, s.batch_no,
                      MIN(s.io_time) AS in_time,
                      SUM(CASE WHEN s.io_type='IN' THEN s.quantity ELSE -s.quantity END) AS stock
               FROM txn_storage s JOIN dim_facility f ON f.facility_id=s.facility_id
               WHERE s.category_code='HAZARD' AND s.batch_no IS NOT NULL
               GROUP BY s.facility_id, s.batch_no HAVING stock > 0
                        AND MIN(s.io_time) < datetime('now', '-365 days')"""):
        days = (datetime.now() - datetime.fromisoformat(r["in_time"])).days
        alerts.append({"type": "hazard_overdue", "level": "high",
                       "title": f"有害批次超期滞留 {days} 天（>365 天）",
                       "detail": f"{r['facility_name']} · 批次 {r['batch_no']} · 在库 {r['stock']} 吨",
                       "refs": {"batch_no": r["batch_no"], "facility_id": r["facility_id"]},
                       "time": r["in_time"]})
    # 2. 焚烧厂贮坑工艺滞留 >7 天
    for r in db.execute(
            """SELECT s.facility_id, f.facility_name, s.related_transfer_no,
                      MIN(s.io_time) AS in_time, SUM(s.quantity) AS stock
               FROM txn_storage s JOIN dim_facility f ON f.facility_id=s.facility_id
               WHERE s.reason='PROCESS' AND s.io_type='IN' AND s.related_transfer_no IS NOT NULL
               GROUP BY s.facility_id, s.related_transfer_no
               HAVING s.related_transfer_no NOT IN
                      (SELECT related_transfer_no FROM txn_storage
                       WHERE io_type='OUT' AND reason='PROCESS'
                         AND related_transfer_no IS NOT NULL)
                 AND MIN(s.io_time) < datetime('now', '-7 days') LIMIT 50"""):
        days = (datetime.now() - datetime.fromisoformat(r["in_time"])).days
        alerts.append({"type": "pit_overdue", "level": "medium",
                       "title": f"贮坑工艺滞留 {days} 天（>7 天）",
                       "detail": f"{r['facility_name']} · {r['stock']} 吨 · 单号 {r['related_transfer_no']}",
                       "refs": {"transfer_no": r["related_transfer_no"], "facility_id": r["facility_id"]},
                       "time": r["in_time"]})
    # 3. 勾稽异常（终段实收与流转单差 > 3%）
    for r in db.execute(
            """SELECT d.disposal_id, d.transfer_no, d.weight_kg, t.weight_kg AS tw,
                      t.batch_no, f.facility_name, d.consume_time
               FROM txn_disposal d JOIN txn_transfer t ON t.transfer_no=d.transfer_no
               JOIN dim_facility f ON f.facility_id=d.facility_id
               WHERE d.reject_reason IS NULL AND t.weight_kg > 0
                 AND ABS(d.weight_kg - t.weight_kg)/t.weight_kg > 0.03"""):
        diff = (r["weight_kg"] - r["tw"]) / r["tw"]
        alerts.append({"type": "reconciliation", "level": "high",
                       "title": f"勾稽异常：终段实收偏差 {diff:+.1%}（容差 3%）",
                       "detail": f"{r['facility_name']} · {r['transfer_no']} · 流转 {r['tw']:.0f}kg / 实收 {r['weight_kg']:.0f}kg",
                       "refs": {"transfer_no": r["transfer_no"], "disposal_id": r["disposal_id"]},
                       "time": r["consume_time"]})
    # 4. 超载（weight_kg > load_ton×1000）
    for r in db.execute(
            """SELECT t.transfer_no, t.weight_kg, v.load_ton, v.plate_no, t.loaded_time
               FROM txn_transfer t JOIN dim_vehicle v ON v.vehicle_id=t.vehicle_id
               WHERE t.weight_kg > v.load_ton * 1000 ORDER BY t.loaded_time DESC LIMIT 50"""):
        alerts.append({"type": "overload", "level": "medium",
                       "title": f"超载告警：装载率 {r['weight_kg']/(r['load_ton']*1000):.0%}",
                       "detail": f"{r['plate_no']} · {r['transfer_no']} · 载重 {r['weight_kg']:.0f}kg / 核载 {r['load_ton']:.0f}t",
                       "refs": {"transfer_no": r["transfer_no"]}, "time": r["loaded_time"]})
    # 5. 中转站"过夜"（枢纽出站车辆清晨才发车）
    for r in db.execute(
            """SELECT t.transfer_no, t.loaded_time, f.facility_name, t.arrived_time
               FROM txn_transfer t JOIN dim_facility f ON f.facility_id=t.from_facility_id
               WHERE f.facility_type='TRANSFER' AND CAST(strftime('%H', t.loaded_time) AS INT) < 8
                 AND t.loaded_time < date('now')
               ORDER BY t.loaded_time DESC LIMIT 50"""):
        alerts.append({"type": "overnight", "level": "medium",
                       "title": "中转过夜告警：次日清晨方才离站",
                       "detail": f"{r['facility_name']} · {r['transfer_no']} · {r['loaded_time']} 发车",
                       "refs": {"transfer_no": r["transfer_no"]}, "time": r["loaded_time"]})
    # 6. 枢纽当日进出失衡（出站显著小于进站，疑似滞留）
    for r in db.execute(
            """WITH inh AS (
                 SELECT to_facility_id AS fid, substr(arrived_time,1,10) AS d,
                        SUM(weight_kg) AS kin
                 FROM txn_transfer
                 WHERE to_facility_id IN ('TR-001','TR-002','TR-003')
                   AND arrived_time IS NOT NULL AND arrived_time < date('now')
                 GROUP BY 1, 2),
               outh AS (
                 SELECT from_facility_id AS fid, substr(loaded_time,1,10) AS d,
                        SUM(weight_kg) AS kout
                 FROM txn_transfer
                 WHERE from_facility_id IN ('TR-001','TR-002','TR-003')
                 GROUP BY 1, 2)
               SELECT f.facility_name, f.facility_id, inh.d AS d, kin,
                      COALESCE(kout, 0) AS kout
               FROM inh
               JOIN dim_facility f ON f.facility_id = inh.fid
               LEFT JOIN outh ON outh.fid = inh.fid AND outh.d = inh.d
               WHERE COALESCE(kout, 0) < kin * 0.95
               ORDER BY inh.d DESC LIMIT 30"""):
        alerts.append({"type": "station_balance", "level": "medium",
                       "title": "枢纽进出失衡：出站量显著低于进站量",
                       "detail": f"{r['facility_name']} · {r['d']} · 进 {r['kin']/1000:.1f}t / 出 {r['kout']/1000:.1f}t",
                       "refs": {"facility_id": r["facility_id"], "date": r["d"]},
                       "time": r["d"]})
    return alerts


@router.get("/alerts")
def alerts(db=Depends(get_db)):
    data = alerts_data(db)
    order = {"high": 0, "medium": 1, "low": 2}
    data.sort(key=lambda a: (order.get(a["level"], 3), a["time"] or ""), reverse=False)
    return {"code": 0, "data": data}
