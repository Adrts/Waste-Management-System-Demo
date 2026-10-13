-- ============================================================
-- 海口市垃圾清运全生命周期数据库（DEMO）· SQLite 实现
-- 依据《海口市垃圾清运全生命周期数据库设计》v2.7 建 6 张表
-- 类型按 SQLite 习惯微调：VARCHAR->TEXT, DECIMAL->REAL,
-- BOOLEAN->INTEGER(0/1), JSON->TEXT, DATETIME/DATE->TEXT(ISO)
-- ============================================================

PRAGMA foreign_keys = ON;

-- 1. dict_waste_category 垃圾类别字典
CREATE TABLE dict_waste_category (
    category_code   TEXT    PRIMARY KEY,                          -- 类别码，一经使用不可改名/复用
    category_name   TEXT    NOT NULL,                             -- 中文名称
    default_route   TEXT,                                         -- 默认处置路径
    is_market_line  INTEGER NOT NULL DEFAULT 0
                    CHECK (is_market_line IN (0,1))               -- 是否市场化回收线
);

-- 2. dim_facility 设施表（全链节点，含产生源）
CREATE TABLE dim_facility (
    facility_id      TEXT PRIMARY KEY,
    facility_name    TEXT NOT NULL,
    facility_type    TEXT NOT NULL
                     CHECK (facility_type IN
                     ('SOURCE','DROP','COLLECT','TRANSFER','STORAGE','TERMINAL')),
    region_code      TEXT,                                        -- 所辖区划
    address          TEXT,
    longitude        REAL NOT NULL,                               -- 坐标必填
    latitude         REAL NOT NULL,
    capacity_ton_day REAL,                                        -- 设计能力 吨/日
    operator         TEXT,
    type_attrs       TEXT,                                        -- 类型专属属性 JSON
    status           TEXT NOT NULL DEFAULT 'RUNNING'
                     CHECK (status IN ('RUNNING','BUILDING','SHUTDOWN'))
);

-- 3. dim_vehicle 车辆表（常规编制 + 临时借调，专车专类）
CREATE TABLE dim_vehicle (
    vehicle_id       TEXT PRIMARY KEY,                            -- 内部车辆号，车牌变更不变
    plate_no         TEXT NOT NULL UNIQUE,                        -- 车牌号
    vehicle_type     TEXT NOT NULL
                     CHECK (vehicle_type IN
                     ('OTHER_TRUCK','KITCHEN_TRUCK','HAZARD_TRUCK','BULK_TRUCK',
                      'TRANSFER_TRUCK','RECY_TRUCK','CONSTR_TRUCK')),  -- 后两类为 v2.7 枚举的 DEMO 扩展
    allowed_category TEXT NOT NULL
                     REFERENCES dict_waste_category(category_code),   -- 专车专类
    load_ton         REAL NOT NULL CHECK (load_ton > 0),
    owner_org        TEXT,
    enrollment_type  TEXT NOT NULL DEFAULT 'REGULAR'
                     CHECK (enrollment_type IN ('REGULAR','TEMP')),
    lender_org       TEXT,                                        -- TEMP 必填
    valid_from       TEXT,                                        -- 借调时间窗 TEMP 必填
    valid_to         TEXT,
    status           TEXT NOT NULL DEFAULT 'ACTIVE'
                     CHECK (status IN ('ACTIVE','REPAIR','RELEASED','RETIRED')),
    CHECK (enrollment_type <> 'TEMP'
           OR (lender_org IS NOT NULL AND valid_from IS NOT NULL AND valid_to IS NOT NULL))
);

-- 4. txn_transfer 流转单（核心脊柱，一段一行）
CREATE TABLE txn_transfer (
    transfer_no      TEXT PRIMARY KEY,                            -- HK-{日期}-{类别}-{流水}
    batch_no         TEXT,                                        -- 批次号：直运/同箱续运/残渣续段/有害必填
    leg_seq          INTEGER NOT NULL DEFAULT 1 CHECK (leg_seq >= 1),
    category_code    TEXT NOT NULL REFERENCES dict_waste_category(category_code),
    reclass_from     TEXT,                                        -- 分类不合格改道原类别
    weight_kg        REAL NOT NULL CHECK (weight_kg > 0),
    from_facility_id TEXT NOT NULL REFERENCES dim_facility(facility_id),
    to_facility_id   TEXT NOT NULL REFERENCES dim_facility(facility_id),
    vehicle_id       TEXT NOT NULL REFERENCES dim_vehicle(vehicle_id),
    carrier_org      TEXT,                                        -- 承运单位（文本冗余）
    status           TEXT NOT NULL DEFAULT 'LOADED'
                     CHECK (status IN ('LOADED','ARRIVED','CONFIRMED')),
    loaded_time      TEXT NOT NULL,
    arrived_time     TEXT,
    emergency_flag   INTEGER NOT NULL DEFAULT 0 CHECK (emergency_flag IN (0,1))
);
CREATE INDEX idx_trf_category  ON txn_transfer(category_code);
CREATE INDEX idx_trf_batch     ON txn_transfer(batch_no);
CREATE INDEX idx_trf_from      ON txn_transfer(from_facility_id);
CREATE INDEX idx_trf_to        ON txn_transfer(to_facility_id);
CREATE INDEX idx_trf_vehicle   ON txn_transfer(vehicle_id);
CREATE INDEX idx_trf_loaded    ON txn_transfer(loaded_time);
CREATE INDEX idx_trf_status    ON txn_transfer(status);
CREATE INDEX idx_trf_veh_time  ON txn_transfer(vehicle_id, loaded_time);

