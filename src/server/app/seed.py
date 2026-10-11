"""种子数据：10 类类别字典 + 100+ 设施 + 140+ 车辆（含临时借调样本）。

设施/车辆规模按 DEMO 缩比（真实：投放点 4624、产生源 6000+、收运车 489 辆），
保持业务结构与路径覆盖不变。运行 generate.py 时自动执行。
"""
import json

# 区划码：460105 秀英 460106 龙华 460107 琼山 460108 美兰 469023 澄迈(老城) 469005 文昌
XY, LH, QS, ML, CM, WC = "460105", "460106", "460107", "460108", "469023", "469005"

CATEGORIES = [
    # code, name, default_route, is_market_line
    ("OTHER",      "其他垃圾", "INCINERATION",    0),
    ("KN_HOME",    "家庭厨余", "KITCHEN_PLANT",   0),
    ("KN_CANTEEN", "餐厨垃圾", "KITCHEN_PLANT",   0),
    ("HAZARD",     "有害垃圾", "HAZARD_TREAT",    0),
    ("RECY",       "可回收物", "MARKET_RECYCLE",  1),
    ("BULK",       "大件垃圾", "BULK_DISASSEMBLE", 0),
    ("CONSTR",     "建筑垃圾", "CONSTR_RECYCLE",  0),
    ("GARDEN",     "园林垃圾", "COMPOST",         0),
    ("FECAL",      "粪渣",     "FECAL_TREAT",     0),
    ("WATER",      "水域垃圾", "INCINERATION",    0),
]

