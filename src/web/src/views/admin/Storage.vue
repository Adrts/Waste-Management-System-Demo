<template>
  <div>
    <div class="page-head">
      <h2>暂存台账（设施级库存流水）</h2>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>出入库登记</el-button>
    </div>

    <el-tabs v-model="tab">
      <el-tab-pane label="流水" name="flow">
        <el-card shadow="never" class="filter-card">
          <el-form inline>
            <el-form-item label="设施">
              <el-select v-model="filters.facility" clearable filterable placeholder="全部" style="width:220px">
                <el-option v-for="f in facilities" :key="f.facility_id" :label="f.facility_name" :value="f.facility_id" />
              </el-select>
            </el-form-item>
            <el-form-item label="类别">
              <el-select v-model="filters.category" clearable placeholder="全部" style="width:120px">
                <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
              </el-select>
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="filters.io_type" clearable placeholder="全部" style="width:100px">
                <el-option label="入库 IN" value="IN" /><el-option label="出库 OUT" value="OUT" />
              </el-select>
            </el-form-item>
            <el-form-item label="原因">
              <el-select v-model="filters.reason" clearable placeholder="全部" style="width:120px">
                <el-option label="常规 NORMAL" value="NORMAL" /><el-option label="工艺 PROCESS" value="PROCESS" /><el-option label="应急 EMERGENCY" value="EMERGENCY" />
              </el-select>
            </el-form-item>
            <el-form-item><el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button></el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never">
          <el-table :data="rows" v-loading="loading" stripe>
            <el-table-column prop="storage_id" label="流水号" width="190" />
            <el-table-column prop="facility_name" label="设施" min-width="180" show-overflow-tooltip />
            <el-table-column prop="category_name" label="类别" width="90" />
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <el-tag :type="row.io_type === 'IN' ? 'success' : 'warning'" size="small">{{ row.io_type === 'IN' ? '入库' : '出库' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数量" width="110" align="right"><template #default="{ row }">{{ row.quantity }} {{ row.unit }}</template></el-table-column>
            <el-table-column prop="batch_no" label="批次号" width="150" />
            <el-table-column label="原因" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.reason !== 'NORMAL'" :type="row.reason === 'EMERGENCY' ? 'danger' : 'info'" size="small">{{ row.reason }}</el-tag>
                <span v-else>常规</span>
              </template>
            </el-table-column>
            <el-table-column prop="related_transfer_no" label="关联流转单" width="200" />
            <el-table-column prop="io_time" label="时间" width="160" />
          </el-table>
          <el-pagination layout="total, prev, pager, next" :total="total" v-model:current-page="page"
                         v-model:page-size="size" style="margin-top:12px" @change="load" />
        </el-card>
      </el-tab-pane>
      <el-tab-pane label="当前库存（ΣIN−ΣOUT）" name="stock">
        <el-card shadow="never">
          <el-table :data="stock" v-loading="stockLoading" stripe>
            <el-table-column prop="facility_name" label="设施" min-width="180" show-overflow-tooltip />
            <el-table-column prop="category_name" label="类别" width="100" />
            <el-table-column prop="batch_no" label="批次号" width="150" />
            <el-table-column label="库存" width="120" align="right">
              <template #default="{ row }"><b>{{ row.stock }}</b> {{ row.unit }}</template>
            </el-table-column>
            <el-table-column prop="last_io_time" label="最后出入库" width="160" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="visible" title="出入库登记" width="520px">
      <el-alert v-if="err" type="error" :title="err" show-icon :closable="false" style="margin-bottom:12px" />
      <el-form :model="form" label-width="110px">
        <el-form-item label="设施" required>
          <el-select v-model="form.facility_id" filterable style="width:100%">
            <el-option v-for="f in stashFacilities" :key="f.facility_id" :label="`${f.facility_name} (${f.facility_type})`" :value="f.facility_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类别" required>
          <el-select v-model="form.category_code" style="width:100%">
            <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型" required>
          <el-radio-group v-model="form.io_type">
            <el-radio value="IN">入库 IN</el-radio><el-radio value="OUT">出库 OUT</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="form.quantity" :min="0.001" :precision="3" style="width:100%" />
          <div class="form-tip">出库后库存不可为负；建筑垃圾单位 m³</div>
        </el-form-item>
        <el-form-item label="单位"><el-input v-model="form.unit" style="width:120px" /></el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="form.batch_no" placeholder="有害垃圾必填" />
        </el-form-item>
        <el-form-item label="原因">
          <el-select v-model="form.reason" style="width:100%">
            <el-option label="常规 NORMAL" value="NORMAL" /><el-option label="工艺性 PROCESS" value="PROCESS" /><el-option label="应急 EMERGENCY" value="EMERGENCY" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联流转单">
          <el-input v-model="form.related_transfer_no" placeholder="选填，把“停下来”与“动起来”缝在一起" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">登记</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../api'

const tab = ref('flow')
const rows = ref([]); const total = ref(0); const page = ref(1); const size = ref(20)
const stock = ref([]); const stockLoading = ref(false)
const loading = ref(false); const saving = ref(false)
const categories = ref([]); const facilities = ref([])
const filters = reactive({ facility: '', category: '', io_type: '', reason: '' })
const visible = ref(false); const err = ref('')
const form = reactive({ facility_id: '', category_code: '', io_type: 'IN', quantity: 1, unit: '吨', batch_no: '', reason: 'NORMAL', related_transfer_no: '' })

const stashFacilities = computed(() => facilities.value.filter(f => ['TRANSFER', 'STORAGE', 'TERMINAL'].includes(f.facility_type)))

async function loadRefs() {
  categories.value = (await http.get('/categories')).data
  facilities.value = (await http.get('/facilities', { params: { size: 200 } })).data.items
}

async function load() {
  loading.value = true
  try {
    const res = await http.get('/storage', { params: { page: page.value, size: size.value, ...filters } })
    rows.value = res.data.items; total.value = res.data.total
  } finally { loading.value = false }
}

async function loadStock() {
  stockLoading.value = true
  try { stock.value = (await http.get('/storage/stock')).data } finally { stockLoading.value = false }
}

function openCreate() {
  err.value = ''
  Object.assign(form, { facility_id: '', category_code: '', io_type: 'IN', quantity: 1, unit: '吨', batch_no: '', reason: 'NORMAL', related_transfer_no: '' })
  visible.value = true
}

async function save() {
  saving.value = true; err.value = ''
  try {
    const res = await http.post('/storage', { ...form, batch_no: form.batch_no || null, related_transfer_no: form.related_transfer_no || null })
    ElMessage.success(res.message); visible.value = false; load(); loadStock()
  } catch (e) { err.value = e.message } finally { saving.value = false }
}

onMounted(() => { loadRefs(); load(); loadStock() })
</script>

<style scoped>
.form-tip { font-size: 11px; color: #909399; }
</style>