-- 5. txn_storage 暂存台账（设施级库存流水，库存=ΣIN−ΣOUT）
CREATE TABLE txn_storage (
    storage_id          TEXT PRIMARY KEY,                         -- 流水号
    facility_id         TEXT NOT NULL REFERENCES dim_facility(facility_id),
    category_code       TEXT NOT NULL REFERENCES dict_waste_category(category_code),
    io_type             TEXT NOT NULL CHECK (io_type IN ('IN','OUT')),
    quantity            REAL NOT NULL CHECK (quantity > 0),
    unit                TEXT NOT NULL DEFAULT '吨',               -- 建筑垃圾用 m³
    io_time             TEXT NOT NULL,                            -- 滞留天数计时钟
    batch_no            TEXT,                                     -- 仅可批次化品类（有害）必填
    reason              TEXT NOT NULL DEFAULT 'NORMAL'
                        CHECK (reason IN ('NORMAL','PROCESS','EMERGENCY')),
    related_transfer_no TEXT REFERENCES txn_transfer(transfer_no)
);
CREATE INDEX idx_stg_fac_cat ON txn_storage(facility_id, category_code);
CREATE INDEX idx_stg_fac_time ON txn_storage(facility_id, io_time);
CREATE INDEX idx_stg_batch   ON txn_storage(batch_no);
CREATE INDEX idx_stg_time    ON txn_storage(io_time);
CREATE INDEX idx_stg_related ON txn_storage(related_transfer_no);

-- 6. txn_disposal 消耗记录（末端实收与消耗方式）
CREATE TABLE txn_disposal (
    disposal_id     TEXT PRIMARY KEY,
    facility_id     TEXT NOT NULL REFERENCES dim_facility(facility_id),  -- 须 type=TERMINAL
    transfer_no     TEXT NOT NULL UNIQUE REFERENCES txn_transfer(transfer_no), -- 终段一一对应
    batch_no        TEXT,
    category_code   TEXT NOT NULL REFERENCES dict_waste_category(category_code),
    weight_kg       REAL NOT NULL DEFAULT 0,
    disposal_method TEXT
                    CHECK (disposal_method IN
                    ('INCINERATION','ANAEROBIC','COMPOST','DISASSEMBLE','RECYCLE','HAZARD_TREAT')),
    consume_time    TEXT,                                         -- 消耗完成时间
    reject_reason   TEXT                                          -- 拒收原因（拒收则状态回退）
);
CREATE INDEX idx_dsp_transfer ON txn_disposal(transfer_no);
CREATE INDEX idx_dsp_facility ON txn_disposal(facility_id);
CREATE INDEX idx_dsp_cat      ON txn_disposal(category_code);
CREATE INDEX idx_dsp_time     ON txn_disposal(consume_time);

-- ============================================================
-- 派生视图（不落列，按设计 v2.7 第四章）
-- ============================================================

-- 运力利用率：荷载=load_ton，实载=weight_kg（重载装载率口径）
CREATE VIEW v_vehicle_utilization AS
SELECT
    v.vehicle_id,
    v.vehicle_type,
    v.allowed_category        AS category_code,
    v.enrollment_type,
    v.owner_org,
    substr(t.loaded_time,1,10) AS stat_date,
    COUNT(*)                   AS trips,
    SUM(t.weight_kg)           AS loaded_kg,
    SUM(v.load_ton) * 1000.0   AS capacity_kg,
    ROUND(SUM(t.weight_kg) / (SUM(v.load_ton) * 1000.0), 4) AS utilization
FROM txn_transfer t
JOIN dim_vehicle v ON v.vehicle_id = t.vehicle_id
GROUP BY v.vehicle_id, substr(t.loaded_time,1,10);

-- 设施+类别 当前库存（ΣIN−ΣOUT，按批次细分可批次化品类）
CREATE VIEW v_storage_stock AS
SELECT
    facility_id,
    category_code,
    batch_no,
    MIN(unit) AS unit,
    ROUND(SUM(CASE WHEN io_type='IN' THEN quantity ELSE -quantity END), 3) AS stock,
    MAX(io_time) AS last_io_time
FROM txn_storage
GROUP BY facility_id, category_code, batch_no;