# facility_id, name, type, region, lng, lat, cap, operator, type_attrs, status
FACILITIES = [
    # ---- 末端设施 TERMINAL ----
    ("TM-INC01", "海口市生活垃圾焚烧发电厂（澄迈老城）", "TERMINAL", CM, 110.0150, 19.9450, 650, "中电国际新能源海南有限公司", '{"装机":"7炉6机 88MW","吨垃圾发电_kwh":440}', "RUNNING"),
    ("TM-KN01",  "餐厨废弃物无害化处理厂（澄迈老城）",   "TERMINAL", CM, 110.0210, 19.9510, 80,  "海南澄迈神州车用沼气有限公司", '{"工艺":"厌氧产沼"}', "RUNNING"),
    ("TM-KH01",  "家庭厨余资源化处理厂（澄迈老城）",     "TERMINAL", CM, 110.0260, 19.9560, 80,  "海南澄迈神州车用沼气有限公司", '{"工艺":"厌氧产沼"}', "RUNNING"),
    ("TM-BULK01","废弃家具处理厂（秀英）",               "TERMINAL", XY, 110.2450, 19.9880, 20,  "海南城发环境服务有限公司", '{}', "RUNNING"),
    ("TM-CZ01",  "建筑垃圾资源化利用厂（秀英美楠村）",   "TERMINAL", XY, 110.2260, 19.9700, 40,  "海南城发环境服务有限公司", '{}', "RUNNING"),
    ("TM-HZ01",  "海南危险废物处置中心",                 "TERMINAL", CM, 109.9820, 19.9080, 5,   "海南危废处置有限公司", '{"资质":"危废经营许可证"}', "RUNNING"),
    ("TM-CMP01", "园林绿化垃圾堆肥厂（琼山）",           "TERMINAL", QS, 110.3680, 19.9620, 15,  "海口市京环城市环境服务有限公司", '{}', "RUNNING"),
    ("TM-FC01",  "粪便无害化处理厂（澄迈）",             "TERMINAL", CM, 110.0080, 19.9380, 10,  "海南澄迈神州车用沼气有限公司", '{}', "RUNNING"),
    ("TM-RC01",  "再生资源加工利用厂（龙华）",           "TERMINAL", LH, 110.3210, 20.0510, 30,  "海南绿保再生资源有限公司", '{}', "RUNNING"),
    ("TM-LF01",  "颜春岭生活垃圾填埋场（已关停）",       "TERMINAL", CM, 110.0120, 19.9360, 0,   "海口市垃圾处理场", '{"备注":"2020年12月关停，无填埋兜底"}', "SHUTDOWN"),
    ("TM-WC01",  "海口文昌共建生活垃圾终端处理设施",     "TERMINAL", WC, 110.7530, 19.6180, 1200, "海口市城市管理局", '{"焚烧":1200,"厨余预处理":100,"粪便预处理":100,"投产":"2027"}', "BUILDING"),
    # ---- 转运站 TRANSFER ----
    ("TR-001", "白水塘转运站（秀英·大型I类枢纽）", "TRANSFER", XY, 110.2760, 19.9980, 1000, "海口市京环城市环境服务有限公司", '{"层级":"大型","服务":"西部"}', "RUNNING"),
    ("TR-002", "江东转运站（美兰·中型）",           "TRANSFER", ML, 110.3840, 20.0470, 300,  "海口市京环城市环境服务有限公司", '{"层级":"中型","服务":"东部"}', "RUNNING"),
    ("TR-003", "长流转运站（秀英·中型）",           "TRANSFER", XY, 110.2440, 20.0100, 150,  "海口市京环城市环境服务有限公司", '{"层级":"中型"}', "RUNNING"),
    ("TR-101", "秀英区海秀小型转运站",             "TRANSFER", XY, 110.2930, 20.0060, 60,  "海口玉禾田环境服务有限公司", '{"层级":"小型"}', "RUNNING"),
    ("TR-102", "秀英区西秀小型转运站",             "TRANSFER", XY, 110.2570, 20.0150, 50,  "海口玉禾田环境服务有限公司", '{"层级":"小型"}', "RUNNING"),
    ("TR-201", "龙华区金贸小型转运站",             "TRANSFER", LH, 110.3130, 20.0280, 60,  "海口龙马环卫环境工程有限公司", '{"层级":"小型"}', "RUNNING"),
    ("TR-301", "琼山区府城小型转运站",             "TRANSFER", QS, 110.3560, 19.9960, 60,  "海口市京环城市环境服务有限公司", '{"层级":"小型"}', "RUNNING"),
    ("TR-302", "琼山区凤翔小型转运站",             "TRANSFER", QS, 110.3450, 19.9790, 50,  "海口市京环城市环境服务有限公司", '{"层级":"小型"}', "RUNNING"),
    ("TR-401", "美兰区白龙小型转运站",             "TRANSFER", ML, 110.3640, 20.0350, 60,  "北京环境有限公司海南分公司", '{"层级":"小型"}', "RUNNING"),
    # ---- 暂存点 STORAGE ----
    ("ST-HZ01", "有害垃圾暂存点（秀英）", "STORAGE", XY, 110.2710, 20.0020, 2, "海口玉禾田环境服务有限公司", '{"限收品类":["HAZARD"]}', "RUNNING"),
    ("ST-HZ02", "有害垃圾暂存点（龙华）", "STORAGE", LH, 110.3180, 20.0240, 2, "海口龙马环卫环境工程有限公司", '{"限收品类":["HAZARD"]}', "RUNNING"),
    ("ST-HZ03", "有害垃圾暂存点（琼山）", "STORAGE", QS, 110.3510, 19.9900, 2, "海口市京环城市环境服务有限公司", '{"限收品类":["HAZARD"]}', "RUNNING"),
    ("ST-HZ04", "有害垃圾暂存点（美兰）", "STORAGE", ML, 110.3720, 20.0420, 2, "北京环境有限公司海南分公司", '{"限收品类":["HAZARD"]}', "RUNNING"),
    ("ST-RC01", "再生资源分拣仓（龙华）", "STORAGE", LH, 110.3260, 20.0440, 30, "海南绿保再生资源有限公司", '{"功能":"可回收物暂存转运"}', "RUNNING"),
    ("ST-RC02", "再生资源分拣仓（美兰）", "STORAGE", ML, 110.3910, 20.0560, 25, "海南绿保再生资源有限公司", '{"功能":"可回收物暂存转运"}', "RUNNING"),
    ("ST-CZ01", "建筑垃圾转运调配场（秀英）", "STORAGE", XY, 110.2380, 19.9810, 30, "海南城发环境服务有限公司", '{"unit":"m³"}', "RUNNING"),
    ("ST-CZ02", "建筑垃圾转运调配场（龙华）", "STORAGE", LH, 110.3060, 20.0610, 30, "海南城发环境服务有限公司", '{"unit":"m³"}', "RUNNING"),
    ("ST-CZ03", "建筑垃圾转运调配场（琼山）", "STORAGE", QS, 110.3740, 19.9530, 30, "海南城发环境服务有限公司", '{"unit":"m³"}', "RUNNING"),
    ("ST-CZ04", "建筑垃圾转运调配场（美兰）", "STORAGE", ML, 110.4050, 20.0280, 30, "海南城发环境服务有限公司", '{"unit":"m³"}', "RUNNING"),
]

