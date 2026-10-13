<template>
  <div>
    <div class="page-head">
      <h2>流转单管理</h2>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>建单</el-button>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline :model="filters" size="default">
        <el-form-item label="单号"><el-input v-model="filters.no" placeholder="HK-..." clearable style="width:170px" @keyup.enter="load" /></el-form-item>
        <el-form-item label="批次号"><el-input v-model="filters.batch" clearable style="width:150px" @keyup.enter="load" /></el-form-item>
        <el-form-item label="类别">
          <el-select v-model="filters.category" clearable placeholder="全部" style="width:130px">
            <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width:120px">
            <el-option label="在途 LOADED" value="LOADED" /><el-option label="已到达 ARRIVED" value="ARRIVED" /><el-option label="已签收 CONFIRMED" value="CONFIRMED" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width:230px" />
        </el-form-item>
        <el-form-item label="应急">
          <el-select v-model="filters.emergency" clearable placeholder="全部" style="width:100px">
            <el-option label="应急单" :value="1" /><el-option label="常规单" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item><el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" size="default" stripe>
        <el-table-column prop="transfer_no" label="流转单号" width="210" fixed>
          <template #default="{ row }">
            <el-link type="primary" @click="trace(row)">{{ row.transfer_no }}</el-link>
            <el-tag v-if="row.emergency_flag" type="danger" size="small" style="margin-left:4px">应急</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="batch_no" label="批次号" width="150" />
        <el-table-column label="段" width="50"><template #default="{ row }">{{ row.leg_seq }}</template></el-table-column>
        <el-table-column prop="category_name" label="类别" width="90" />
        <el-table-column label="改道自" width="90">
          <template #default="{ row }"><el-tag v-if="row.reclass_from" type="warning" size="small">{{ row.reclass_from }}</el-tag></template>
        </el-table-column>
        <el-table-column label="重量(kg)" width="100" align="right"><template #default="{ row }">{{ row.weight_kg.toLocaleString() }}</template></el-table-column>
        <el-table-column prop="from_name" label="起点" min-width="150" show-overflow-tooltip />
        <el-table-column prop="to_name" label="终点" min-width="150" show-overflow-tooltip />
        <el-table-column prop="plate_no" label="车辆" width="110" />
        <el-table-column label="装载率" width="80" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.weight_kg > row.load_ton * 1000 ? '#f56c6c' : '#67c23a' }">
              {{ (row.weight_kg / (row.load_ton * 1000) * 100).toFixed(0) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="row.status === 'CONFIRMED' ? 'success' : row.status === 'ARRIVED' ? 'warning' : 'primary'" size="small">
              {{ { LOADED: '在途', ARRIVED: '已到达', CONFIRMED: '已签收' }[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="loaded_time" label="装运时间" width="160" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'LOADED'" size="small" type="warning" @click="arrive(row)">到达</el-button>
            <el-button v-if="row.status === 'ARRIVED' && row.to_type === 'TERMINAL'" size="small" type="success" @click="openConfirm(row)">签收</el-button>
            <el-button v-if="row.status === 'ARRIVED' && row.to_type !== 'TERMINAL'" size="small" type="success" plain @click="confirmNonTerminal(row)">确认过站</el-button>
            <el-button v-if="row.status === 'ARRIVED' && row.to_type === 'TERMINAL'" size="small" type="danger" plain @click="reject(row)">拒收</el-button>
            <el-button v-if="row.status === 'LOADED'" size="small" @click="edit(row)">修改</el-button>
            <el-button v-if="row.status === 'LOADED'" size="small" type="danger" plain @click="del(row)">作废</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination layout="total, sizes, prev, pager, next" :total="total" v-model:current-page="page"
                     v-model:page-size="size" :page-sizes="[20, 50, 100]" style="margin-top:12px" @change="load" />
    </el-card>

    <!-- 建单 -->
    <el-dialog v-model="createVisible" title="新建流转单（一段一行）" width="640px">
      <el-alert v-if="createErr" type="error" :title="createErr" show-icon :closable="false" style="margin-bottom:12px" />
      <el-form :model="form" label-width="110px">
        <el-form-item label="垃圾类别" required>
          <el-select v-model="form.category_code" style="width:100%" @change="onCatChange">
            <el-option v-for="c in categories" :key="c.category_code" :label="`${c.category_name} (${c.category_code})`" :value="c.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="承运车辆" required>
          <el-select v-model="form.vehicle_id" style="width:100%" filterable
                     :placeholder="form.category_code ? '仅显示专车专类匹配车辆' : '请先选类别'">
            <el-option v-for="v in eligibleVehicles" :key="v.vehicle_id"
                       :label="`${v.plate_no} · 核载${v.load_ton}t · ${v.owner_org}${v.enrollment_type === 'TEMP' ? '（借调 ' + v.valid_from + '~' + v.valid_to + '）' : ''}`"
                       :value="v.vehicle_id" />
          </el-select>
          <div class="form-tip">专车专类校验：车辆 allowed_category 必须与本单类别一致（F-2）</div>
        </el-form-item>
        <el-form-item label="起点设施" required>
          <el-select v-model="form.from_facility_id" filterable style="width:100%">
            <el-option v-for="f in facilityOptions" :key="f.facility_id" :label="`${f.facility_name} (${f.facility_type})`" :value="f.facility_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="终点设施" required>
          <el-select v-model="form.to_facility_id" filterable style="width:100%">
            <el-option v-for="f in facilityOptions" :key="f.facility_id" :label="`${f.facility_name} (${f.facility_type}${f.status !== 'RUNNING' ? '·' + f.status : ''})`"
                       :value="f.facility_id" :disabled="f.status === 'SHUTDOWN'" />
          </el-select>
          <div class="form-tip">已关停（SHUTDOWN）设施禁止指向（F-8）</div>
        </el-form-item>
        <el-form-item label="装运重量(kg)" required>
          <el-input-number v-model="form.weight_kg" :min="1" :max="40000" style="width:100%" />
        </el-form-item>
        <el-form-item label="段序 leg_seq">
          <el-input-number v-model="form.leg_seq" :min="1" :max="5" />
          <span class="form-tip" style="margin-left:10px">1=产出段，同批次续段递增</span>
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="form.batch_no" placeholder="有害垃圾必填；跨中转混装续段禁止填写（F-4）" />
        </el-form-item>
        <el-form-item label="改道原类别">
          <el-select v-model="form.reclass_from" clearable placeholder="分类不合格改道时填写（如 KN_HOME）" style="width:100%">
            <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="装运时间">
          <el-date-picker v-model="form.loaded_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
        </el-form-item>
        <el-form-item label="应急标记">
          <el-switch v-model="form.emergency_flag" active-text="台风等应急清运" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">提交建单</el-button>
      </template>
    </el-dialog>

    <!-- 签收 -->
    <el-dialog v-model="confirmVisible" title="末端签收（生成消耗记录，闭环）" width="560px">
      <el-descriptions :column="2" border size="small" style="margin-bottom:12px">
        <el-descriptions-item label="流转单">{{ currentRow?.transfer_no }}</el-descriptions-item>
        <el-descriptions-item label="流转重量">{{ currentRow?.weight_kg }} kg</el-descriptions-item>
        <el-descriptions-item label="终点">{{ currentRow?.to_name }}</el-descriptions-item>
        <el-descriptions-item label="类别">{{ currentRow?.category_name }}</el-descriptions-item>
      </el-descriptions>
      <el-form :model="confirmForm" label-width="110px">
        <el-form-item label="末端实重(kg)" required>
          <el-input-number v-model="confirmForm.weight_kg" :min="1" style="width:100%" />
          <div class="form-tip">与流转重量偏差 &gt;3% 将计入勾稽异常</div>
        </el-form-item>
        <el-form-item label="消耗方式" required>
          <el-select v-model="confirmForm.disposal_method" style="width:100%">
            <el-option label="焚烧发电 INCINERATION" value="INCINERATION" />
            <el-option label="厌氧产沼 ANAEROBIC" value="ANAEROBIC" />
            <el-option label="堆肥 COMPOST" value="COMPOST" />
            <el-option label="拆解 DISASSEMBLE" value="DISASSEMBLE" />
            <el-option label="再生利用 RECYCLE" value="RECYCLE" />
            <el-option label="危废处置 HAZARD_TREAT" value="HAZARD_TREAT" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="success" :loading="saving" @click="saveConfirm">确认签收</el-button>
      </template>
    </el-dialog>

    <!-- 修改 -->
    <el-dialog v-model="editVisible" title="修改流转单（仅 LOADED）" width="480px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="装运重量(kg)"><el-input-number v-model="editForm.weight_kg" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="批次号"><el-input v-model="editForm.batch_no" /></el-form-item>
        <el-form-item label="应急标记"><el-switch v-model="editForm.emergency_flag" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../api'

const rows = ref([]); const total = ref(0); const page = ref(1); const size = ref(20)
const loading = ref(false); const saving = ref(false)
const categories = ref([]); const facilities = ref([]); const vehicles = ref([])
const filters = reactive({ no: '', batch: '', category: '', status: '', emergency: null })
const range = ref(null)
const createVisible = ref(false); const createErr = ref('')
const confirmVisible = ref(false); const editVisible = ref(false)
const currentRow = ref(null)
const form = reactive({ category_code: '', vehicle_id: '', from_facility_id: '', to_facility_id: '', weight_kg: 1000, leg_seq: 1, batch_no: '', reclass_from: '', loaded_time: '', emergency_flag: false })
const confirmForm = reactive({ weight_kg: 0, disposal_method: '' })
const editForm = reactive({ weight_kg: 0, batch_no: '', emergency_flag: false })

const eligibleVehicles = computed(() =>
  vehicles.value.filter(v => v.allowed_category === form.category_code &&
    (v.status === 'ACTIVE' || v.enrollment_type === 'TEMP')))
const facilityOptions = computed(() => facilities.value)

async function loadRefs() {
  categories.value = (await http.get('/categories')).data
  facilities.value = (await http.get('/facilities', { params: { size: 200 } })).data.items
  vehicles.value = (await http.get('/vehicles', { params: { size: 200 } })).data.items
}

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, size: size.value, ...filters }
    if (range.value) { params.start = range.value[0]; params.end = range.value[1] }
    const res = await http.get('/transfers', { params })
    rows.value = res.data.items; total.value = res.data.total
  } finally { loading.value = false }
}

function openCreate() {
  createErr.value = ''
  Object.assign(form, { category_code: '', vehicle_id: '', from_facility_id: '', to_facility_id: '', weight_kg: 1000, leg_seq: 1, batch_no: '', reclass_from: '', loaded_time: nowStr(), emergency_flag: false })
  createVisible.value = true
}

function onCatChange() {
  form.vehicle_id = ''
  if (form.category_code === 'HAZARD' && !form.batch_no) {
    form.batch_no = 'HZ-' + new Date().toISOString().slice(0, 10).replaceAll('-', '') + '-1'
  }
  if (form.category_code !== 'HAZARD' && form.batch_no.startsWith('HZ-')) form.batch_no = ''
}

async function save() {
  saving.value = true; createErr.value = ''
  try {
    const res = await http.post('/transfers', { ...form, batch_no: form.batch_no || null, reclass_from: form.reclass_from || null })
    ElMessage.success(res.message)
    createVisible.value = false; load()
  } catch (e) { createErr.value = e.message } finally { saving.value = false }
}

async function arrive(row) {
  await http.post(`/transfers/${row.transfer_no}/arrive`, {})
  ElMessage.success('已登记到达'); load()
}

function openConfirm(row) {
  currentRow.value = row
  confirmForm.weight_kg = row.weight_kg
  confirmForm.disposal_method = defaultMethod(row.category_code)
  confirmVisible.value = true
}

function defaultMethod(cat) {
  return { OTHER: 'INCINERATION', WATER: 'INCINERATION', KN_HOME: 'ANAEROBIC', KN_CANTEEN: 'ANAEROBIC',
    FECAL: 'ANAEROBIC', HAZARD: 'HAZARD_TREAT', BULK: 'DISASSEMBLE', RECY: 'RECYCLE',
    CONSTR: 'RECYCLE', GARDEN: 'COMPOST' }[cat] || 'INCINERATION'
}

async function saveConfirm() {
  saving.value = true
  try {
    const res = await http.post(`/transfers/${currentRow.value.transfer_no}/confirm`,
      { weight_kg: confirmForm.weight_kg, disposal_method: confirmForm.disposal_method })
    ElMessage.success(res.message)
    for (const w of res.data?.warnings || []) ElMessage.warning(w)
    confirmVisible.value = false; load()
  } catch (e) { ElMessage.error(e.message) } finally { saving.value = false }
}

async function confirmNonTerminal(row) {
  await http.post(`/transfers/${row.transfer_no}/arrive`, {}).catch(() => {})
  await http.post(`/transfers/${row.transfer_no}/confirm`, {
    weight_kg: row.weight_kg, disposal_method: 'INCINERATION'
  }).catch(e => ElMessage.error(e.message))
  ElMessage.success('已确认'); load()
}

async function reject(row) {
  const { value } = await ElMessageBox.prompt('请填写拒收原因（拒收后状态回退为 LOADED）', '拒收', {
    inputPlaceholder: '如：分类不合格，含杂质超标', inputValidator: v => !!v || '必填'
  })
  const res = await http.post(`/transfers/${row.transfer_no}/reject`, { reason: value })
  ElMessage.success(res.message); load()
}

function edit(row) {
  currentRow.value = row
  Object.assign(editForm, { weight_kg: row.weight_kg, batch_no: row.batch_no || '', emergency_flag: !!row.emergency_flag })
  editVisible.value = true
}
async function saveEdit() {
  saving.value = true
  try {
    await http.patch(`/transfers/${currentRow.value.transfer_no}`, {
      weight_kg: editForm.weight_kg, batch_no: editForm.batch_no || null, emergency_flag: editForm.emergency_flag
    })
    ElMessage.success('已修改'); editVisible.value = false; load()
  } catch (e) { ElMessage.error(e.message) } finally { saving.value = false }
}

async function del(row) {
  await ElMessageBox.confirm(`确认作废 ${row.transfer_no}？`, '作废', { type: 'warning' })
  await http.delete(`/transfers/${row.transfer_no}`)
  ElMessage.success('已作废'); load()
}

async function trace(row) {
  window.open('/admin/trace?transfer_no=' + encodeURIComponent(row.transfer_no), '_blank')
}

function nowStr() {
  const d = new Date(); const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:00`
}

onMounted(() => { loadRefs(); load() })
</script>

<style scoped>
.form-tip { font-size: 11px; color: #909399; line-height: 1.5; }
</style>
