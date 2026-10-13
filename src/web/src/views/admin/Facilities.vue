<template>
  <div>
    <div class="page-head">
      <h2>设施管理（全链节点：产生源/投放点/收集点/转运站/暂存点/末端）</h2>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增设施</el-button>
    </div>
    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="类型">
          <el-select v-model="filters.type" clearable placeholder="全部" style="width:150px">
            <el-option v-for="(label, v) in types" :key="v" :label="label" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width:130px">
            <el-option label="运行 RUNNING" value="RUNNING" /><el-option label="在建 BUILDING" value="BUILDING" /><el-option label="关停 SHUTDOWN" value="SHUTDOWN" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字"><el-input v-model="filters.keyword" clearable style="width:180px" @keyup.enter="load" /></el-form-item>
        <el-form-item><el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" stripe size="default">
        <el-table-column prop="facility_id" label="编码" width="120" />
        <el-table-column prop="facility_name" label="名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="100"><template #default="{ row }">{{ types[row.facility_type] }}</template></el-table-column>
        <el-table-column label="区划" width="80"><template #default="{ row }">{{ regions[row.region_code] || row.region_code }}</template></el-table-column>
        <el-table-column prop="capacity_ton_day" label="能力(t/d)" width="90" align="right" />
        <el-table-column prop="operator" label="运营方" min-width="150" show-overflow-tooltip />
        <el-table-column prop="transfer_count" label="关联单量" width="90" align="right" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'RUNNING' ? 'success' : row.status === 'BUILDING' ? 'info' : 'danger'" size="small">
              {{ { RUNNING: '运行', BUILDING: '在建', SHUTDOWN: '关停' }[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="edit(row)">编辑</el-button>
            <el-button v-if="row.status === 'RUNNING'" size="small" type="warning" plain @click="shutdown(row)">关停</el-button>
            <el-button v-if="row.status === 'SHUTDOWN'" size="small" type="success" plain @click="reopen(row)">恢复</el-button>
            <el-button size="small" type="danger" plain :disabled="row.transfer_count > 0" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination layout="total, prev, pager, next" :total="total" v-model:current-page="page"
                     v-model:page-size="size" style="margin-top:12px" @change="load" />
    </el-card>

    <el-dialog v-model="visible" :title="isEdit ? '编辑设施' : '新增设施'" width="600px">
      <el-alert v-if="err" type="error" :title="err" show-icon :closable="false" style="margin-bottom:12px" />
      <el-form :model="form" label-width="110px">
        <el-form-item label="设施编码" required><el-input v-model="form.facility_id" :disabled="isEdit" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="form.facility_name" /></el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.facility_type" style="width:100%">
            <el-option v-for="(label, v) in types" :key="v" :label="label" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="区划">
          <el-select v-model="form.region_code" style="width:100%">
            <el-option v-for="(label, v) in regions" :key="v" :label="label" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="地址"><el-input v-model="form.address" /></el-form-item>
        <el-form-item label="经度" required><el-input-number v-model="form.longitude" :precision="5" :step="0.001" style="width:100%" /></el-form-item>
        <el-form-item label="纬度" required><el-input-number v-model="form.latitude" :precision="5" :step="0.001" style="width:100%" /></el-form-item>
        <el-form-item label="能力(t/d)"><el-input-number v-model="form.capacity_ton_day" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="运营方"><el-input v-model="form.operator" /></el-form-item>
        <el-form-item label="专属属性"><el-input v-model="form.type_attrs" type="textarea" :rows="2" placeholder='JSON，如 {"限收品类":["HAZARD"]}' /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="运行 RUNNING" value="RUNNING" /><el-option label="在建 BUILDING" value="BUILDING" /><el-option label="关停 SHUTDOWN" value="SHUTDOWN" />
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

const types = { SOURCE: '产生源', DROP: '投放点', COLLECT: '收集点', TRANSFER: '转运站', STORAGE: '暂存点', TERMINAL: '末端设施' }
const regions = { '460105': '秀英区', '460106': '龙华区', '460107': '琼山区', '460108': '美兰区', '469023': '澄迈县', '469005': '文昌市' }
const rows = ref([]); const total = ref(0); const page = ref(1); const size = ref(20)
const loading = ref(false); const saving = ref(false)
const filters = reactive({ type: '', status: '', keyword: '' })
const visible = ref(false); const err = ref(''); const isEdit = ref(false)
const form = reactive({ facility_id: '', facility_name: '', facility_type: 'DROP', region_code: '460105', address: '', longitude: 110.3, latitude: 20.0, capacity_ton_day: 0, operator: '', type_attrs: '{}', status: 'RUNNING' })

async function load() {
  loading.value = true
  try {
    const res = await http.get('/facilities', { params: { page: page.value, size: size.value, ...filters } })
    rows.value = res.data.items; total.value = res.data.total
  } finally { loading.value = false }
}

function openCreate() {
  err.value = ''; isEdit.value = false
  Object.assign(form, { facility_id: '', facility_name: '', facility_type: 'DROP', region_code: '460105', address: '', longitude: 110.3, latitude: 20.0, capacity_ton_day: 0, operator: '', type_attrs: '{}', status: 'RUNNING' })
  visible.value = true
}

function edit(row) {
  err.value = ''; isEdit.value = true
  Object.assign(form, { ...row, type_attrs: typeof row.type_attrs === 'string' ? row.type_attrs : JSON.stringify(row.type_attrs || {}) })
  visible.value = true
}

async function save() {
  saving.value = true; err.value = ''
  try {
    const body = { ...form }
    if (typeof body.type_attrs === 'string' && body.type_attrs.trim()) JSON.parse(body.type_attrs)
    const res = isEdit.value ? await http.put(`/facilities/${encodeURIComponent(form.facility_id)}`, body)
      : await http.post('/facilities', body)
    ElMessage.success(res.message); visible.value = false; load()
  } catch (e) { err.value = e.message.includes('JSON') ? '专属属性不是合法 JSON' : e.message } finally { saving.value = false }
}

async function shutdown(row) {
  await ElMessage.confirm(`确认关停【${row.facility_name}】？关停后新建流转单指向该设施将被拒绝（F-8）。`, '关停设施', { type: 'warning' })
  await http.put(`/facilities/${encodeURIComponent(row.facility_id)}`, { ...row, status: 'SHUTDOWN' })
  ElMessage.success('已关停'); load()
}

async function reopen(row) {
  await http.put(`/facilities/${encodeURIComponent(row.facility_id)}`, { ...row, status: 'RUNNING' })
  ElMessage.success('已恢复运行'); load()
}

async function del(row) {
  await ElMessage.confirm(`确认删除 ${row.facility_name}？`, '删除', { type: 'warning' })
  const res = await http.delete(`/facilities/${encodeURIComponent(row.facility_id)}`)
  ElMessage.success(res.message); load()
}

onMounted(load)
</script>

<style scoped>
</style>