# 投放点小区名池（42 个：秀英11 龙华11 琼山10 美兰10）
DROP_NAMES = {
    XY: ["海秀花园", "阳光郡小区", "丽晶花园", "西秀绿园", "金滩华府", "时代城小区",
         "港澳公寓", "保利中央海岸", "远大商城", "长滨五路西小区", "永庄村投放点"],
    LH: ["金贸文华小区", "龙华新城花园", "滨海丽景小区", "玉沙村投放点", "国贸大院",
         "世纪华庭", "龙昆苑小区", "城西路小区", "滨涯湖小区", "海垦花园", "世贸雅苑"],
    QS: ["府城文昌阁小区", "凤翔花园", "椰海家园", "红城湖国际小区", "琼山文庄小区",
         "培龙市场周边", "迈瀛村投放点", "河口路小区", "新市街小区", "那央村投放点"],
    ML: ["白龙苑小区", "海甸岛碧海小区", "新埠岛花园", "文明东小区", "蓝天路小区",
         "下洋社区投放点", "鹧鸪茶小区", "演丰墟投放点", "大英山西苑", "美舍河小区"],
}

# 产生源 SOURCE：餐饮8 工地5 化粪池4 市场3 景区3 码头2
SOURCES = [
    ("SOURCE-CY01", "海口皇冠假日酒店（餐厨签约）", "SOURCE", LH, 110.3230, 20.0330, 4, "商家自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-CY02", "琼菜王餐厅（龙昆南店）",       "SOURCE", QS, 110.3510, 20.0050, 3, "商家自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-CY03", "海口希尔顿酒店",               "SOURCE", ML, 110.3780, 20.0490, 4, "商家自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-CY04", "骑楼老街餐饮街区",             "SOURCE", LH, 110.3330, 20.0450, 5, "商家自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-CY05", "秀英寻尝里夜市",               "SOURCE", XY, 110.2850, 20.0110, 3, "商家自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-CY06", "海南大学食堂群（海甸）",       "SOURCE", ML, 110.3230, 20.0650, 6, "单位自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-CY07", "海南省人民医院食堂",           "SOURCE", LH, 110.3010, 20.0260, 2, "单位自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-CY08", "观澜湖度假区餐饮群",           "SOURCE", QS, 110.3430, 19.9320, 4, "商家自营", '{"签约":"餐厨收运协议"}'),
    ("SOURCE-GD01", "江东新区总部经济区工地",       "SOURCE", ML, 110.4030, 20.0510, 0, "中建三局", '{"工程":"在建"}'),
    ("SOURCE-GD02", "新海港片区改造项目工地",       "SOURCE", XY, 110.2620, 20.0240, 0, "中铁广州局", '{"工程":"在建"}'),
    ("SOURCE-GD03", "椰海大道东段装修集中点",       "SOURCE", QS, 110.3620, 19.9750, 0, "琼山城投", '{"工程":"装修"}'),
    ("SOURCE-GD04", "长流起步区安置房工地",         "SOURCE", XY, 110.2330, 20.0080, 0, "海口城建", '{"工程":"在建"}'),
    ("SOURCE-GD05", "美兰机场二期配套工地",         "SOURCE", ML, 110.4590, 19.9410, 0, "海南机场", '{"工程":"在建"}'),
    ("SOURCE-FT01", "秀英化粪池清掏点1号",          "SOURCE", XY, 110.2960, 19.9930, 0, "玉禾田", '{}'),
    ("SOURCE-FT02", "龙华化粪池清掏点1号",          "SOURCE", LH, 110.3170, 20.0370, 0, "龙马环卫", '{}'),
    ("SOURCE-FT03", "琼山化粪池清掏点1号",          "SOURCE", QS, 110.3490, 20.0010, 0, "京环公司", '{}'),
    ("SOURCE-FT04", "美兰化粪池清掏点1号",          "SOURCE", ML, 110.3680, 20.0530, 0, "京兰公司", '{}'),
    ("SOURCE-SC01", "培龙农贸市场",                 "SOURCE", QS, 110.3540, 19.9940, 0, "市场管理方", '{}'),
    ("SOURCE-SC02", "海垦农贸市场",                 "SOURCE", LH, 110.3090, 20.0190, 0, "市场管理方", '{}'),
    ("SOURCE-SC03", "白沙门综合市场",               "SOURCE", ML, 110.3310, 20.0700, 0, "市场管理方", '{}'),
    ("SOURCE-JQ01", "白沙门公园",                   "SOURCE", ML, 110.3290, 20.0730, 0, "海口旅文", '{}'),
    ("SOURCE-JQ02", "石山火山口公园",               "SOURCE", XY, 110.2080, 19.9330, 0, "海口旅文", '{}'),
    ("SOURCE-JQ03", "骑楼老街景区",                 "SOURCE", LH, 110.3350, 20.0440, 0, "海口旅文", '{}'),
    ("SOURCE-MT01", "秀英港水域保洁点",             "SOURCE", XY, 110.2740, 20.0280, 0, "海上环卫专责", '{}'),
    ("SOURCE-MT02", "新埠岛渔港水域保洁点",         "SOURCE", ML, 110.3860, 20.0630, 0, "海上环卫专责", '{}'),
]

