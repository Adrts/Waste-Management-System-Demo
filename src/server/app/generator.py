"""缩比模拟数据生成器。

对应《DEMO项目目标与验收》D-2~D-8：
- 时间跨度：2024-07-01 至今（>730 天，覆盖 2025/2026 两个春节 + 台风季）
- 流转单 ≥10 万行、日均 ≥300 车次
- 全路径覆盖：直运/汇运(含农村三段)/有害批次/贮坑工艺暂存/厨余餐厨/可回收市场线/
  大件拆解残渣续段/建筑调配场/园林/粪渣/水域/改道/应急
- 规律注入：春节前 7 天厨余/其他 +30%；台风临近 72h +50%；周末 +10%
- 异常注入：勾稽异常、超载、中转过夜、有害超期批次、贮坑滞留、拒收回退、改道
- 随机种子固定可复现；注入清单写入 data/meta.json（规律清单交付物）
"""
import json
import os
import random
from collections import defaultdict
from datetime import date, datetime, timedelta

import db as _db
import seed as _seed

R = random.Random(42)
TODAY = date.today()
START = date(2024, 7, 1)

CNY = {2025: date(2025, 1, 29), 2026: date(2026, 2, 17)}
TYPHOONS = [
    {"name": "台风“摩羯”", "landfall": date(2024, 9, 5)},
    {"name": "台风“蝴蝶”", "landfall": date(2025, 6, 14)},
    {"name": "台风“杨柳”", "landfall": date(2026, 8, 13)},
]
OVERNIGHT_DATES = {date(2024, 10, 14), date(2025, 11, 6)}   # 中转站过夜样本
REJECT_EVERY, OVERLOAD_EVERY, RECON_EVERY = 10000, 26000, 18000  # 注入抽样间隔
BASE = {  # 吨/日（缩比，真实约 3500 吨/日）
    "OTHER": 400, "KN_HOME": 65, "KN_CANTEEN": 58, "HAZARD": 1.3, "RECY": 12,
    "BULK": 12, "CONSTR": 25, "GARDEN": 8, "FECAL": 6, "WATER": 3,
}
REGION_W = {"460105": 0.24, "460106": 0.27, "460107": 0.23, "460108": 0.26}
HUB_OF = {
    "460105": [("TR-001", 0.8), ("TR-003", 0.2)],
    "460106": [("TR-001", 1.0)],
    "460107": [("TR-002", 0.6), ("TR-001", 0.4)],
    "460108": [("TR-002", 1.0)],
}
SMALL_OUT = {"TR-101": "TR-001", "TR-102": "TR-001", "TR-201": "TR-001",
             "TR-301": "TR-002", "TR-302": "TR-002", "TR-401": "TR-002"}
HAZ_POINT = {"460105": "ST-HZ01", "460106": "ST-HZ02", "460107": "ST-HZ03",
             "460108": "ST-HZ04"}
RECY_WH = {"460105": "ST-RC01", "460106": "ST-RC01", "460107": "ST-RC02",
           "460108": "ST-RC02"}
CZ_YARD = {"SOURCE-GD01": "ST-CZ04", "SOURCE-GD02": "ST-CZ01",
           "SOURCE-GD03": "ST-CZ03", "SOURCE-GD04": "ST-CZ01",
           "SOURCE-GD05": "ST-CZ04"}

# ---------------- 输出缓冲与计数 ----------------
trf, stg, dsp = [], [], []
_no_seq = defaultdict(int)
_sto_seq = defaultdict(int)
_dsp_seq = defaultdict(int)
_haz_seq = [0]
_pit_seq = [0]
_trf_idx = [0]
_dsp_idx = [0]
_veh_rr = defaultdict(int)

VEH_BY_CAT = defaultdict(list)
DROP_BY_REGION = defaultdict(list)
HAZ_BUFFER = defaultdict(list)
RECY_BUFFER = defaultdict(list)
CZ_BUFFER = defaultdict(list)
REJECT_SET = set()

injected = {"reconciliation": [], "overload": [], "overnight": [], "long_hazard": [],
            "long_pit": [], "rejects": [], "reclass": []}


def at(d, hh, mm=0):
    return datetime(d.year, d.month, d.day, hh, mm)


