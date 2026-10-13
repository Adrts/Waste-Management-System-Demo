<template>
  <div>
    <div class="page-head"><h2>消耗记录（末端实收）</h2></div>
    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="关键字">
          <el-input v-model="filters.keyword" placeholder="记录号/流转单/批次" clearable style="width:180px" @keyup.enter="load" />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="filters.category" clearable placeholder="全部" style="width:120px">
            <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="方式">
          <el-select v-model="filters.method" clearable placeholder="全部" style="width:170px">
            <el-option v-for="(label, m) in methods" :key="m" :label="label" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item><el-button type="primary" @click="load"><el-icon><Search /></el-icon>查询</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="disposal_id" label="消耗记录号" width="190" />
        <el-table-column prop="transfer_no" label="终段流转单" width="200">
          <template #default="{ row }"><el-link type="primary" @click="goTrace(row)">{{ row.transfer_no }}</el-link></template>
        </el-table-column>
        <el-table-column prop="facility_name" label="末端设施" min-width="170" show-overflow-tooltip />
        <el-table-column prop="category_name" label="类别" width="90" />
        <el-table-column label="实收重量(kg)" width="110" align="right"><template #default="{ row }">{{ row.weight_kg.toLocaleString() }}</template></el-table-column>
        <el-table-column label="消耗方式" width="140">
          <template #default="{ row }">{{ methods[row.disposal_method] || '—' }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="220">
          <template #default="{ row }">
            <el-tag v-if="row.reject_reason" type="danger" size="small">拒收：{{ row.reject_reason }}</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="consume_time" label="消耗时间" width="160" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.reject_reason" size="small" @click="edit(row)">修改</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination layout="total, prev, pager, next" :total="total" v-model:current-page="page"
                     v-model:page-size="size" style="margin-top:12px" @change="load" />
    </el-card>

    <el-dialog v-model="visible" title="修改消耗记录" width="520px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="实收重量(kg)"><el-input-number v-model="form.weight_kg" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="消耗方式">
          <el-select v-model="form.disposal_method" style="width:100%">
            <el-option v-for="(label, m) in methods" :key="m" :label="label" :value="m" />
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

const methods = { INCINERATION: '焚烧发电', ANAEROBIC: '厌氧产沼', COMPOST: '堆肥',
  DISASSEMBLE: '拆解', RECYCLE: '再生利用', HAZARD_TREAT: '危废处置' }
const rows = ref([]); const total = ref(0); const page = ref(1); const size = ref(20)
const loading = ref(false); const saving = ref(false)
const categories = ref([])
const filters = reactive({ keyword: '', category: '', method: '' })
const visible = ref(false)
const current = ref(null)
const form = reactive({ weight_kg: 0, disposal_method: '' })

async function loadRefs() { categories.value = (await http.get('/categories')).data }

async function load() {
  loading.value = true
  try {
    const res = await http.get('/disposal', { params: { page: page.value, size: size.value, ...filters } })
    rows.value = res.data.items; total.value = res.data.total
  } finally { loading.value = false }
}

function edit(row) {
  current.value = row
  form.weight_kg = row.weight_kg; form.disposal_method = row.disposal_method
  visible.value = true
}

async function save() {
  saving.value = true
  try {
    const res = await http.put(`/disposal/${current.value.disposal_id}`,
      { weight_kg: form.weight_kg, disposal_method: form.disposal_method })
    ElMessage.success(res.message); visible.value = false; load()
  } catch (e) { ElMessage.error(e.message) } finally { saving.value = false }
}

function goTrace(row) { window.open('/admin/trace?transfer_no=' + encodeURIComponent(row.transfer_no), '_blank') }

onMounted(() => { loadRefs(); load() })
</script>

<style scoped>
</style>