# 农村收集点 COLLECT 6
COLLECTS = [
    ("CL-30101", "旧州镇垃圾收集点",   "COLLECT", QS, 110.4030, 19.9020, 0, "琼山区环卫站", '{}'),
    ("CL-30102", "三门坡镇垃圾收集点", "COLLECT", QS, 110.4410, 19.9170, 0, "琼山区环卫站", '{}'),
    ("CL-30103", "红旗镇垃圾收集点",   "COLLECT", QS, 110.4190, 19.9480, 0, "琼山区环卫站", '{}'),
    ("CL-40101", "三江镇垃圾收集点",   "COLLECT", ML, 110.4980, 19.9980, 0, "美兰区环卫站", '{}'),
    ("CL-40102", "演丰镇垃圾收集点",   "COLLECT", ML, 110.4680, 20.0270, 0, "美兰区环卫站", '{}'),
    ("CL-40103", "灵山镇垃圾收集点",   "COLLECT", ML, 110.4210, 20.0000, 0, "美兰区环卫站", '{}'),
]

# 车辆：type, allowed_category, load_ton, owner, count（前缀 VH-）
VEHICLE_GROUPS = [
    ("OTHER_TRUCK",    "OTHER",      8,  "海口玉禾田环境服务有限公司",           18),   # 秀英
    ("OTHER_TRUCK",    "OTHER",      8,  "海口龙马环卫环境工程有限公司",         18),   # 龙华
    ("OTHER_TRUCK",    "OTHER",      8,  "海口市京环城市环境服务有限公司",       17),   # 琼山
    ("OTHER_TRUCK",    "OTHER",      8,  "北京环境有限公司海南分公司",           17),   # 美兰
    ("KITCHEN_TRUCK",  "KN_HOME",    8,  "海口市京环城市环境服务有限公司",       12),
    ("KITCHEN_TRUCK",  "KN_CANTEEN", 8,  "海南澄迈神州车用沼气有限公司",         10),
    ("HAZARD_TRUCK",   "HAZARD",     5,  "海南危废运输有限公司",                 3),
    ("BULK_TRUCK",     "BULK",       10, "海南城发环境服务有限公司",             5),
    ("RECY_TRUCK",     "RECY",       5,  "海南绿保再生资源有限公司",             6),
    ("CONSTR_TRUCK",   "CONSTR",     15, "海南城发环境服务有限公司",             8),
    ("TRANSFER_TRUCK", "OTHER",      25, "海口市京环城市环境服务有限公司",       12),
    ("OTHER_TRUCK",    "GARDEN",     8,  "海口龙马环卫环境工程有限公司",         4),
    ("OTHER_TRUCK",    "FECAL",      8,  "海南澄迈神州车用沼气有限公司",         3),
    ("OTHER_TRUCK",    "WATER",      5,  "海上环卫专责队伍",                     2),
]

