<template>
  <div>
    <div class="page-head">
      <h2>垃圾类别字典</h2>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增类别</el-button>
    </div>
    <el-card shadow="never">
      <el-alert type="info" :closable="false" style="margin-bottom:12px"
                title="编码一经使用不可改名/不可复用（历史单据都挂在旧编码上）；默认路径不强制，实际改道记录在流转单 reclass_from" />
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="category_code" label="类别码" width="140" />
        <el-table-column prop="category_name" label="名称" width="140" />
        <el-table-column label="默认路径" min-width="160">
          <template #default="{ row }">{{ routes[row.default_route] || row.default_route || '—' }}</template>
        </el-table-column>
        <el-table-column label="市场化回收线" width="120">
          <template #default="{ row }"><el-tag v-if="row.is_market_line" type="success" size="small">是</el-tag><span v-else>否</span></template>
        </el-table-column>
        <el-table-column prop="transfer_count" label="关联流转单" width="110" align="right" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="edit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain :disabled="row.transfer_count > 0" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="visible" :title="isEdit ? '编辑类别' : '新增类别'" width="480px">
      <el-alert v-if="err" type="error" :title="err" show-icon :closable="false" style="margin-bottom:12px" />
      <el-form :model="form" label-width="110px">
        <el-form-item label="类别码" required>
          <el-input v-model="form.category_code" :disabled="isEdit && form.transfer_count > 0" placeholder="如 OTHER / KN_HOME" />
          <div class="tip">大写下划线格式，编码不可复用</div>
        </el-form-item>
        <el-form-item label="名称" required><el-input v-model="form.category_name" /></el-form-item>
        <el-form-item label="默认路径">
          <el-select v-model="form.default_route" style="width:100%">
            <el-option v-for="(label, v) in routes" :key="v" :label="label" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="市场化回收线"><el-switch v-model="form.is_market_line" /></el-form-item>
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

const routes = { INCINERATION: '焚烧', KITCHEN_PLANT: '厨余/餐厨厂', HAZARD_TREAT: '危废暂存→处置',
  MARKET_RECYCLE: '市场化回收', BULK_DISASSEMBLE: '大件拆解', CONSTR_RECYCLE: '建筑资源化',
  COMPOST: '堆肥', FECAL_TREAT: '粪便无害化' }
const rows = ref([]); const loading = ref(false); const saving = ref(false)
const visible = ref(false); const err = ref(''); const isEdit = ref(false)
const form = reactive({ category_code: '', category_name: '', default_route: '', is_market_line: false, transfer_count: 0 })

async function load() {
  loading.value = true
  try { rows.value = (await http.get('/categories')).data } finally { loading.value = false }
}

function openCreate() {
  err.value = ''; isEdit.value = false
  Object.assign(form, { category_code: '', category_name: '', default_route: '', is_market_line: false, transfer_count: 0 })
  visible.value = true
}

function edit(row) {
  err.value = ''; isEdit.value = true
  Object.assign(form, row); visible.value = true
}

async function save() {
  saving.value = true; err.value = ''
  try {
    const body = { ...form, is_market_line: !!form.is_market_line }
    const res = isEdit.value ? await http.put(`/categories/${encodeURIComponent(body.category_code)}`, body)
      : await http.post('/categories', body)
    ElMessage.success(res.message); visible.value = false; load()
  } catch (e) { err.value = e.message } finally { saving.value = false }
}

async function del(row) {
  await ElMessage.confirm(`确认删除类别 ${row.category_name}？`)
  await http.delete(`/categories/${encodeURIComponent(row.category_code)}`)
  ElMessage.success('已删除'); load()
}

onMounted(load)
</script>

<style scoped>
.tip { font-size: 11px; color: #909399; }
</style>
