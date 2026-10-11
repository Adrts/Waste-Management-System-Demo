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
      <div v-for="k in kpis" :key="k.label" class="kpi panel">
        <i class="corner"></i><i class="corner"></i>
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
          <i class="corner"></i><i class="corner"></i>
          <div class="panel-title">类别结构
            <span class="sub">
              <el-select v-model="region" size="small" style="width:110px" @change="loadCategory">
                <el-option label="全市" value="" />
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
          <i class="corner"></i><i class="corner"></i>
          <div class="panel-title">运力利用率 <span class="sub">按类别 · 近 7 天（重载装载率口径）</span></div>
          <div ref="utilChart" class="chart fill"></div>
        </div>
      </div>

      <!-- 中列 -->
      <div class="col mid">
        <div class="panel grow2">
          <i class="corner"></i><i class="corner"></i>
          <div class="panel-title">清运 / 处置趋势
            <span class="sub">
              近
              <el-select v-model="trendDays" size="small" style="width:80px" @change="loadTrend">
                <el-option :value="30" label="30 天" />
                <el-option :value="90" label="90 天" />
                <el-option :value="180" label="180 天" />
                <el-option :value="365" label="1 年" />
              </el-select>
              · 节日 / 台风自动标注 · 预测线待接入分析模块
            </span>
          </div>
          <div ref="trendChart" class="chart fill"></div>
        </div>
        <div class="panel grow1">
          <i class="corner"></i><i class="corner"></i>
          <div class="panel-title">垃圾流向桑基图 <span class="sub">产生 → 中转 → 末端处置</span></div>
          <div ref="sankeyChart" class="chart fill"></div>
        </div>
      </div>

      <!-- 右列 -->
      <div class="col">
        <div class="panel grow1">
          <i class="corner"></i><i class="corner"></i>
          <div class="panel-title">设施分布与负荷 <span class="sub">点大小=接收量 · 颜色=类型</span></div>
          <div ref="mapChart" class="chart fill"></div>
        </div>
        <div class="panel grow1">
          <i class="corner"></i><i class="corner"></i>
          <div class="panel-title">预警中心
            <span class="sub">共 {{ alerts.length }} 条 · 点击下钻原始单据</span>
          </div>
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
const user = JSON.parse(localStorage.getItem('wms_user') || '{}')

