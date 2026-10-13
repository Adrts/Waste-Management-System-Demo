<template>
  <div class="screen">
    <!-- 顶栏 -->
    <header class="hd">
      <div class="hd-left">
        <span class="hd-date num">{{ clock }}</span>
      </div>
      <div class="hd-title">
        <h1>海口市垃圾全生命周期管理数据展板</h1>
        <p>HAIKOU WASTE FULL-LIFECYCLE MANAGEMENT · DEMO</p>
      </div>
      <div class="hd-right">
        <el-button size="small" text class="hd-btn" @click="$router.push('/admin')">
          <el-icon><Setting /></el-icon>&nbsp;进入管理页
        </el-button>
        <el-button size="small" text class="hd-btn" @click="logout">
          <el-icon><SwitchButton /></el-icon>&nbsp;退出
        </el-button>
      </div>
    </header>

    <!-- KPI -->
    <section class="kpi-row">
      <div v-for="(k, i) in kpis" :key="k.label" class="kpi panel"
           :style="{ animationDelay: (i * 60) + 'ms' }">
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-value num" :style="{ color: k.color }">
          {{ k.value }}<span class="kpi-unit">{{ k.unit }}</span>
        </div>
        <div class="kpi-sub" v-if="k.sub">{{ k.sub }}</div>
      </div>
    </section>

    <!-- 主体三列 -->
    <section class="main-grid">
      <!-- 左列 -->
      <div class="col">
        <div class="panel grow">
          <div class="panel-title"><span class="tt">类别结构</span>
            <span class="sub">
              <el-select v-model="region" size="small" style="width:100px" @change="loadCategory">
                <el-option label="全市" value="ALL" />
                <el-option label="秀英区" value="460105" />
                <el-option label="龙华区" value="460106" />
                <el-option label="琼山区" value="460107" />
                <el-option label="美兰区" value="460108" />
              </el-select>
            </span>
          </div>
          <div ref="catPie" class="chart half"></div>
          <div ref="catBar" class="chart half"></div>
        </div>
        <div class="panel grow">
          <div class="panel-title"><span class="tt">运力利用率</span>
            <span class="sub">按类别 · 近 7 天（重载装载率）</span></div>
          <div ref="utilChart" class="chart fill"></div>
        </div>
      </div>

      <!-- 中列 -->
      <div class="col mid">
        <div class="panel grow2">
          <div class="panel-title"><span class="tt">清运 / 处置趋势</span>
            <span class="sub">
              近
              <el-select v-model="trendDays" size="small" style="width:76px" @change="loadTrend">
                <el-option :value="30" label="30 天" />
                <el-option :value="90" label="90 天" />
                <el-option :value="180" label="180 天" />
                <el-option :value="365" label="1 年" />
              </el-select>
              · 节日 / 台风标注 · 预测待接入
            </span>
          </div>
          <div ref="trendChart" class="chart fill"></div>
        </div>
        <div class="panel grow1">
          <div class="panel-title"><span class="tt">垃圾流向桑基图</span>
            <span class="sub">产生 → 中转 → 末端处置</span></div>
          <div ref="sankeyChart" class="chart fill"></div>
        </div>
      </div>

      <!-- 右列 -->
      <div class="col">
        <div class="panel grow1">
          <div class="panel-title"><span class="tt">设施分布与负荷</span>
            <span class="sub">点大小=接收量 · 颜色=类型</span></div>
          <div ref="mapChart" class="chart fill"></div>
        </div>
        <div class="panel grow1">
          <div class="panel-title"><span class="tt">预警中心</span>
            <span class="sub">共 {{ alerts.length }} 条 · 点击下钻</span></div>
          <div class="alert-list">
            <div v-for="(a, i) in alerts.slice(0, 30)" :key="i" class="alert-item"
                 :class="'lv-' + a.level" @click="drill(a)">
              <div class="alert-title">
                <span class="dot"></span>{{ a.title }}
              </div>
              <div class="alert-detail">{{ a.detail }}</div>
            </div>
            <el-empty v-if="!alerts.length" description="暂无预警" :image-size="50" />
          </div>
        </div>
      </div>
    </section>

    <!-- 下钻抽屉 -->
    <el-drawer v-model="drawer" :title="drawerTitle" size="46%" class="drill-drawer">
      <el-timeline v-if="timeline.length">
        <el-timeline-item v-for="(t, i) in timeline" :key="i" :timestamp="t.time"
                          :type="t.event.includes('消耗') ? 'success' : (t.event.includes('拒收') ? 'danger' : 'primary')">
          <b>{{ t.event }}</b> · {{ t.facility }}
          <div class="tl-detail">{{ t.detail }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="无流转轨迹" />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import http from '../api'

const router = useRouter()

const clock = ref('')
let clockTimer = null
function tick() {
  const d = new Date()
  const p = n => String(n).padStart(2, '0')
  clock.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

const kpi = ref({})
// KPI 数字滚动：display 向目标值缓动
const display = ref({ collected: 0, disposal: 0, trips: 0, transit: 0, rate: 0, util: 0, alerts: 0 })
let rafId = null
function animateTo(target) {
  const from = { ...display.value }
  const t0 = performance.now(); const dur = 700
  cancelAnimationFrame(rafId)
  const step = now => {
    const p = Math.min(1, (now - t0) / dur)
    const e = 1 - Math.pow(1 - p, 3)                     // easeOutCubic
    const o = {}
    for (const key in target) o[key] = from[key] + (target[key] - from[key]) * e
    display.value = o
    if (p < 1) rafId = requestAnimationFrame(step)
  }
  rafId = requestAnimationFrame(step)
}

const kpis = computed(() => [
  { label: '今日清运量', value: display.value.collected.toFixed(1), unit: ' t', color: '#2154d8',
    sub: `车次 ${Math.round(display.value.trips)} · 昨日 ${((kpi.value.collected_prev_day || 0) / 1000).toFixed(0)}t` },
  { label: '今日处置量', value: display.value.disposal.toFixed(1), unit: ' t', color: '#0e9f8a' },
  { label: '在途车次', value: String(Math.round(display.value.transit)), unit: ' 单', color: '#d97706' },
  { label: '无害化处置率', value: display.value.rate.toFixed(1), unit: ' %', color: '#16a34a', sub: '累计口径' },
  { label: '运力利用率', value: display.value.util.toFixed(1), unit: ' %', color: '#6366f1', sub: '重载装载率' },
  { label: '预警数', value: String(Math.round(display.value.alerts)), unit: ' 条', color: '#ef4444' }
])

const region = ref('ALL')
const trendDays = ref(90)
const alerts = ref([])
const drawer = ref(false)
const drawerTitle = ref('')
const timeline = ref([])

const catPie = ref(null); const catBar = ref(null); const utilChart = ref(null)
const trendChart = ref(null); const sankeyChart = ref(null); const mapChart = ref(null)
let charts = []
let kpiTimer = null
let onResizeFn = null

const CAT_COLORS = ['#2154d8', '#10b981', '#f59e0b', '#ef4444', '#6366f1',
  '#14b8a6', '#f97316', '#8b5cf6', '#ec4899', '#0ea5e9']
const C = { axisText: '#8a97ab', label: '#5a6a85', split: '#e8edf5', axisLine: '#d5dde9' }

function mk(refEl, opt) {
  const c = echarts.init(refEl)
  c.setOption(opt)
  charts.push(c)
  return c
}

// 按 ref 取已初始化的实例，避免 charts[N] 数字索引与初始化顺序强耦合
function chartOf(refEl) {
  return refEl.value ? echarts.getInstanceByDom(refEl.value) : null
}

async function loadKpi() {
  kpi.value = (await http.get('/stats/kpi')).data
  animateTo({
    collected: (kpi.value.collected_kg || 0) / 1000,
    disposal: (kpi.value.disposal_kg || 0) / 1000,
    trips: kpi.value.trips || 0,
    transit: kpi.value.in_transit || 0,
    rate: kpi.value.hazard_free_rate || 0,
    util: (kpi.value.vehicle_utilization || 0) * 100,
    alerts: kpi.value.alert_count || 0
  })
}

async function loadCategory() {
  const rows = (await http.get('/stats/category', {
    params: { start: isoDaysAgo(30), region: region.value === 'ALL' ? '' : region.value }
  })).data
  catPie.value && chartOf(catPie)?.setOption({
    series: [{ data: rows.map((r, i) => ({ name: r.category_name, value: Math.round(r.kg / 1000), itemStyle: { color: CAT_COLORS[i % 10] } })) }]
  })
  catBar.value && chartOf(catBar)?.setOption({
    yAxis: { data: rows.map(r => r.category_name).reverse() },
    series: [{ data: rows.map(r => +(r.kg / 1000).toFixed(1)).reverse() }]
  })
}

async function loadTrend() {
  const end = new Date(); const start = new Date(Date.now() - trendDays.value * 864e5)
  const data = (await http.get('/stats/trend', {
    params: { start: fmtLocal(start), end: fmtLocal(end) }
  })).data
  const dates = data.days.map(d => d.date)
  const mkArea = [], mkLine = []
  for (const e of data.events) {
    if (new Date(e.date) < new Date(dates[0]) || new Date(e.date) > new Date(dates.at(-1))) continue
    if (e.type === 'cny') {
      const d1 = new Date(e.date); const d0 = new Date(d1.getTime() - 2 * 864e5); const d2 = new Date(d1.getTime() + 5 * 864e5)
      const f = fmtLocal
      mkArea.push([{ xAxis: f(d0), itemStyle: { color: 'rgba(245, 158, 11, .10)' }, label: { formatter: '春节', color: '#d97706' } },
                   { xAxis: f(d2) }])
    } else {
      mkArea.push([{ xAxis: e.window[0], itemStyle: { color: 'rgba(239, 68, 68, .08)' }, label: { formatter: e.name, color: '#ef4444' } },
                   { xAxis: e.window[1] }])
    }
    mkLine.push({ xAxis: e.date, name: e.type === 'cny' ? '春节' : e.name })
  }
  chartOf(trendChart)?.setOption({
    xAxis: { data: dates },
    series: [
      { name: '清运量', data: data.days.map(d => +(d.generated_kg / 1000).toFixed(1)) },
      { name: '处置量', data: data.days.map(d => +(d.disposal_kg / 1000).toFixed(1)) },
      { name: '事件', type: 'line', data: [],
        markArea: { silent: true, data: mkArea },
        markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#ef4444', opacity: .55 },
          label: { show: true, position: 'insideEndTop', fontSize: 10, formatter: p => p.name },
          data: mkLine } }
    ]
  })
}

async function loadSankey() {
  const d = (await http.get('/stats/sankey')).data
  chartOf(sankeyChart)?.setOption({
    series: [{ nodes: d.nodes, links: d.links }]
  })
}

async function loadMap() {
  const facs = (await http.get('/stats/facilities', { params: { days: 7 } })).data
  const byType = { TRANSFER: '#2154d8', TERMINAL: '#10b981' }
  const geojson = await fetch('/geo/haikou.json').then(r => r.json()).catch(() => null)
  if (!mapChart.value) return                                    // 页面已卸载，放弃渲染
  if (geojson) echarts.registerMap('haikou', geojson)
  const mapOpt = geojson ? {
    geo: {
      map: 'haikou', roam: false, zoom: 1.15, top: 12, bottom: 6,
      itemStyle: { areaColor: '#e3ebf9', borderColor: '#c2d2ef' },
      emphasis: { label: { show: false }, itemStyle: { areaColor: '#d0e0fb' } },
      select: { disabled: true }
    },
    tooltip: { formatter: p => p.name ? `${p.name}<br/>近7日接收 ${p.value[2]} t` : '' },
    series: [
      {
        type: 'scatter', coordinateSystem: 'geo',
        data: facs.map(f => ({
          name: f.facility_name,
          value: [f.longitude, f.latitude, Math.round(f.received_kg / 1000)],
          symbolSize: Math.max(6, Math.min(26, Math.sqrt(f.received_kg / 1000) * 1.4)),
          itemStyle: { color: byType[f.facility_type], shadowBlur: 8, shadowColor: byType[f.facility_type] }
        }))
      }
    ]
  } : { xAxis: { show: false }, yAxis: { show: false }, series: [] }
  const c = echarts.getInstanceByDom(mapChart.value) || echarts.init(mapChart.value)
  c.setOption(mapOpt)
  if (!charts.includes(c)) charts.push(c)
}

async function loadUtil() {
  const rows = (await http.get('/stats/utilization')).data.filter(r => r.category_code)
  const cats = [...new Set(rows.map(r => r.category_code))]
  const nameByCode = Object.fromEntries(rows.map(r => [r.category_code, r.category_name || r.category_code]))
  chartOf(utilChart)?.setOption({
    yAxis: { data: cats.map(c => nameByCode[c]) },
    series: [
      { name: '常规编制', data: cats.map(c => { const r = rows.find(x => x.category_code === c && x.enrollment_type === 'REGULAR'); return r ? +(r.utilization * 100).toFixed(1) : 0 }) },
      { name: '临时借调', data: cats.map(c => { const r = rows.find(x => x.category_code === c && x.enrollment_type === 'TEMP'); return r ? +(r.utilization * 100).toFixed(1) : 0 }) }
    ]
  })
}

async function loadAlerts() {
  alerts.value = (await http.get('/stats/alerts')).data
}

async function drill(a) {
  const refs = a.refs || {}
  if (a.type === 'station_balance') {
    drawerTitle.value = a.title + ' — ' + a.detail
    timeline.value = [{ time: refs.date, event: '设施级预警', facility: a.detail,
      detail: '请在管理页「追溯查询」中按该设施 + 日期组合核查当日进出单据' }]
    drawer.value = true
    return
  }
  const q = refs.batch_no ? `batch_no=${encodeURIComponent(refs.batch_no)}`
    : refs.transfer_no ? `transfer_no=${encodeURIComponent(refs.transfer_no)}`
      : refs.facility_id ? `facility_id=${encodeURIComponent(refs.facility_id)}` : null
  if (!q) return
  drawerTitle.value = a.title + ' — ' + a.detail
  const res = await http.get('/trace?' + q)
  timeline.value = res.data.timeline || []
  drawer.value = true
}

function fmtLocal(d) {
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
function isoDaysAgo(n) {
  return fmtLocal(new Date(Date.now() - n * 864e5))   // 本地时区，避免 UTC 取数偏移一天
}

function logout() {
  localStorage.removeItem('wms_token')
  localStorage.removeItem('wms_user')
  router.push('/login')
}

const baseGrid = { left: 8, right: 16, top: 26, bottom: 4, containLabel: true }

onMounted(async () => {
  tick(); clockTimer = setInterval(tick, 1000)

  // 类别环图
  mk(catPie.value, {
    tooltip: { trigger: 'item', formatter: '{b}: {c} t ({d}%)' },
    legend: { type: 'scroll', orient: 'horizontal', bottom: 0, left: 'center',
      textStyle: { color: C.label, fontSize: 10 }, itemWidth: 10, itemHeight: 10,
      pageIconSize: 9, pageTextStyle: { fontSize: 9 } },
    series: [{ type: 'pie', radius: ['44%', '68%'], center: ['50%', '44%'],
      label: { show: false }, itemStyle: { borderColor: '#fff', borderWidth: 2 } }]
  })
  // 类别条形
  mk(catBar.value, {
    grid: { ...baseGrid, top: 6, left: 20, right: 34 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', splitNumber: 3,
      axisLabel: { color: C.axisText, fontSize: 9,
        formatter: v => v >= 1000 ? (v / 1000).toFixed(v % 1000 ? 1 : 0) + 'k' : v },
      splitLine: { lineStyle: { color: C.split } } },
    yAxis: { type: 'category', axisLabel: { color: C.label, fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barWidth: 8, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#2154d8' }, { offset: 1, color: '#6f8ff0' }]), borderRadius: 4 },
      label: { show: true, position: 'right', color: C.label, fontSize: 9, formatter: p => p.value >= 1000 ? (p.value / 1000).toFixed(1) + 'k' : p.value } }]
  })
  // 趋势
  mk(trendChart.value, {
    grid: { ...baseGrid, bottom: 22 },
    tooltip: { trigger: 'axis' },
    legend: { top: 2, right: 10, textStyle: { color: C.label, fontSize: 11 }, itemWidth: 14 },
    xAxis: { type: 'category', boundaryGap: false,
      axisLabel: { color: C.axisText, formatter: v => v.slice(5) },
      axisLine: { lineStyle: { color: C.axisLine } } },
    yAxis: { type: 'value', name: '吨/日', nameTextStyle: { color: C.axisText }, axisLabel: { color: C.axisText }, splitLine: { lineStyle: { color: C.split } } },
    series: [
      { name: '清运量', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 2, color: '#2154d8' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(33, 84, 216, .16)' }, { offset: 1, color: 'rgba(33, 84, 216, 0)' }]) } },
      { name: '处置量', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 2, color: '#10b981' } },
      { name: '事件', type: 'scatter', data: [] }
    ]
  })
  // 桑基
  mk(sankeyChart.value, {
    tooltip: { trigger: 'item' },
    series: [{ type: 'sankey', left: 10, right: 116, top: 8, bottom: 8,
      nodeWidth: 10, nodeGap: 10, draggable: false,
      label: { color: '#33415c', fontSize: 10, width: 106, overflow: 'truncate',
        formatter: p => p.data.name },
      lineStyle: { color: 'gradient', opacity: .25, curveness: .5 },
      itemStyle: { borderColor: 'transparent' },
      emphasis: { focus: 'adjacency' } }]
  })
  // 运力利用率
  mk(utilChart.value, {
    grid: { ...baseGrid, left: 24 },
    tooltip: { trigger: 'axis', valueFormatter: v => v + ' %' },
    legend: { top: 0, right: 8, textStyle: { color: C.label, fontSize: 10 }, itemWidth: 12 },
    xAxis: { type: 'value', axisLabel: { color: C.axisText, formatter: '{value}%' }, splitLine: { lineStyle: { color: C.split } } },
    yAxis: { type: 'category', axisLabel: { color: C.label, fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [
      { name: '常规编制', type: 'bar', stack: 'u', barWidth: 9, itemStyle: { color: '#2154d8', borderRadius: [4, 0, 0, 4] } },
      { name: '临时借调', type: 'bar', stack: 'u', barWidth: 9, itemStyle: { color: '#f59e0b', borderRadius: [0, 4, 4, 0] } }
    ]
  })
  // 地图
  const onResize = () => charts.forEach(c => c.resize())
  window.addEventListener('resize', onResize)
  onResizeFn = onResize
  loadMap().catch(e => console.error('[dashboard] loadMap', e))
  for (const fn of [loadKpi, loadCategory, loadTrend, loadSankey, loadUtil, loadAlerts]) {
    try { await fn() } catch (e) { console.error('[dashboard]', fn.name, e) }
  }
  kpiTimer = setInterval(() => { loadKpi().catch(() => {}); loadAlerts().catch(() => {}) }, 60000)
})

onBeforeUnmount(() => {
  clearInterval(clockTimer)
  clearInterval(kpiTimer)
  cancelAnimationFrame(rafId)
  if (onResizeFn) window.removeEventListener('resize', onResizeFn)
  charts.forEach(c => c.dispose())
})
</script>

<style scoped>
.hd {
  display: flex; align-items: center; padding: 12px 18px;
  background: #fff; border-bottom: 1px solid #e8edf5;
}
.hd-title { flex: 1; text-align: center; min-width: 0; }
.hd-title h1 { font-size: 20px; letter-spacing: 2px; font-weight: 700; color: #16337a; white-space: nowrap; }
.hd-title p { font-size: 10px; letter-spacing: 3px; color: #8a97ab; margin-top: 2px; white-space: nowrap; }
.hd-left, .hd-right { width: 190px; display: flex; gap: 6px; align-items: center; }
.hd-right { justify-content: flex-end; }
.hd-date { color: #2154d8; font-size: 14px; letter-spacing: 1px; }
.hd-btn { color: #6b7a90; }
.hd-btn:hover { color: #2154d8; }

.kpi-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; padding: 12px 14px 0; }
.kpi { text-align: center; padding: 10px 6px 12px; transition: transform .25s ease, box-shadow .25s ease; }
.kpi:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(15, 34, 67, .10); }
.kpi-label { font-size: 12px; color: #6b7a90; letter-spacing: 2px; }
.kpi-value { font-size: 30px; font-weight: 700; line-height: 1.3; }
.kpi-unit { font-size: 12px; margin-left: 3px; color: #8a97ab; font-weight: 400; }
.kpi-sub { font-size: 10px; color: #6b7a90; }

.main-grid {
  flex: 1; display: grid; grid-template-columns: 1fr 1.5fr 1fr; gap: 10px;
  padding: 10px 14px 12px; min-height: 0;
}
.col { display: flex; flex-direction: column; gap: 10px; min-height: 0; }
.grow { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.grow1 { flex: 1.1; display: flex; flex-direction: column; min-height: 0; }
.grow2 { flex: 1.5; display: flex; flex-direction: column; min-height: 0; }
.mid .grow2 { flex: 1.6; }
.mid .grow1 { flex: 1; }
.chart { width: 100%; min-height: 0; flex: 1; }
.chart.half { flex: 1; }

.alert-list { flex: 1; overflow-y: auto; margin-top: 4px; }
.alert-item { padding: 6px 8px; border-radius: 6px; cursor: pointer; margin-bottom: 6px;
  background: #f7f9fc; border: 1px solid #e8edf5; transition: .2s; }
.alert-item:hover { background: #ecf0fb; border-color: #c2cdf2; transform: translateX(2px); }
.alert-title { font-size: 12px; color: #6b7a90; display: flex; align-items: center; gap: 6px; }
.lv-high .alert-title { color: #ef4444; }
.lv-medium .alert-title { color: #d97706; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex: none; }
.alert-detail { font-size: 11px; color: #6b7a90; margin-top: 3px; padding-left: 12px; }
.tl-detail { font-size: 12px; color: #5a6a85; }

/* 浅色面板卡片 */
.screen {
  height: 100vh; display: flex; flex-direction: column; overflow: hidden;
  background: linear-gradient(180deg, #f7f9fc, #eef2f8);
  color: #1f2d3d;
}
.panel {
  position: relative;
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 10px;
  padding: 10px 12px;
  box-shadow: 0 2px 10px rgba(15, 34, 67, .05);
  animation: fadeUp .5s ease both;
}
.mid .panel:nth-child(1) { animation-delay: 80ms; }
.mid .panel:nth-child(2) { animation-delay: 160ms; }
.col:not(.mid) .panel:nth-child(1) { animation-delay: 120ms; }
.col:not(.mid) .panel:nth-child(2) { animation-delay: 200ms; }
.panel-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 600; color: #1f2d3d; margin-bottom: 4px;
  min-width: 0; flex-wrap: nowrap;
}
.panel-title::before {
  content: ""; width: 4px; height: 14px; border-radius: 2px;
  background: #2154d8; flex: none;
}
.panel-title .tt { white-space: nowrap; flex: none; }
.panel-title .sub {
  margin-left: auto; min-width: 0;
  display: flex; align-items: center; gap: 2px;
  font-size: 11px; letter-spacing: 0; color: #6b7a90; font-weight: 400;
  white-space: nowrap; overflow: hidden;
}
.panel-title .sub > * { flex: none; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: none; }
}
</style>