def S(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def pick_weighted(pairs):
    x = R.random()
    for item, p in pairs:
        x -= p
        if x <= 0:
            return item
    return pairs[-1][0]


def day_factor(cat, d):
    f = 1.0
    if d.month in (11, 12, 1, 2):
        f *= 1.06                                             # 旅游旺季
    f *= 1 + 0.03 * (d.year - 2024)                           # 年增长
    if d.weekday() >= 5 and cat in ("OTHER", "KN_HOME", "RECY"):
        f *= 1.10                                             # 周末小高峰 +10%
    for cny in CNY.values():
        if cny - timedelta(days=7) <= d < cny and cat in ("OTHER", "KN_HOME"):
            f *= 1.30                                         # 春节前 7 天 +30%
    for ev in TYPHOONS:
        lf = ev["landfall"]
        if lf - timedelta(days=3) <= d <= lf:
            f *= 1.50                                         # 台风临近 72h +50%
        elif lf < d <= lf + timedelta(days=3):
            f *= 1.60 if cat == "OTHER" else (3.0 if cat == "GARDEN" else 1.1)
    return f * R.lognormvariate(0, 0.10)


def in_typhoon(d):
    return any(ev["landfall"] - timedelta(days=3) <= d <= ev["landfall"] + timedelta(days=3)
               for ev in TYPHOONS)


def next_no(d, cat):
    _no_seq[(d, cat)] += 1
    return f"HK-{d:%Y%m%d}-{cat}-{_no_seq[(d, cat)]:04d}"


def next_sto(d):
    _sto_seq[d] += 1
    return f"STO-{d:%Y%m%d}-{_sto_seq[d]:04d}"


def next_dsp(d):
    _dsp_seq[d] += 1
    return f"DSP-{d:%Y%m%d}-{_dsp_seq[d]:04d}"


def pick_vehicle(tag, d):
    key = POOL_KEY.get(tag, tag)
    pool = VEH_BY_CAT.get(key) or []
    usable = [v for v in pool
              if (v["enrollment_type"] == "REGULAR" and v["status"] == "ACTIVE")
              or (v["enrollment_type"] == "TEMP"
                  and v["valid_from"] <= d.isoformat() <= v["valid_to"])]
    if not usable:
        usable = [v for v in pool if v["status"] == "ACTIVE"] or pool
    _veh_rr[key] += 7
    return usable[_veh_rr[key] % len(usable)]


def _status_for(loaded, arrived):
    """按时间判定状态；返回 None 表示该单不应生成（未来时段）。"""
    today0 = datetime.combine(TODAY, datetime.min.time())
    now = datetime.now().replace(microsecond=0)
    if loaded >= today0 + timedelta(days=1):
        return None
    if loaded < today0 - timedelta(days=1):
        return "CONFIRMED"
    if loaded < today0:                                        # 昨天
        return "ARRIVED" if loaded.hour >= 18 else "CONFIRMED"
    # 今天：早 8 点前到达 → 已签收；已到达 → 待签收；未到达 → 在途
    if arrived and arrived <= now and arrived.hour < 8:
        return "CONFIRMED"
    if arrived and arrived <= now:
        return "ARRIVED"
    if loaded <= now:
        return "LOADED"
    return None


def add_leg(d, cat, frm, to, veh, weight, loaded, arrived, *,
            batch=None, leg_seq=1, reclass_from=None, emergency=False):
    """建流转单。返回 (transfer_no, status, weight_kg)；no 为 None 表示未生成。"""
    _trf_idx[0] += 1
    no = next_no(d, cat)
    reject = (_trf_idx[0] % REJECT_EVERY == 0
              and cat in ("OTHER", "KN_HOME", "KN_CANTEEN")
              and leg_seq == 1 and batch is None
              and to.startswith("TM-") and to not in ("TM-LF01", "TM-WC01"))
    status = "LOADED" if reject else _status_for(loaded, arrived)
    if status is None:
        return None, None, None
    w = weight
    if _trf_idx[0] % OVERLOAD_EVERY == 0 and not reject:
        w = veh["load_ton"] * 1000 * R.uniform(1.02, 1.08)    # 超载样本（千克）
    trf.append((no, batch, leg_seq, cat, reclass_from, round(w, 2), frm, to,
                veh["vehicle_id"], veh["owner_org"], status, S(loaded),
                S(arrived) if arrived else None, 1 if emergency else 0))
    if reject:
        REJECT_SET.add(no)
        injected["rejects"].append({"transfer_no": no, "date": d.isoformat()})
    elif _trf_idx[0] % OVERLOAD_EVERY == 0:
        injected["overload"].append({"transfer_no": no, "weight_kg": round(w, 2),
                                     "load_ton": veh["load_ton"], "date": d.isoformat()})
    return no, status, w


def add_disposal(d, fac, no, cat, weight, method, outputs, consume,
                 batch=None, reject=None):
    """消耗记录；非拒收行按抽样注入勾稽异常（实收重量 -28%）。"""
    _dsp_idx[0] += 1
    anomalous = reject is None and _dsp_idx[0] % RECON_EVERY == 0
    if anomalous:
        weight *= 0.72
    did = next_dsp(consume.date())
    dsp.append((did, fac, no, batch, cat, round(weight, 2), method,
                json.dumps(outputs, ensure_ascii=False) if outputs else None,
                S(consume), reject))
    if anomalous:
        injected["reconciliation"].append(
            {"transfer_no": no, "disposal_id": did, "date": d.isoformat()})


def add_pit(d, fac, no, cat, weight, arrived):
    """焚烧厂贮坑工艺暂存：IN 即入，OUT 滞 2-6 天（前 2 单滞 8-10 天作超期样本）。"""
    _pit_seq[0] += 1
    if _pit_seq[0] <= 2:
        lag = timedelta(days=R.randint(8, 10))                 # 贮坑滞留样本
        injected["long_pit"].append({"facility": fac, "in_time": S(arrived),
                                     "days": lag.days})
    else:
        lag = timedelta(days=R.randint(2, 6))
    if arrived + lag > datetime.combine(TODAY, datetime.min.time()):
        lag = timedelta(hours=2)
    out_t = arrived + lag
    consume = out_t + timedelta(minutes=R.randint(30, 180))
    stg.append((next_sto(out_t.date()), fac, cat, "IN", round(weight / 1000, 3),
                "吨", S(arrived), None, "PROCESS", no))
    stg.append((next_sto(out_t.date()), fac, cat, "OUT", round(weight / 1000, 3),
                "吨", S(out_t), None, "PROCESS", no))
    return consume


def w_jitter(w, lo=0.96, hi=1.04):
    return w * R.uniform(lo, hi)


# ---------------- 各类别日流 ----------------

def gen_other(d, tonnage):
    """其他垃圾：城区汇运(2 段) + 直运 + 农村三段线，经白水塘/江东进焚烧厂。"""
    hub_in = defaultdict(float)
    urban, direct, rural = 0.62, 0.30, 0.08
    all_drops = sum(DROP_BY_REGION.values(), [])
    for region, rw in REGION_W.items():
        w_ton = tonnage * urban * rw                            # 吨
        n = max(1, round(w_ton * 1000 / 2400))                  # 车次
        hub = pick_weighted(HUB_OF[region])
        for _ in range(n):
            wt = w_jitter(w_ton * 1000 / n)                     # 千克
            veh = pick_vehicle("OTHER_TRUCK", d)
            t0 = at(d, R.randint(6, 10), R.choice((0, 15, 30, 45)))
            t1 = t0 + timedelta(minutes=R.randint(40, 100))
            no, st, wkg = add_leg(d, "OTHER", R.choice(DROP_BY_REGION[region]), hub, veh,
                                  wt, t0, t1, emergency=in_typhoon(d) and R.random() < 0.5)
            if no and st:
                hub_in[hub] += wkg
    # 直运
    dw = tonnage * direct
    n = max(1, round(dw * 1000 / 2300))
    for i in range(n):
        wt = w_jitter(dw * 1000 / n)
        veh = pick_vehicle("OTHER_TRUCK", d)
        t0 = at(d, R.randint(6, 11), R.choice((0, 20, 40)))
        t1 = t0 + timedelta(minutes=R.randint(70, 130))
        no, st, wkg = add_leg(d, "OTHER", R.choice(all_drops), "TM-INC01", veh, wt, t0, t1,
                              emergency=in_typhoon(d) and R.random() < 0.5)
        if no and (st == "CONFIRMED" or no in REJECT_SET):
            _finish_incin(d, no, None, "OTHER", wkg, t1)
    # 农村三段：收集点 → 小型站 → 枢纽 → 焚烧厂（按 6.5t/趟上限拆分车次，台风放量不超载）
    rw_ton = tonnage * rural
    cls = [("CL-30101", "TR-301"), ("CL-30102", "TR-302"), ("CL-30103", "TR-301"),
           ("CL-40101", "TR-401"), ("CL-40102", "TR-401"), ("CL-40103", "TR-401")]
    n_legs = max(6, int(rw_ton * 1000 / 6500) + 1)
    for i in range(n_legs):
        cl, small = cls[i % 6]
        wt = w_jitter(rw_ton * 1000 / n_legs)
        veh = pick_vehicle("OTHER_TRUCK", d)
        t0 = at(d, R.randint(7, 11), R.choice((0, 30)))
        t1 = t0 + timedelta(minutes=R.randint(50, 110))
        no, st, wkg = add_leg(d, "OTHER", cl, small, veh, wt, t0, t1,
                              emergency=in_typhoon(d) and R.random() < 0.5)
        if no and st:
            hub_in[SMALL_OUT[small]] += wkg
            if st in ("ARRIVED", "CONFIRMED"):
                stg.append((next_sto(d), small, "OTHER", "IN", round(wkg / 1000, 3),
                            "吨", S(t1), None, "NORMAL", no))
                stg.append((next_sto(d), small, "OTHER", "OUT", round(wkg / 1000, 3),
                            "吨", S(t1 + timedelta(hours=1)), None, "NORMAL", no))
    # 枢纽出站（当日压箱转运；过夜样本顺延次日清晨）
    for hub in ("TR-001", "TR-002", "TR-003"):
        total = hub_in.get(hub, 0.0)
        if total <= 0:
            continue
        if d in OVERNIGHT_DATES and hub == "TR-001":
            injected["overnight"].append({"date": d.isoformat(), "facility": hub})
            _hub_out(d, hub, max(0.0, total - 21000))          # 当日正常出站
            _hub_out(d + timedelta(days=1), hub, min(total, 21000), next_morning=True)
        else:
            _hub_out(d, hub, total)


def _hub_out(d, hub, total, next_morning=False):
    n = max(1, round(total / 21000))                 # total 为千克
    for i in range(n):
        wt = total / n * R.uniform(0.995, 1.005)
        veh = pick_vehicle("TRANSFER_TRUCK", d)
        t0 = at(d, 6 if next_morning else R.randint(13, 20), R.choice((0, 30)))
        t1 = t0 + timedelta(minutes=R.randint(70, 120))
        no, st, wkg = add_leg(d, "OTHER", hub, "TM-INC01", veh, wt, t0, t1,
                              emergency=in_typhoon(d) and R.random() < 0.4)
        if no and (st == "CONFIRMED" or no in REJECT_SET):
            _finish_incin(d, no, None, "OTHER", wkg, t1)


def _finish_incin(d, no, batch, cat, wt, arrived):
    """终到焚烧厂：35% 走贮坑工艺暂存后消耗。"""
    if no in REJECT_SET:
        add_disposal(d, "TM-INC01", no, cat, 0, None, None, arrived,
                     batch=batch, reject="分类不合格，含杂质超标，拒收退回")
        return
    if R.random() < 0.35:
        consume = add_pit(d, "TM-INC01", no, cat, wt, arrived)
    else:
        consume = arrived + timedelta(minutes=R.randint(30, 120))
    add_disposal(consume.date(), "TM-INC01", no, cat, wt, "INCINERATION",
                 {"电力_kwh": round(wt * 0.44), "炉渣砖_t": round(wt * 0.02, 2),
                  "飞灰固化_t": round(wt * 0.003, 3)}, consume, batch=batch)


def gen_kitchen(d, cat, tonnage, terminal):
    n = max(1, round(tonnage * 1000 / 1700))
    canteen_srcs = [f"SOURCE-CY0{k}" for k in range(1, 9)]
    home_srcs = (DROP_BY_REGION["460107"] + DROP_BY_REGION["460108"] +
                 ["SOURCE-SC01", "SOURCE-SC02", "SOURCE-SC03"])
    for _ in range(n):
        wt = w_jitter(tonnage * 1000 / n)
        veh = pick_vehicle("KITCHEN_TRUCK", d)
        frm = R.choice(canteen_srcs if cat == "KN_CANTEEN" else home_srcs)
        t0 = at(d, R.randint(7, 12), R.choice((0, 15, 30, 45)))
        t1 = t0 + timedelta(minutes=R.randint(60, 140))
        no, st, w = add_leg(d, cat, frm, terminal, veh, wt, t0, t1)
        if not no:
            continue
        if no in REJECT_SET:
            add_disposal(d, terminal, no, cat, 0, None, None, t1,
                         reject="厨余杂质率超 20%，拒收退回")
            continue
        if st != "CONFIRMED":
            continue
        consume = t1 + timedelta(minutes=R.randint(40, 150))
        outputs = ({"沼气_m3": round(w * 68), "生物柴油_t": round(w * 0.03, 3),
                    "有机肥_t": round(w * 0.15, 2)} if cat == "KN_CANTEEN"
                   else {"沼气_m3": round(w * 62), "有机肥_t": round(w * 0.18, 2)})
        add_disposal(consume.date(), terminal, no, cat, w, "ANAEROBIC", outputs,
                     consume)


def gen_hazard(d):
    """有害垃圾：产生点→暂存点（批次入库），每 3 天按批次出库→危废处置。"""
    for _ in range(2):
        region = R.choice(list(REGION_W))
        point = HAZ_POINT[region]
        wt = R.uniform(400, 800)
        veh = pick_vehicle("HAZARD_TRUCK", d)
        t0 = at(d, R.randint(8, 15), R.choice((0, 30)))
        t1 = t0 + timedelta(minutes=R.randint(40, 90))
        _haz_seq[0] += 1
        batch = f"HZ-{point[-2:]}-{_haz_seq[0]:05d}"
        no, st, w = add_leg(d, "HAZARD", R.choice(DROP_BY_REGION[region]), point, veh,
                            wt, t0, t1, batch=batch)
        if no and st in ("ARRIVED", "CONFIRMED"):
            stg.append((next_sto(d), point, "HAZARD", "IN", round(w / 1000, 3),
                        "吨", S(t1), batch, "NORMAL", no))
            b = {"batch": batch, "kg": w, "in_time": t1, "in_date": d, "ship": None}
            if _haz_seq[0] <= 2:
                b["hold"] = date(2099, 1, 1)                    # 超期滞留样本：始终在库
                injected["long_hazard"].append({"batch_no": batch, "facility": point,
                                                "days": (TODAY - d).days})
            HAZ_BUFFER[point].append(b)


def ship_hazard(d):
    for point, batches in HAZ_BUFFER.items():
        if d.day % 3:
            continue
        ready = [b for b in batches
                 if b["ship"] is None
                 and (("hold" in b and d >= b["hold"])
                      or ("hold" not in b and (d - b["in_date"]).days >= 1))]
        for b in ready:
            veh = pick_vehicle("HAZARD_TRUCK", d)
            t0 = at(d, R.randint(9, 14), 0)
            t1 = t0 + timedelta(minutes=R.randint(90, 150))
            no, st, w = add_leg(d, "HAZARD", point, "TM-HZ01", veh, b["kg"], t0, t1,
                                batch=b["batch"], leg_seq=2)
            if not no:
                continue
            b["ship"] = no
            if st in ("ARRIVED", "CONFIRMED"):
                stg.append((next_sto(d), point, "HAZARD", "OUT",
                            round(w / 1000, 3), "吨", S(t0), b["batch"],
                            "NORMAL", no))
            if st == "CONFIRMED":
                consume = t1 + timedelta(hours=R.randint(2, 6))
                add_disposal(consume.date(), "TM-HZ01", no, "HAZARD", w,
                             "HAZARD_TREAT",
                             {"危废安全处置_t": round(w / 1000, 3), "转运联单": no},
                             consume, batch=b["batch"])
                batches.remove(b)
                if (d - b["in_date"]).days > 365:
                    injected["long_hazard"].append({"batch_no": b["batch"],
                                                    "facility": point,
                                                    "days": (d - b["in_date"]).days})


def gen_recy(d, tonnage):
    for _ in range(max(1, round(tonnage * 1000 / 2200))):
        region = R.choice(list(REGION_W))
        wh = RECY_WH[region]
        wt = w_jitter(2200)
        veh = pick_vehicle("RECY_TRUCK", d)
        t0 = at(d, R.randint(8, 16), R.choice((0, 30)))
        t1 = t0 + timedelta(minutes=R.randint(30, 80))
        no, st, w = add_leg(d, "RECY", R.choice(DROP_BY_REGION[region]), wh, veh,
                            wt, t0, t1)
        if no and st in ("ARRIVED", "CONFIRMED"):
            stg.append((next_sto(d), wh, "RECY", "IN", round(w / 1000, 3),
                        "吨", S(t1), None, "NORMAL", no))
            RECY_BUFFER[wh].append({"kg": w, "in_date": d, "no": no, "ship": None})


def ship_recy(d):
    for wh, items in RECY_BUFFER.items():
        if R.random() > 0.7:
            continue
        ready = [x for x in items
                 if x["ship"] is None and (d - x["in_date"]).days >= 1]
        for chunk in [ready[i:i + 2] for i in range(0, len(ready), 2)]:
            total = sum(x["kg"] for x in chunk) * R.uniform(0.97, 0.99)
            veh = pick_vehicle("RECY_TRUCK", d)
            t0 = at(d, R.randint(9, 15), 0)
            t1 = t0 + timedelta(minutes=R.randint(50, 100))
            no, st, w = add_leg(d, "RECY", wh, "TM-RC01", veh, total, t0, t1, leg_seq=2)
            if not no:
                continue
            for x in chunk:
                x["ship"] = no
            if st in ("ARRIVED", "CONFIRMED"):
                for x in chunk:
                    stg.append((next_sto(d), wh, "RECY", "OUT",
                                round(x["kg"] / 1000, 3), "吨", S(t0), None,
                                "NORMAL", x["no"]))
            if st == "CONFIRMED":
                consume = t1 + timedelta(hours=R.randint(1, 4))
                add_disposal(consume.date(), "TM-RC01", no, "RECY", w, "RECYCLE",
                             {"再生原料_t": round(w * 0.88 / 1000, 3),
                              "市场交易线": "不经环卫考核"}, consume)
                for x in chunk:
                    items.remove(x)


def gen_constr(d, tonnage):
    for _ in range(max(1, round(tonnage * 1000 / 3200))):
        src = R.choice(list(CZ_YARD))
        yard = CZ_YARD[src]
        wt = w_jitter(3200)
        veh = pick_vehicle("CONSTR_TRUCK", d)
        t0 = at(d, R.randint(7, 17), R.choice((0, 30)))
        t1 = t0 + timedelta(minutes=R.randint(40, 110))
        no, st, w = add_leg(d, "CONSTR", src, yard, veh, wt, t0, t1)
        if no and st in ("ARRIVED", "CONFIRMED"):
            stg.append((next_sto(d), yard, "CONSTR", "IN", round(w * 0.0007, 2),
                        "m³", S(t1), None, "NORMAL", no))
            CZ_BUFFER[yard].append({"kg": w, "in_date": d, "no": no, "ship": None})


def ship_constr(d):
    for yard, items in CZ_BUFFER.items():
        if R.random() > 0.7:
            continue
        ready = [x for x in items
                 if x["ship"] is None and (d - x["in_date"]).days >= 2]
        if not ready:
            continue
        for chunk in [ready[i:i + 2] for i in range(0, len(ready), 2)]:
            m3 = sum(x["kg"] * 0.0007 for x in chunk) * R.uniform(0.96, 1.0)
            kg = m3 / 0.0007
            veh = pick_vehicle("CONSTR_TRUCK", d)
            t0 = at(d, R.randint(8, 15), 0)
            t1 = t0 + timedelta(minutes=R.randint(60, 120))
            no, st, w = add_leg(d, "CONSTR", yard, "TM-CZ01", veh, kg, t0, t1, leg_seq=2)
            if not no:
                continue
            for x in chunk:
                x["ship"] = no
            if st in ("ARRIVED", "CONFIRMED"):
                stg.append((next_sto(d), yard, "CONSTR", "OUT", round(m3, 2), "m³",
                            S(t0), None, "NORMAL", chunk[0]["no"]))
            if st == "CONFIRMED":
                consume = t1 + timedelta(hours=R.randint(2, 8))
                add_disposal(consume.date(), "TM-CZ01", no, "CONSTR", w, "RECYCLE",
                             {"再生骨料_m3": round(m3 * 0.8, 2), "再生建材_利用率": 0.832},
                             consume)
                for x in chunk:
                    items.remove(x)


def gen_bulk(d, tonnage):
    n = max(1, round(tonnage * 1000 / 2000))
    for _ in range(n):
        frm = R.choice(DROP_BY_REGION["460105"] + DROP_BY_REGION["460106"])
        wt = w_jitter(2000)
        veh = pick_vehicle("BULK_TRUCK", d)
        t0 = at(d, R.randint(8, 16), 0)
        t1 = t0 + timedelta(minutes=R.randint(60, 130))
        no, st, w = add_leg(d, "BULK", frm, "TM-BULK01", veh, wt, t0, t1)
        if not no or st != "CONFIRMED":
            continue
        batch = f"BJ-{no}"
        consume = t1 + timedelta(hours=R.randint(2, 8))
        add_disposal(consume.date(), "TM-BULK01", no, "BULK", w, "DISASSEMBLE",
                     {"可回用金属_t": round(w * 0.00008, 3),
                      "木材_t": round(w * 0.0001, 3),
                      "残渣_t": round(w * 0.00055, 3)}, consume, batch=batch)
        rd = d + timedelta(days=1)                              # 残渣续段（同批次）
        if rd > TODAY:
            continue
        rwt = w * R.uniform(0.5, 0.6)
        rveh = pick_vehicle("BULK_TRUCK", rd)
        rt0 = at(rd, R.randint(8, 11), 0)
        rt1 = rt0 + timedelta(minutes=R.randint(60, 120))
        rno, rst, rw = add_leg(rd, "BULK", "TM-BULK01", "TM-INC01", rveh, rwt, rt0, rt1,
                               batch=batch, leg_seq=2)
        if rno and rst == "CONFIRMED":
            rcon = (add_pit(rd, "TM-INC01", rno, "BULK", rw, rt1)
                    if R.random() < 0.3 else rt1 + timedelta(minutes=R.randint(30, 90)))
            add_disposal(rcon.date(), "TM-INC01", rno, "BULK", rw, "INCINERATION",
                         {"电力_kwh": round(rw * 0.44)}, rcon, batch=batch)


def gen_garden(d, tonnage):
    for _ in range(max(1, round(tonnage * 1000 / 2000))):
        frm = R.choice(["SOURCE-JQ01", "SOURCE-JQ02", "SOURCE-JQ03"] +
                       DROP_BY_REGION["460105"][:3])
        to = "TM-CMP01" if R.random() < 0.6 else "TM-INC01"
        wt = w_jitter(2000)
        veh = pick_vehicle("GARDEN", d)
        t0 = at(d, R.randint(7, 15), 0)
        t1 = t0 + timedelta(minutes=R.randint(60, 150))
        no, st, w = add_leg(d, "GARDEN", frm, to, veh, wt, t0, t1,
                            emergency=in_typhoon(d) and R.random() < 0.6)
        if no and st == "CONFIRMED":
            consume = t1 + timedelta(hours=R.randint(2, 10))
            if to == "TM-CMP01":
                add_disposal(consume.date(), to, no, "GARDEN", w, "COMPOST",
                             {"有机肥_t": round(w * 0.25, 3)}, consume)
            else:
                add_disposal(consume.date(), to, no, "GARDEN", w, "INCINERATION",
                             {"电力_kwh": round(w * 0.44)}, consume)


def gen_fecal_water(d):
    for _ in range(3):
        frm = R.choice(["SOURCE-FT01", "SOURCE-FT02", "SOURCE-FT03", "SOURCE-FT04"])
        wt = w_jitter(2000)
        veh = pick_vehicle("FECAL", d)
        t0 = at(d, R.randint(7, 14), 0)
        t1 = t0 + timedelta(minutes=R.randint(50, 110))
        no, st, w = add_leg(d, "FECAL", frm, "TM-FC01", veh, wt, t0, t1)
        if no and st == "CONFIRMED":
            consume = t1 + timedelta(hours=R.randint(1, 4))
            add_disposal(consume.date(), "TM-FC01", no, "FECAL", w, "ANAEROBIC",
                         {"沼气_m3": round(w * 30)}, consume)
    for _ in range(2):
        frm = R.choice(["SOURCE-MT01", "SOURCE-MT02"])
        wt = w_jitter(1500)
        veh = pick_vehicle("WATER", d)
        t0 = at(d, R.randint(7, 16), 0)
        t1 = t0 + timedelta(minutes=R.randint(40, 90))
        no, st, w = add_leg(d, "WATER", frm, "TM-INC01", veh, wt, t0, t1)
        if no and st == "CONFIRMED":
            consume = t1 + timedelta(hours=R.randint(1, 3))
            add_disposal(consume.date(), "TM-INC01", no, "WATER", w, "INCINERATION",
                         {"电力_kwh": round(w * 0.44)}, consume)


def gen_reclass(d):
    """分类不合格改道：原类别 KN_HOME，按其他垃圾焚烧。"""
    wt = w_jitter(1800)
    veh = pick_vehicle("OTHER_TRUCK", d)
    frm = R.choice(DROP_BY_REGION["460107"])
    t0 = at(d, R.randint(8, 14), 0)
    t1 = t0 + timedelta(minutes=R.randint(80, 140))
    no, st, w = add_leg(d, "OTHER", frm, "TM-INC01", veh, wt, t0, t1,
                        reclass_from="KN_HOME")
    if no and st == "CONFIRMED":
        injected["reclass"].append({"transfer_no": no, "date": d.isoformat()})
        consume = t1 + timedelta(minutes=R.randint(30, 90))
        add_disposal(consume.date(), "TM-INC01", no, "OTHER", w, "INCINERATION",
                     {"电力_kwh": round(w * 0.44), "备注": "拍照留底后按其他垃圾焚烧"},
                     consume)


def gen_emergency_storage(d):
    """台风应急临时堆放（EMERGENCY，不挂具体流转单）。"""
    if not in_typhoon(d) or R.random() > 0.6 or d >= TODAY:
        return
    point = R.choice(["TR-001", "TR-002"])
    wt = R.uniform(8000, 15000)
    stg.append((next_sto(d), point, "OTHER", "IN", round(wt / 1000, 3), "吨",
                S(at(d, 20)), None, "EMERGENCY", None))
    out_d = min(d + timedelta(days=R.randint(1, 3)), TODAY - timedelta(days=1))
    if out_d > d:
        stg.append((next_sto(out_d), point, "OTHER", "OUT", round(wt / 1000, 3),
                    "吨", S(at(out_d, 7)), None, "EMERGENCY", None))


# ---------------- 主流程 ----------------

def _load_pools(conn):
    for row in conn.execute(
            "SELECT region_code, facility_id FROM dim_facility "
            "WHERE status='RUNNING' AND facility_type='DROP'"):
        DROP_BY_REGION[row[0]].append(row[1])
    for row in conn.execute(
            "SELECT vehicle_id, vehicle_type, allowed_category, enrollment_type,"
            " valid_from, valid_to, status, owner_org, load_ton FROM dim_vehicle"):
        vid, vtype, cat, etype, vf, vt, st, owner, load = row
        if vtype == "OTHER_TRUCK":
            key = {"OTHER": "OTHER_TRUCK", "GARDEN": "GARDEN",
                   "FECAL": "FECAL", "WATER": "WATER"}[cat]
        else:
            key = vtype
        VEH_BY_CAT[key].append({"vehicle_id": vid, "type": vtype,
                                "enrollment_type": etype,
                                "valid_from": vf or "1900-01-01",
                                "valid_to": vt or "1900-01-01",
                                "status": st, "owner_org": owner, "load_ton": load})


# 请求标签 → 车辆池键
POOL_KEY = {"OTHER": "OTHER_TRUCK", "OTHER_TRUCK": "OTHER_TRUCK",
            "TRANSFER_TRUCK": "TRANSFER_TRUCK",
            "KITCHEN_TRUCK": "KITCHEN_TRUCK", "KN_HOME": "KITCHEN_TRUCK",
            "KN_CANTEEN": "KITCHEN_TRUCK", "HAZARD": "HAZARD_TRUCK",
            "HAZARD_TRUCK": "HAZARD_TRUCK", "BULK": "BULK_TRUCK",
            "BULK_TRUCK": "BULK_TRUCK", "RECY": "RECY_TRUCK",
            "RECY_TRUCK": "RECY_TRUCK", "CONSTR": "CONSTR_TRUCK",
            "CONSTR_TRUCK": "CONSTR_TRUCK", "GARDEN": "GARDEN",
            "FECAL": "FECAL", "WATER": "WATER"}


def _pick_special_dates(days):
    """从日期序列确定性挑出改道注入日期。"""
    step = max(1, len(days) // 13)
    return [days[i] for i in range(30, len(days) - 30, step)][:12]


def _flush(conn):
    """按天落库 + 每日提交（内存峰值有界，WAL 不会随总量增长）。"""
    n = len(trf)
    if trf:
        conn.executemany("INSERT INTO txn_transfer VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", trf)
        trf.clear()
    if stg:
        conn.executemany("INSERT INTO txn_storage VALUES (?,?,?,?,?,?,?,?,?,?)", stg)
        stg.clear()
    if dsp:
        conn.executemany("INSERT INTO txn_disposal VALUES (?,?,?,?,?,?,?,?,?,?)", dsp)
        dsp.clear()
    conn.commit()
    return n


def generate(conn):
    _load_pools(conn)
    total, d, n_days = 0, START, (TODAY - START).days
    reclass_days = set(_pick_special_dates(
        [START + timedelta(days=i) for i in range(n_days + 1)]))
    for _ in range(n_days + 1):
        f = {c: day_factor(c, d) for c in BASE}
        ton = {c: BASE[c] * f[c] for c in BASE}
        gen_other(d, ton["OTHER"])
        gen_kitchen(d, "KN_HOME", ton["KN_HOME"], "TM-KH01")
        gen_kitchen(d, "KN_CANTEEN", ton["KN_CANTEEN"], "TM-KN01")
        gen_hazard(d)
        ship_hazard(d)
        gen_recy(d, ton["RECY"])
        ship_recy(d)
        gen_constr(d, ton["CONSTR"])
        ship_constr(d)
        gen_bulk(d, ton["BULK"])
        gen_garden(d, ton["GARDEN"])
        gen_fecal_water(d)
        if d in reclass_days:
            gen_reclass(d)
        gen_emergency_storage(d)
        total += _flush(conn)          # 每日落库并提交
        d += timedelta(days=1)
    return total


def build_meta(conn):
    cnt = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("txn_transfer", "txn_storage", "txn_disposal")}
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "range": [START.isoformat(), TODAY.isoformat()],
        "seed": 42,
        "rows": {"transfer": cnt["txn_transfer"], "storage": cnt["txn_storage"],
                 "disposal": cnt["txn_disposal"]},
        "emergency_legs": conn.execute(
            "SELECT COUNT(*) FROM txn_transfer WHERE emergency_flag=1").fetchone()[0],
        "events": {
            "cny": [{"name": "春节", "date": c.isoformat()} for c in sorted(CNY.values())],
            "typhoons": [{"name": ev["name"], "landfall": ev["landfall"].isoformat(),
                          "window_start": (ev["landfall"] - timedelta(days=3)).isoformat(),
                          "window_end": (ev["landfall"] + timedelta(days=3)).isoformat()}
                         for ev in TYPHOONS],
        },
        "rules": [
            "春节前 7 天：家庭厨余/其他垃圾日清运量上浮约 +30%",
            "台风临近 72h：全品类清运量上浮约 +50%；灾后 3 天其他垃圾 +60%、园林垃圾 ×3",
            "周末（周六/周日）：其他/家庭厨余/可回收物 +10%",
            "冬季（11 月-2 月）旅游旺季 +6%；年增长 +3%",
        ],
        "injected": injected,
    }


if __name__ == "__main__":
    path = _db.DB_PATH
    os.makedirs(_db.DATA_DIR, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    conn = _db.connect(path)
    _db.init_schema(conn)
    print("seed:", _seed.seed_all(conn), flush=True)
    n = generate(conn)
    meta = build_meta(conn)
    meta_path = os.path.join(_db.DATA_DIR, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print("rows:", meta["rows"])
    print("injected:", {k: len(v) if isinstance(v, list) else v
                        for k, v in injected.items()})
    print("meta ->", meta_path)
