"""生成数据自检：对照《DEMO项目目标与验收》5.1 数据层指标（D-1~D-8）。"""
import json
import sys

import db as _db

TOL = 0.03  # 勾稽容差 3%


def main():
    conn = _db.connect()
    c = conn.cursor()
    ok = []

    def check(name, cond, detail):
        ok.append(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name}: {detail}")

    # D-1 表结构
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    expect6 = {"dict_waste_category", "dim_facility", "dim_vehicle",
               "txn_transfer", "txn_storage", "txn_disposal"}
    check("D-1 六表齐全", expect6 <= set(tables), f"{sorted(tables)}")

    # D-2 时间跨度
    mn, mx = c.execute("SELECT MIN(loaded_time), MAX(loaded_time) FROM txn_transfer").fetchone()
    d0, d1 = mn[:10], mx[:10]
    from datetime import date
    span = (date.fromisoformat(d1) - date.fromisoformat(d0)).days
    check("D-2 跨度≥730天", span >= 730, f"{d0} ~ {d1} = {span} 天")

    # D-3 规模
    n = c.execute("SELECT COUNT(*) FROM txn_transfer").fetchone()[0]
    per_day = c.execute(
        "SELECT AVG(cnt) FROM (SELECT COUNT(*) cnt FROM txn_transfer GROUP BY substr(loaded_time,1,10))"
    ).fetchone()[0]
    check("D-3 流转单≥10万行", n >= 100000, f"{n} 行")
    check("D-3 日均≥300车次", per_day >= 300, f"日均 {per_day:.0f} 车次")

    # D-4 主数据
    fac = c.execute("SELECT COUNT(*) FROM dim_facility").fetchone()[0]
    veh = c.execute("SELECT COUNT(*) FROM dim_vehicle").fetchone()[0]
    temp = c.execute("SELECT COUNT(*) FROM dim_vehicle WHERE enrollment_type='TEMP'").fetchone()[0]
    cat = c.execute("SELECT COUNT(*) FROM dict_waste_category").fetchone()[0]
    check("D-4 设施≥100", fac >= 100, f"{fac}")
    check("D-4 车辆≥120 且 TEMP≥3", veh >= 120 and temp >= 3, f"{veh} 辆 / TEMP {temp}")
    check("D-4 类别=10", cat == 10, f"{cat}")

    # D-5 路径覆盖
    paths = {
        "直运(投放点→焚烧厂)": "SELECT COUNT(*) FROM txn_transfer t JOIN dim_facility f ON f.facility_id=t.from_facility_id WHERE f.facility_type='DROP' AND t.to_facility_id='TM-INC01'",
        "汇运(枢纽→焚烧厂)": "SELECT COUNT(*) FROM txn_transfer WHERE from_facility_id IN ('TR-001','TR-002','TR-003') AND to_facility_id='TM-INC01'",
        "农村三段(收集点→小型站)": "SELECT COUNT(*) FROM txn_transfer t JOIN dim_facility f ON f.facility_id=t.from_facility_id WHERE f.facility_type='COLLECT'",
        "有害批次链": "SELECT COUNT(*) FROM txn_transfer WHERE category_code='HAZARD' AND batch_no IS NOT NULL",
        "贮坑工艺暂存": "SELECT COUNT(*) FROM txn_storage WHERE reason='PROCESS'",
        "厨余/餐厨厌氧": "SELECT COUNT(*) FROM txn_disposal WHERE disposal_method='ANAEROBIC'",
        "可回收市场线": "SELECT COUNT(*) FROM txn_disposal WHERE category_code='RECY'",
        "大件拆解+残渣续段": "SELECT COUNT(*) FROM txn_transfer WHERE category_code='BULK' AND leg_seq=2",
        "建筑调配场": "SELECT COUNT(*) FROM txn_storage WHERE category_code='CONSTR'",
        "改道 reclass": "SELECT COUNT(*) FROM txn_transfer WHERE reclass_from IS NOT NULL",
        "应急标记": "SELECT COUNT(*) FROM txn_transfer WHERE emergency_flag=1",
        "应急暂存": "SELECT COUNT(*) FROM txn_storage WHERE reason='EMERGENCY'",
        "拒收回退样本": "SELECT COUNT(*) FROM txn_disposal WHERE reject_reason IS NOT NULL",
    }
    for name, sql in paths.items():
        v = c.execute(sql).fetchone()[0]
        check(f"D-5 {name}", v > 0, f"{v} 条")

    # D-6 勾稽平衡率（终段消耗 vs 流转单，容差 3%）
    total, bad = c.execute(f"""
        SELECT COUNT(*),
               SUM(CASE WHEN ABS(d.weight_kg - t.weight_kg) / t.weight_kg > {TOL} THEN 1 ELSE 0 END)
        FROM txn_disposal d JOIN txn_transfer t ON t.transfer_no = d.transfer_no
        WHERE d.reject_reason IS NULL""").fetchone()
    rate = 1 - bad / total
    check("D-6 勾稽平衡率≥99%", rate >= 0.99, f"{rate*100:.2f}%（异常 {bad}/{total}）")
    n_recon = c.execute("SELECT COUNT(*) FROM txn_disposal WHERE reject_reason IS NULL AND weight_kg > 0 "
                        f"AND ABS(weight_kg - (SELECT weight_kg FROM txn_transfer WHERE transfer_no=txn_disposal.transfer_no))"
                        f" / (SELECT weight_kg FROM txn_transfer WHERE transfer_no=txn_disposal.transfer_no) > 0.1").fetchone()[0]
    check("D-6 勾稽异常样本可触发", n_recon >= 5, f"{n_recon} 条 >10% 偏差")

    # D-7 库存口径（抽 3 设施×类别：ΣIN−ΣOUT 与视图一致）
    for fac_, cat_ in [("ST-HZ01", "HAZARD"), ("ST-RC01", "RECY"), ("TM-INC01", "OTHER")]:
        s1 = c.execute("SELECT ROUND(SUM(CASE WHEN io_type='IN' THEN quantity ELSE -quantity END),3) "
                       "FROM txn_storage WHERE facility_id=? AND category_code=?", (fac_, cat_)).fetchone()[0] or 0
        s2 = c.execute("SELECT ROUND(COALESCE(SUM(stock),0),3) FROM v_storage_stock "
                       "WHERE facility_id=? AND category_code=?", (fac_, cat_)).fetchone()[0]
        check(f"D-7 库存口径 {fac_}/{cat_}", abs(s1 - s2) < 0.001, f"明细 {s1} = 视图 {s2}")

    # D-8 规律核对：春节前7天 vs 基线
    def daily(cat, d0, d1):
        return c.execute(
            "SELECT AVG(w) FROM (SELECT SUM(weight_kg) w FROM txn_transfer "
            "WHERE category_code=? AND substr(loaded_time,1,10) BETWEEN ? AND ? "
            "GROUP BY substr(loaded_time,1,10))", (cat, d0, d1)).fetchone()[0]

    for cny, label in [("2025-01-29", "2025春节"), ("2026-02-17", "2026春节")]:
        pre = daily("OTHER", "2024-01-01", "2099-01-01")  # placeholder
        base = c.execute(
            "SELECT AVG(w) FROM (SELECT SUM(weight_kg) w FROM txn_transfer "
            "WHERE category_code='OTHER' AND substr(loaded_time,1,10) "
            "BETWEEN date(?, '-40 days') AND date(?, '-10 days') "
            "GROUP BY substr(loaded_time,1,10))", (cny, cny)).fetchone()[0]
        pre7 = c.execute(
            "SELECT AVG(w) FROM (SELECT SUM(weight_kg) w FROM txn_transfer "
            "WHERE category_code='OTHER' AND substr(loaded_time,1,10) "
            "BETWEEN date(?, '-7 days') AND date(?, '-1 day') "
            "GROUP BY substr(loaded_time,1,10))", (cny, cny)).fetchone()[0]
        check(f"D-8 {label}节前厨余/其他上浮≈+30%", 1.10 <= pre7 / base <= 1.50,
              f"节前 {pre7:.0f}kg/日 vs 基线 {base:.0f}kg/日 = {pre7/base-1:+.0%}")
    for ty, d in [("摩羯", "2024-09-05"), ("蝴蝶", "2025-06-14")]:
        base = c.execute(
            "SELECT AVG(w) FROM (SELECT SUM(weight_kg) w FROM txn_transfer "
            "WHERE substr(loaded_time,1,10) BETWEEN date(?, '-20 days') AND date(?, '-5 days') "
            "GROUP BY substr(loaded_time,1,10))", (d, d)).fetchone()[0]
        win = c.execute(
            "SELECT AVG(w) FROM (SELECT SUM(weight_kg) w FROM txn_transfer "
            "WHERE substr(loaded_time,1,10) BETWEEN date(?, '-3 days') AND ? "
            "GROUP BY substr(loaded_time,1,10))", (d, d)).fetchone()[0]
        check(f"D-8 台风{ty}临近72h上浮≈+50%", 1.25 <= win / base <= 1.9,
              f"窗口 {win:.0f} vs 基线 {base:.0f} = {win/base-1:+.0%}")
    wk = c.execute(
        "SELECT AVG(CASE WHEN CAST(strftime('%w', d) AS INT) IN (0,6) THEN w END), "
        "AVG(CASE WHEN CAST(strftime('%w', d) AS INT) NOT IN (0,6) THEN w END) "
        "FROM (SELECT substr(loaded_time,1,10) d, SUM(weight_kg) w FROM txn_transfer "
        "WHERE category_code='OTHER' GROUP BY d)").fetchone()
    wknd, wkdy = wk
    check("D-8 周末小高峰≈+10%", 1.03 <= wknd / wkdy <= 1.18,
          f"周末 {wknd:.0f} vs 工作日 {wkdy:.0f} = {wknd/wkdy-1:+.0%}")

    # 注入样本（来自 meta.json）
    try:
        with open(_db.DB_PATH.replace("wms.db", "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        inj = meta["injected"]
        print(f"\n注入清单: 勾稽异常 {len(inj['reconciliation'])} | 超载 {len(inj['overload'])} "
              f"| 过夜 {len(inj['overnight'])} | 有害超期 {len(inj['long_hazard'])} "
              f"| 贮坑滞留 {len(inj['long_pit'])} | 拒收 {len(inj['rejects'])} "
              f"| 改道 {len(inj['reclass'])} | 应急单 {meta.get('emergency_legs')}")
    except FileNotFoundError:
        print("meta.json 缺失")

    print(f"\n==== 结果: {sum(ok)}/{len(ok)} 通过 ====")
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