const clock = ref('')
let clockTimer = null
function tick() {
  const d = new Date()
  const p = n => String(n).padStart(2, '0')
  clock.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

const kpi = ref({})
const kpis = computed(() => [
  { label: '今日清运量', value: (kpi.value.collected_kg / 1000).toFixed(1), unit: ' t', color: '#35e2d4',
    sub: `车次 ${kpi.value.trips} · 昨日 ${(kpi.value.collected_prev_day / 1000).toFixed(0)}t` },
  { label: '今日处置量', value: (kpi.value.disposal_kg / 1000).toFixed(1), unit: ' t', color: '#5eead4' },
  { label: '在途车次', value: kpi.value.in_transit, unit: ' 单', color: '#facc15' },
  { label: '无害化处置率', value: kpi.value.hazard_free_rate, unit: ' %', color: '#34d399', sub: '累计口径' },
  { label: '运力利用率', value: ((kpi.value.vehicle_utilization || 0) * 100).toFixed(1), unit: ' %', color: '#60a5fa', sub: '重载装载率' },
  { label: '预警数', value: kpi.value.alert_count, unit: ' 条', color: '#f87171' }
])

const region = ref('')
const trendDays = ref(90)
const alerts = ref([])
const drawer = ref(false)
const drawerTitle = ref('')
const timeline = ref([])

const catPie = ref(null); const catBar = ref(null); const utilChart = ref(null)
const trendChart = ref(null); const sankeyChart = ref(null); const mapChart = ref(null)
let charts = []

const CAT_COLORS = ['#2f7df6', '#35e2d4', '#facc15', '#f87171', '#34d399',
  '#a78bfa', '#fb923c', '#4ade80', '#e879f9', '#38bdf8']

function mk(refEl, opt) {
  const c = echarts.init(refEl)
  c.setOption(opt)
  charts.push(c)
  return c
}

async function loadKpi() {
  kpi.value = (await http.get('/stats/kpi')).data
}

async function loadCategory() {
  const rows = (await http.get('/stats/category', { params: { start: isoDaysAgo(30), region: region.value } })).data
  catPie.value && charts[0]?.setOption({
    series: [{ data: rows.map((r, i) => ({ name: r.category_name, value: Math.round(r.kg / 1000), itemStyle: { color: CAT_COLORS[i % 10] } })) }]
  })
  catBar.value && charts[1]?.setOption({
    yAxis: { data: rows.map(r => r.category_name).reverse() },
    series: [{ data: rows.map(r => +(r.kg / 1000).toFixed(1)).reverse() }]
  })
}

async function loadTrend() {
  const end = new Date(); const start = new Date(Date.now() - trendDays.value * 864e5)
  const data = (await http.get('/stats/trend', {
    params: { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
  })).data
  const dates = data.days.map(d => d.date)
  const mkArea = [], mkLine = []
  for (const e of data.events) {
    if (new Date(e.date) < new Date(dates[0]) || new Date(e.date) > new Date(dates.at(-1))) continue
    if (e.type === 'cny') {
      const d1 = new Date(e.date); const d0 = new Date(d1.getTime() - 2 * 864e5); const d2 = new Date(d1.getTime() + 5 * 864e5)
      const f = x => x.toISOString().slice(0, 10)
      mkArea.push([{ xAxis: f(d0), itemStyle: { color: 'rgba(250,204,21,.10)' }, label: { formatter: '春节', color: '#facc15' } },
                   { xAxis: f(d2) }])
    } else {
      mkArea.push([{ xAxis: e.window[0], itemStyle: { color: 'rgba(248,113,113,.12)' }, label: { formatter: e.name, color: '#f87171' } },
                   { xAxis: e.window[1] }])
    }
    mkLine.push({ xAxis: e.date, name: e.type === 'cny' ? '春节' : e.name })
  }
  charts[2]?.setOption({
    xAxis: { data: dates },
    series: [
      { name: '清运量', data: data.days.map(d => +(d.generated_kg / 1000).toFixed(1)) },
      { name: '处置量', data: data.days.map(d => +(d.disposal_kg / 1000).toFixed(1)) },
      { name: '事件', type: 'line', data: [],
        markArea: { silent: true, data: mkArea },
        markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#f87171', opacity: .55 },
          label: { show: true, position: 'insideEndTop', fontSize: 10, formatter: p => p.name },
          data: mkLine } }
    ]
  })
}

async function loadSankey() {
  const d = (await http.get('/stats/sankey')).data
  charts[3]?.setOption({
    series: [{ nodes: d.nodes, links: d.links }]
  })
}

async function loadMap() {
  const facs = (await http.get('/stats/facilities', { params: { days: 7 } })).data
  const byType = { TRANSFER: '#60a5fa', TERMINAL: '#34d399' }
  const geojson = await fetch('/geo/haikou.json').then(r => r.json()).catch(() => null)
  if (geojson) echarts.registerMap('haikou', geojson)
  const mapOpt = geojson ? {
    geo: {
      map: 'haikou', roam: false, zoom: 1.15, top: 12, bottom: 6,
      itemStyle: { areaColor: 'rgba(24,49,80,.85)', borderColor: 'rgba(56,116,163,.8)' },
      emphasis: { label: { show: false }, itemStyle: { areaColor: 'rgba(47,125,246,.25)' } },
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
  charts[5]?.setOption({
    yAxis: { data: cats },
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

function isoDaysAgo(n) {
  return new Date(Date.now() - n * 864e5).toISOString().slice(0, 10)
}

function logout() {
  localStorage.removeItem('wms_token')
  router.push('/login')
}

const baseGrid = { left: 8, right: 16, top: 26, bottom: 4, containLabel: true }

onMounted(async () => {
  tick(); clockTimer = setInterval(tick, 1000)

  // 类别环图
  mk(catPie.value, {
    tooltip: { trigger: 'item', formatter: '{b}: {c} t ({d}%)' },
    legend: { orient: 'vertical', right: 0, top: 'middle', textStyle: { color: '#9db8cf', fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    series: [{ type: 'pie', radius: ['52%', '78%'], center: ['38%', '50%'],
      label: { show: false }, itemStyle: { borderColor: '#0b1526', borderWidth: 2 } }]
  })
  // 类别条形
  mk(catBar.value, {
    grid: { ...baseGrid, top: 6, left: 20 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', axisLabel: { color: '#6b8ba6', fontSize: 9 }, splitLine: { lineStyle: { color: 'rgba(56,116,163,.2)' } } },
    yAxis: { type: 'category', axisLabel: { color: '#9db8cf', fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barWidth: 8, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#2f7df6' }, { offset: 1, color: '#35e2d4' }]), borderRadius: 4 }, label: { show: true, position: 'right', color: '#9db8cf', fontSize: 9, formatter: '{c} t' } }]
  })
  // 趋势
  mk(trendChart.value, {
    grid: { ...baseGrid, bottom: 20 },
    tooltip: { trigger: 'axis' },
    legend: { top: 2, right: 10, textStyle: { color: '#9db8cf', fontSize: 11 }, itemWidth: 14 },
    xAxis: { type: 'category', boundaryGap: false, axisLabel: { color: '#6b8ba6' }, axisLine: { lineStyle: { color: 'rgba(56,116,163,.5)' } } },
    yAxis: { type: 'value', name: '吨/日', nameTextStyle: { color: '#6b8ba6' }, axisLabel: { color: '#6b8ba6' }, splitLine: { lineStyle: { color: 'rgba(56,116,163,.18)' } } },
    series: [
      { name: '清运量', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 2, color: '#35e2d4' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(53,226,212,.25)' }, { offset: 1, color: 'rgba(53,226,212,0)' }]) } },
      { name: '处置量', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 2, color: '#2f7df6' } },
      { name: '事件', type: 'scatter', data: [] }
    ]
  })
  // 桑基
  mk(sankeyChart.value, {
    tooltip: { trigger: 'item' },
    series: [{ type: 'sankey', left: 10, right: 120, top: 8, bottom: 8,
      nodeWidth: 10, nodeGap: 10, draggable: false,
      label: { color: '#cfe3f5', fontSize: 10 },
      lineStyle: { color: 'gradient', opacity: .25, curveness: .5 },
      itemStyle: { borderColor: 'transparent' },
      emphasis: { focus: 'adjacency' } }]
  })
  // 地图
  await loadMap()
  // 运力利用率
  mk(utilChart.value, {
    grid: { ...baseGrid, left: 24 },
    tooltip: { trigger: 'axis', valueFormatter: v => v + ' %' },
    legend: { top: 0, right: 8, textStyle: { color: '#9db8cf', fontSize: 10 }, itemWidth: 12 },
    xAxis: { type: 'value', axisLabel: { color: '#6b8ba6', formatter: '{value}%' }, splitLine: { lineStyle: { color: 'rgba(56,116,163,.2)' } } },
    yAxis: { type: 'category', axisLabel: { color: '#9db8cf', fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [
      { name: '常规编制', type: 'bar', stack: 'u', barWidth: 9, itemStyle: { color: '#2f7df6', borderRadius: [4, 0, 0, 4] } },
      { name: '临时借调', type: 'bar', stack: 'u', barWidth: 9, itemStyle: { color: '#facc15', borderRadius: [0, 4, 4, 0] } }
    ]
  })

  const onResize = () => charts.forEach(c => c.resize())
  window.addEventListener('resize', onResize)
  window.__wmsResizeCleanup = onResize
  for (const fn of [loadKpi, loadCategory, loadTrend, loadSankey, loadMap, loadUtil, loadAlerts]) {
    try { await fn() } catch (e) { console.error('[dashboard]', fn.name, e) }
  }
  setInterval(() => { loadKpi().catch(() => {}); loadAlerts().catch(() => {}) }, 60000)
})

onBeforeUnmount(() => {
  clearInterval(clockTimer)
  if (window.__wmsResizeCleanup) window.removeEventListener('resize', window.__wmsResizeCleanup)
  charts.forEach(c => c.dispose())
})
</script>

<style scoped>
.hd { display: flex; align-items: center; padding: 10px 18px 6px; }
.hd-title { flex: 1; text-align: center; }
.hd-title h1 {
  font-size: 24px; letter-spacing: 6px; font-weight: 700;
  background: linear-gradient(180deg, #eaf7ff, #7fd8e8);
  -webkit-background-clip: text; color: transparent;
  text-shadow: 0 0 24px rgba(53,226,212,.25);
}
.hd-title p { font-size: 10px; letter-spacing: 4px; color: #4f7089; margin-top: 2px; }
.hd-left, .hd-right { width: 220px; display: flex; gap: 6px; align-items: center; }
.hd-right { justify-content: flex-end; }
.hd-date { color: #35e2d4; font-size: 14px; letter-spacing: 1px; }
.hd-btn { color: #7fa6c4; }

.kpi-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; padding: 4px 14px; }
.kpi { text-align: center; padding: 8px 6px 10px; }
.kpi-label { font-size: 12px; color: #7fa6c4; letter-spacing: 2px; }
.kpi-value { font-size: 30px; font-weight: 700; line-height: 1.25; text-shadow: 0 0 18px currentColor; }
.kpi-unit { font-size: 12px; margin-left: 3px; color: #7fa6c4; font-weight: 400; }
.kpi-sub { font-size: 10px; color: #537a97; }

.main-grid {
  flex: 1; display: grid; grid-template-columns: 1fr 1.5fr 1fr; gap: 10px;
  padding: 0 14px 12px; min-height: 0;
}
.col { display: flex; flex-direction: column; gap: 10px; min-height: 0; }
.grow { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.grow1 { flex: 1.1; display: flex; flex-direction: column; min-height: 0; }
.grow2 { flex: 1.5; display: flex; flex-direction: column; min-height: 0; }
.mid .grow2 { flex: 1.6; }
.mid .grow1 { flex: 1; }
.chart { width: 100%; min-height: 0; flex: 1; }
.chart.half { flex: 1; }

.corner { position: absolute; width: 10px; height: 10px; border-color: #35e2d4; border-style: solid; border-width: 0; }
.corner:nth-of-type(1) { bottom: -1px; left: -1px; border-bottom-width: 2px; border-left-width: 2px; }
.corner:nth-of-type(2) { bottom: -1px; right: -1px; border-bottom-width: 2px; border-right-width: 2px; }

.alert-list { flex: 1; overflow-y: auto; margin-top: 4px; }
.alert-item { padding: 6px 8px; border-radius: 6px; cursor: pointer; margin-bottom: 6px;
  background: rgba(20, 42, 66, .45); border: 1px solid rgba(56,116,163,.25); transition: .2s; }
.alert-item:hover { background: rgba(47,125,246,.15); border-color: rgba(53,226,212,.5); }
.alert-title { font-size: 12px; color: #ffd9a0; display: flex; align-items: center; gap: 6px; }
.lv-high .alert-title { color: #f87171; }
.lv-medium .alert-title { color: #facc15; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; box-shadow: 0 0 8px currentColor; flex: none; }
.alert-detail { font-size: 11px; color: #7fa6c4; margin-top: 3px; padding-left: 12px; }
.tl-detail { font-size: 12px; color: #9db8cf; }
</style>
