<template>
  <div>
    <div class="page-head">
      <h2>数据汇总</h2>
      <el-button type="success" :loading="exporting" @click="exportCsv"><el-icon><Download /></el-icon>导出 CSV</el-button>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent>
        <el-form-item label="粒度">
          <el-radio-group v-model="granularity" @change="resetAndLoad">
            <el-radio-button value="day">日</el-radio-button>
            <el-radio-button value="month">月</el-radio-button>
            <el-radio-button value="year">年</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                          start-placeholder="开始" end-placeholder="结束" style="width:230px" @change="resetAndLoad" />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="filters.category" clearable placeholder="全部" style="width:120px" @change="resetAndLoad">
            <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
          </el-select>
        </el-form-item>

        <!-- 设施维度 -->
        <template v-if="tab === 'storage'">
          <el-form-item label="设施">
            <el-select v-model="filters.facility" clearable filterable placeholder="全部设施" style="width:210px" @change="resetAndLoad">
              <el-option v-for="f in stashFacilities" :key="f.facility_id" :label="f.facility_name" :value="f.facility_id" />
            </el-select>
          </el-form-item>
        </template>
        <!-- 车辆维度 -->
        <template v-else>
          <el-form-item label="车辆">
            <el-select v-model="filters.vehicle" clearable filterable placeholder="全部车辆" style="width:190px" @change="resetAndLoad">
              <el-option v-for="v in vehicles" :key="v.vehicle_id"
                         :label="`${v.plate_no}（${v.category_name}）`" :value="v.vehicle_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="编制">
            <el-select v-model="filters.enrollment" clearable placeholder="全部" style="width:110px" @change="resetAndLoad">
              <el-option label="常规" value="REGULAR" /><el-option label="借调" value="TEMP" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item><el-button type="primary" @click="resetAndLoad"><el-icon><Search /></el-icon>查询</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" v-loading="loading">
      <el-tabs v-model="tab" @tab-change="resetAndLoad">
        <el-tab-pane label="设施出入库汇总" name="storage" />
        <el-tab-pane label="车辆工作量汇总" name="vehicle" />
      </el-tabs>

      <!-- 设施出入库 -->
      <el-table v-if="tab === 'storage'" :data="rows" stripe size="default">
        <el-table-column prop="period" label="周期" width="120" />
        <el-table-column prop="facility_name" label="设施" min-width="200" show-overflow-tooltip />
        <el-table-column label="设施类型" width="100">
          <template #default="{ row }">{{ facTypes[row.facility_type] || row.facility_type }}</template>
        </el-table-column>
        <el-table-column prop="category_name" label="类别" width="100" />
        <el-table-column label="入库量" width="130" align="right">
          <template #default="{ row }"><b style="color:#67c23a">{{ row.in_qty?.toLocaleString() }}</b> {{ row.unit }}</template>
        </el-table-column>
        <el-table-column label="出库量" width="130" align="right">
          <template #default="{ row }"><b style="color:#e6a23c">{{ row.out_qty?.toLocaleString() }}</b> {{ row.unit }}</template>
        </el-table-column>
        <el-table-column label="净存量" width="130" align="right">
          <template #default="{ row }">{{ ((row.in_qty || 0) - (row.out_qty || 0)).toLocaleString() }} {{ row.unit }}</template>
        </el-table-column>
        <el-table-column prop="entries" label="流水条数" width="90" align="right" />
      </el-table>

      <!-- 车辆工作量 -->
      <el-table v-else :data="rows" stripe size="default">
        <el-table-column prop="period" label="周期" width="120" />
        <el-table-column prop="plate_no" label="车牌" width="110" />
        <el-table-column label="车型" width="110">
          <template #default="{ row }">{{ vehTypes[row.vehicle_type] || row.vehicle_type }}</template>
        </el-table-column>
        <el-table-column prop="category_name" label="专类" width="90" />
        <el-table-column label="编制" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enrollment_type === 'TEMP' ? 'warning' : 'info'" size="small">
              {{ row.enrollment_type === 'TEMP' ? '借调' : '常规' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trips" label="趟次" width="80" align="right" />
        <el-table-column label="总载重(kg)" width="120" align="right">
          <template #default="{ row }">{{ row.total_kg?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="装载率" width="100" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.load_rate > 1 ? '#f56c6c' : '#409eff' }">{{ (row.load_rate * 100).toFixed(1) }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="emergency_trips" label="应急趟次" width="90" align="right" />
        <el-table-column prop="owner_org" label="所属单位" min-width="160" show-overflow-tooltip />
      </el-table>

      <el-pagination layout="total, sizes, prev, pager, next" :total="total" v-model:current-page="page"
                     v-model:page-size="size" :page-sizes="[20, 50, 100]" style="margin-top:12px"
                     @current-change="load" @size-change="resetAndLoad" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../api'

const facTypes = { SOURCE: '产生源', DROP: '投放点', COLLECT: '收集点', TRANSFER: '转运站', STORAGE: '暂存点', TERMINAL: '末端设施' }
const vehTypes = { OTHER_TRUCK: '其他垃圾车', KITCHEN_TRUCK: '厨余车', HAZARD_TRUCK: '有害车',
  BULK_TRUCK: '大件车', TRANSFER_TRUCK: '大型转运车', RECY_TRUCK: '可回收物回收车', CONSTR_TRUCK: '建筑垃圾车' }

const tab = ref('storage')
const granularity = ref('month')
const range = ref(null)
const filters = reactive({ facility: '', vehicle: '', category: '', enrollment: '' })
const rows = ref([]); const total = ref(0); const page = ref(1); const size = ref(20)
const loading = ref(false); const exporting = ref(false)
const categories = ref([]); const facilities = ref([]); const vehicles = ref([])

const stashFacilities = computed(() =>
  facilities.value.filter(f => ['TRANSFER', 'STORAGE', 'TERMINAL'].includes(f.facility_type)))

async function loadRefs() {
  categories.value = (await http.get('/categories')).data
  facilities.value = (await http.get('/facilities', { params: { size: 200 } })).data.items
  vehicles.value = (await http.get('/vehicles', { params: { size: 200 } })).data.items
}

function baseParams() {
  const p = { granularity: granularity.value, category: filters.category }
  if (range.value) { p.start = range.value[0]; p.end = range.value[1] }
  if (tab.value === 'storage') p.facility = filters.facility
  else { p.vehicle = filters.vehicle; p.enrollment = filters.enrollment }
  return p
}

async function load() {
  loading.value = true
  try {
    const url = tab.value === 'storage' ? '/reports/storage' : '/reports/vehicle'
    const res = await http.get(url, { params: { page: page.value, size: size.value, ...baseParams() } })
    rows.value = res.data.items; total.value = res.data.total
  } finally { loading.value = false }
}

function resetAndLoad() { page.value = 1; load() }

function localToday() {
  const d = new Date(); const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

async function exportCsv() {
  exporting.value = true
  try {
    const res = await http.get('/reports/export', {
      params: { type: tab.value, ...baseParams() }, responseType: 'blob'
    })
    const blob = new Blob([res], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = (tab.value === 'storage' ? '设施出入库汇总_' : '车辆工作量汇总_') +
      { day: '日', month: '月', year: '年' }[granularity.value] + '_' + localToday() + '.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally { exporting.value = false }
}

onMounted(() => { loadRefs(); load() })
</script>

<style scoped>
</style>