# 临时借调车辆（即借即登，台风事件样本 + 1 个在借）
TEMP_VEHICLES = [
    # id, plate_suffix, allowed, load, owner, lender, from, to, status
    ("VH-TMP01", "琼A·T9001", "OTHER",  8, "省外应急支援车队", "海南省环卫应急保障队", "2024-09-03", "2024-09-15", "RELEASED"),
    ("VH-TMP02", "琼A·T9002", "OTHER",  8, "省外应急支援车队", "海南省环卫应急保障队", "2024-09-05", "2024-09-20", "RELEASED"),
    ("VH-TMP03", "琼A·T9003", "GARDEN", 8, "跨区调度车队",     "海口市城市管理局",     "2026-08-10", "2026-08-25", "RELEASED"),
    ("VH-TMP04", "琼A·T9004", "OTHER",  8, "社会租赁车队",     "海口市城市管理局",     "2026-09-20", "2026-11-30", "ACTIVE"),
]


def _rnd_coord(region):
    """各区内确定性散布投放点坐标。"""
    centers = {XY: (110.285, 20.000), LH: (110.320, 20.028),
               QS: (110.358, 19.990), ML: (110.378, 20.042)}
    cx, cy = centers[region]
    n = len(DROP_NAMES[region])
    idx = sum(ord(c) for c in region)
    return (round(cx + ((idx * 7) % 50 - 25) / 1000 + 0.0, 4),
            round(cy + ((idx * 13) % 36 - 18) / 1000, 4))


def seed_all(conn):
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO dict_waste_category VALUES (?,?,?,?)", CATEGORIES)

    facilities = list(FACILITIES)
    fid_seq = {"DROP": 0, "SOURCE": 0}
    for region, names in DROP_NAMES.items():
        prefix = {XY: "1", LH: "2", QS: "3", ML: "4"}[region]
        for i, nm in enumerate(names, 1):
            fid_seq["DROP"] += 1
            dx, dy = _rnd_coord(region)
            facilities.append((
                f"DP-{prefix}{i:02d}", f"{nm}（分类投放点）", "DROP", region,
                round(dx + i * 0.0011, 4), round(dy + (i % 5) * 0.0009, 4),
                0, "各区环卫PPP企业", '{"桶位":4}', "RUNNING"))
    for fid, nm, typ, region, lng, lat, cap, op, attrs in SOURCES:
        facilities.append((fid, nm, typ, region, lng, lat, cap, op, attrs, "RUNNING"))
    for row in COLLECTS:
        facilities.append((*row, "RUNNING"))

    cur.executemany(
        """INSERT INTO dim_facility
           (facility_id,facility_name,facility_type,region_code,address,longitude,
            latitude,capacity_ton_day,operator,type_attrs,status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        [(f[0], f[1], f[2], f[3], "", f[4], f[5], f[6], f[7], f[8], f[9]) for f in facilities])

    plates = iter(_plate_seq())
    rows, seq = [], 0
    for vtype, allowed, load, owner, cnt in VEHICLE_GROUPS:
        for _ in range(cnt):
            seq += 1
            rows.append((f"VH-{seq:04d}", next(plates), vtype, allowed, load, owner,
                         "REGULAR", None, None, None, "ACTIVE"))
    for vid, plate, allowed, load, owner, lender, vf, vt, st in TEMP_VEHICLES:
        vtype = "KITCHEN_TRUCK" if allowed.startswith("KN") else (
            "BULK_TRUCK" if allowed == "BULK" else
            "OTHER_TRUCK" if allowed not in ("CONSTR",) else "CONSTR_TRUCK")
        rows.append((vid, plate, vtype, allowed, load, owner, "TEMP",
                     lender, vf, vt, st))
    cur.executemany(
        """INSERT INTO dim_vehicle
           (vehicle_id,plate_no,vehicle_type,allowed_category,load_ton,owner_org,
            enrollment_type,lender_org,valid_from,valid_to,status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()
    return {"categories": len(CATEGORIES), "facilities": len(facilities),
            "vehicles": len(rows)}


def _plate_seq():
    import itertools
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    for n in itertools.count(1):
        yield f"琼A·{letters[n % len(letters)]}{n * 37 % 10000:04d}"


if __name__ == "__main__":
    import db as _db
    conn = _db.connect()
    _db.init_schema(conn)
    print(seed_all(conn))
