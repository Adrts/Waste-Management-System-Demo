<template>
  <div>
    <div class="page-head">
      <h2>车辆管理（常规编制 + 临时借调，专车专类）</h2>
      <div>
        <el-button type="warning" @click="openCreate('TEMP')"><el-icon><Plus /></el-icon>借调车辆即借即登</el-button>
        <el-button type="primary" @click="openCreate('REGULAR')"><el-icon><Plus /></el-icon>新增常规车辆</el-button>
      </div>
    </div>
    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width:140px">
            <el-option label="在役 ACTIVE" value="ACTIVE" /><el-option label="维修 REPAIR" value="REPAIR" />
            <el-option label="已退场 RELEASED" value="RELEASED" /><el-option label="报废 RETIRED" value="RETIRED" />
          </el-select>
        </el-form-item>
        <el-form-item label="编制">
          <el-select v-model="filters.enrollment" clearable placeholder="全部" style="width:130px">
            <el-option label="常规 REGULAR" value="REGULAR" /><el-option label="借调 TEMP" value="TEMP" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字"><el-input v-model="filters.keyword" placeholder="车辆号/车牌/单位" clearable style="width:180px" @keyup.enter="load" /></el-form-item>
        <el-form-item><el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="vehicle_id" label="车辆号" width="100" />
        <el-table-column prop="plate_no" label="车牌" width="110" />
        <el-table-column label="车型" width="120"><template #default="{ row }">{{ vtypes[row.vehicle_type] }}</template></el-table-column>
        <el-table-column prop="category_name" label="专类" width="90">
          <template #default="{ row }"><el-tag size="small">{{ row.category_name }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="load_ton" label="核载(t)" width="80" align="right" />
        <el-table-column prop="owner_org" label="所属单位" min-width="170" show-overflow-tooltip />
        <el-table-column label="编制" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enrollment_type === 'TEMP' ? 'warning' : 'info'" size="small">{{ row.enrollment_type === 'TEMP' ? '借调' : '常规' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="借调信息" min-width="190">
          <template #default="{ row }">
            <span v-if="row.enrollment_type === 'TEMP'">{{ row.lender_org }} · {{ row.valid_from }} ~ {{ row.valid_to }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="transfer_count" label="单量" width="70" align="right" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'RELEASED' ? 'info' : 'danger'" size="small">
              {{ { ACTIVE: '在役', REPAIR: '维修', RELEASED: '已退场', RETIRED: '报废' }[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="edit(row)">编辑</el-button>
            <el-button v-if="row.enrollment_type === 'TEMP' && row.status === 'ACTIVE'" size="small" type="warning" plain @click="release(row)">退场</el-button>
            <el-button size="small" type="danger" plain :disabled="row.transfer_count > 0" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination layout="total, prev, pager, next" :total="total" v-model:current-page="page"
                     v-model:page-size="size" style="margin-top:12px" @change="load" />
    </el-card>

    <el-dialog v-model="visible" :title="isEdit ? '编辑车辆' : (form.enrollment_type === 'TEMP' ? '临时借调车辆登记（即借即登）' : '新增常规车辆')" width="560px">
      <el-alert v-if="err" type="error" :title="err" show-icon :closable="false" style="margin-bottom:12px" />
      <el-form :model="form" label-width="120px">
        <el-form-item label="车辆编号" required><el-input v-model="form.vehicle_id" :disabled="isEdit" placeholder="如 VH-TMP05" /></el-form-item>
        <el-form-item label="车牌号" required><el-input v-model="form.plate_no" placeholder="琼A·XXXXX" /></el-form-item>
        <el-form-item label="车型" required>
          <el-select v-model="form.vehicle_type" style="width:100%">
            <el-option v-for="(label, v) in vtypes" :key="v" :label="label" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="允许类别" required>
          <el-select v-model="form.allowed_category" style="width:100%">
            <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
          </el-select>
          <div class="tip">专车专类：建单时与本单类别联动校验（F-2）</div>
        </el-form-item>
        <el-form-item label="核载(t)" required><el-input-number v-model="form.load_ton" :min="0.5" :max="40" style="width:100%" /></el-form-item>
        <el-form-item label="所属单位"><el-input v-model="form.owner_org" /></el-form-item>
        <el-form-item label="编制">
          <el-radio-group v-model="form.enrollment_type">
            <el-radio value="REGULAR">常规 REGULAR</el-radio><el-radio value="TEMP">临时借调 TEMP</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.enrollment_type === 'TEMP'">
          <el-form-item label="借调单位" required><el-input v-model="form.lender_org" placeholder="TEMP 必填" /></el-form-item>
          <el-form-item label="借调时间窗" required>
            <el-date-picker v-model="tempRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="valid_from" end-placeholder="valid_to" style="width:100%" />
            <div class="tip">时间窗外的派单将被拒绝（F-5）</div>
          </el-form-item>
        </template>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="在役 ACTIVE" value="ACTIVE" /><el-option label="维修 REPAIR" value="REPAIR" />
            <el-option label="已退场 RELEASED" value="RELEASED" /><el-option label="报废 RETIRED" value="RETIRED" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../api'

const vtypes = { OTHER_TRUCK: '其他垃圾车', KITCHEN_TRUCK: '厨余车', HAZARD_TRUCK: '有害车',
  BULK_TRUCK: '大件车', TRANSFER_TRUCK: '大型转运车', RECY_TRUCK: '可回收物回收车', CONSTR_TRUCK: '建筑垃圾车' }
const rows = ref([]); const total = ref(0); const page = ref(1); const size = ref(20)
const loading = ref(false); const saving = ref(false)
const categories = ref([])
const filters = reactive({ status: '', enrollment: '', keyword: '' })
const visible = ref(false); const err = ref(''); const isEdit = ref(false)
const tempRange = ref(null)
const form = reactive({ vehicle_id: '', plate_no: '', vehicle_type: 'OTHER_TRUCK', allowed_category: 'OTHER', load_ton: 8, owner_org: '', enrollment_type: 'REGULAR', lender_org: '', status: 'ACTIVE' })

async function loadRefs() { categories.value = (await http.get('/categories')).data }

async function load() {
  loading.value = true
  try {
    const res = await http.get('/vehicles', { params: { page: page.value, size: size.value, ...filters } })
    rows.value = res.data.items; total.value = res.data.total
  } finally { loading.value = false }
}

function openCreate(enrollment) {
  err.value = ''; isEdit.value = false; tempRange.value = null
  Object.assign(form, { vehicle_id: '', plate_no: '', vehicle_type: enrollment === 'TEMP' ? 'OTHER_TRUCK' : 'OTHER_TRUCK', allowed_category: 'OTHER', load_ton: 8, owner_org: '', enrollment_type: enrollment, lender_org: '', status: 'ACTIVE' })
  visible.value = true
}

function edit(row) {
  err.value = ''; isEdit.value = true
  Object.assign(form, row)
  tempRange.value = row.valid_from && row.valid_to ? [row.valid_from, row.valid_to] : null
  visible.value = true
}

async function save() {
  saving.value = true; err.value = ''
  try {
    const body = { ...form }
    if (body.enrollment_type === 'TEMP') {
      if (!tempRange.value) throw new Error('借调车辆必须填写借调时间窗（TEMP 必填 lender_org + 时间窗）')
      body.valid_from = tempRange.value[0]; body.valid_to = tempRange.value[1]
    } else { body.lender_org = null; body.valid_from = null; body.valid_to = null }
    const res = isEdit.value ? await http.put(`/vehicles/${encodeURIComponent(form.vehicle_id)}`, body)
      : await http.post('/vehicles', body)
    ElMessage.success(res.message); visible.value = false; load()
  } catch (e) { err.value = e.message } finally { saving.value = false }
}

async function release(row) {
  await ElMessage.confirm(`确认【${row.plate_no}】退场？退场后置 RELEASED，历史流转单仍可追溯（F-5）。`, '借调退场', { type: 'warning' })
  const res = await http.post(`/vehicles/${encodeURIComponent(row.vehicle_id)}/release`)
  ElMessage.success(res.message); load()
}

async function del(row) {
  await ElMessage.confirm(`确认删除 ${row.plate_no}？`, '删除', { type: 'warning' })
  const res = await http.delete(`/vehicles/${encodeURIComponent(row.vehicle_id)}`)
  ElMessage.success(res.message); load()
}

onMounted(() => { loadRefs(); load() })
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.page-head h2 { font-size: 18px; color: #1f2d3d; }
.filter-card { margin-bottom: 12px; }
.filter-card :deep(.el-form-item) { margin-bottom: 0; }
.tip { font-size: 11px; color: #909399; }
</style>
