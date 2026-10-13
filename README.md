# 海口市垃圾全生命周期管理系统 DEMO

以海口市真实业务结构为蓝本的缩比模拟演示系统：**全生命周期数据链 + 管理页 + 数据展板**。
统计分析模块（回归/时序/马尔可夫链/PCA/运力建议）按计划暂缓，接口与页面占位已预留。

## 技术栈

- 数据库：SQLite（单文件 `src/server/data/wms.db`，WAL 模式，26.7 万行流转单）
- 后端：Python 3.14 + FastAPI（依赖已装入项目根 `.venv`）
- 前端：Vue 3 + Element Plus + ECharts（Vite 构建，产物由 FastAPI 静态托管）

## 运行

> 详细部署步骤与常见问题见 **[docs/启动说明.md](docs/启动说明.md)**；Windows 下可直接双击项目根 **`启动.bat`** 一键启动。

```powershell
# 1. 启动后端（含前端静态托管，一个服务即可演示）
cd src\server
..\..\.venv\Scripts\python run.py 8000

# 2. 浏览器访问
#    数据展板  http://127.0.0.1:8000/dashboard
#    数据管理  http://127.0.0.1:8000/admin
#    演示登录  admin / haikou123（单角色演示级）
```

## 重新生成模拟数据（可选）

```powershell
cd src\server\app
..\..\..\.venv\Scripts\python generator.py    # 重建 wms.db + data/meta.json 规律清单
..\..\..\.venv\Scripts\python validate.py     # D-1~D-8 自检（30 项）
```

数据规律（预埋，详见 `src/server/data/meta.json`）：春节前 7 天厨余/其他 +30%、
台风临近 72h +50%、周末 +10%；注入勾稽异常/超载/中转过夜/有害超期/拒收回退/改道样本。

## 前端开发模式（可选）

```powershell
cd src\web
npm install
npm run dev        # http://localhost:5173，/api 代理到 8000
npm run build      # 产物 dist/，由 FastAPI 托管
```

## 目录结构

```
docs/            项目目标与验收 · 全流程汇报 · 数据库设计（v2.8）
src/server/      FastAPI 后端（app/routers 六组路由）+ schema.sql + 生成器 + 自检
src/web/         Vue3 前端（views/Dashboard.vue 展板 · views/admin/* 管理页）
```

## 演示脚本（对应验收 S-1~S-3）

1. **一车垃圾全旅程**：管理页建单（投放点→焚烧厂，专车专类校验）→ 到达 → 签收（生成消耗记录 DSP）→ 追溯查询还原单据链。
2. **节日峰值**：展板趋势图切"1 年"看春节前黄色标注带的清运量抬升（+30%）。
3. **台风应急**：趋势图红色台风标注带 + 借调车辆管理（VH-TMP 系列，时间窗外派单被拒）+ 应急标记单据统计。
4. **数据汇总（v1.1 新增）**：管理页「数据汇总」——设施出入库与车辆工作量（趟次/总载重/装载率）按 日/月/年 汇总，支持条件筛选与 CSV 导出（UTF-8 BOM，Excel 直接打开）。
