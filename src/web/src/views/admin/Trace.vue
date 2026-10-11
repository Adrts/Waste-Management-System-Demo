<template>
  <div>
    <div class="page-head"><h2>追溯查询（F-7：按单号/批次/设施/类别/时间段还原全旅程）</h2></div>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="流转单号"><el-input v-model="q.transfer_no" placeholder="HK-..." clearable style="width:200px" @keyup.enter="search" /></el-form-item>
        <el-form-item label="批次号"><el-input v-model="q.batch_no" placeholder="HZ-...（有害垃圾全旅程）" clearable style="width:200px" @keyup.enter="search" /></el-form-item>
        <el-form-item label="或按条件">
          <el-select v-model="q.facility_id" clearable filterable placeholder="设施" style="width:190px">
            <el-option v-for="f in facilities" :key="f.facility_id" :label="f.facility_name" :value="f.facility_id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="q.category_code" clearable placeholder="类别" style="width:120px">
            <el-option v-for="c in categories" :key="c.category_code" :label="c.category_name" :value="c.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width:230px" />
        </el-form-item>
        <el-form-item><el-button type="primary" @click="search"><el-icon><Search /></el-icon>追溯</el-button></el-form-item>
      </el-form>
    </el-card>

    <!-- 批次/单号旅程 -->
    <el-card v-if="mode === 'journey'" shadow="never">
      <el-alert :title="`共 ${data.legs.length} 段流转 · ${data.storages.length} 条暂存流水 · ${data.disposals.length} 条消耗记录`"
                type="success" show-icon :closable="false" style="margin-bottom:14px" />
      <el-row :gutter="16">
        <el-col :span="13">
          <h4>全旅程时间线</h4>
          <el-timeline style="max-height:520px; overflow:auto; padding-left:4px">
            <el-timeline-item v-for="(t, i) in data.timeline" :key="i" :timestamp="t.time"
              :type="t.event.includes('消耗') ? 'success' : t.event.includes('拒收') ? 'danger' : t.event.includes('到达') ? 'warning' : 'primary'">
              <b>{{ t.event }}</b> · {{ t.facility }}
              <div class="tl-detail">{{ t.detail }}</div>
            </el-timeline-item>
          </el-timeline>
        </el-col>
        <el-col :span="11">
          <h4>流转段明细</h4>
          <el-table :data="data.legs" size="small" border style="margin-bottom:14px">
            <el-table-column prop="transfer_no" label="单号" width="190" />
            <el-table-column prop="leg_seq" label="段" width="42" />
            <el-table-column prop="from_name" label="起点" min-width="120" show-overflow-tooltip />
            <el-table-column prop="to_name" label="终点" min-width="120" show-overflow-tooltip />
            <el-table-column prop="weight_kg" label="kg" width="80" align="right" />
            <el-table-column prop="status" label="状态" width="90" />
          </el-table>
          <h4>暂存流水</h4>
          <el-table :data="data.storages" size="small" border style="margin-bottom:14px">
            <el-table-column prop="storage_id" label="流水号" width="180" />
            <el-table-column prop="facility_name" label="设施" min-width="130" show-overflow-tooltip />
            <el-table-column label="类型" width="60"><template #default="{ row }">{{ row.io_type }}</template></el-table-column>
            <el-table-column label="数量" width="90" align="right"><template #default="{ row }">{{ row.quantity }}{{ row.unit }}</template></el-table-column>
            <el-table-column prop="io_time" label="时间" width="150" />
          </el-table>
          <h4>消耗记录</h4>
          <el-table :data="data.disposals" size="small" border>
            <el-table-column prop="disposal_id" label="记录号" width="180" />
            <el-table-column prop="facility_name" label="设施" min-width="130" show-overflow-tooltip />
            <el-table-column prop="weight_kg" label="kg" width="90" align="right" />
            <el-table-column prop="disposal_method" label="方式" width="120" />
            <el-table-column prop="reject_reason" label="拒收原因" min-width="110" />
          </el-table>
        </el-col>
      </el-row>
    </el-card>

    <!-- 条件列表 -->
    <el-card v-if="mode === 'list'" shadow="never">
      <el-table :data="listRows" size="default" stripe>
        <el-table-column prop="transfer_no" label="单号" width="210">
          <template #default="{ row }"><el-link type="primary" @click="searchOne(row.transfer_no)">{{ row.transfer_no }}</el-link></template>
        </el-table-column>
        <el-table-column prop="category_name" label="类别" width="90" />
        <el-table-column prop="weight_kg" label="kg" width="90" align="right" />
        <el-table-column prop="from_name" label="起点" min-width="150" show-overflow-tooltip />
        <el-table-column prop="to_name" label="终点" min-width="150" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="loaded_time" label="装运时间" width="160" />
      </el-table>
      <el-alert v-if="!listRows.length" title="无匹配单据" type="info" :closable="false" style="margin-top:10px" />
    </el-card>

    <el-empty v-if="!mode" description="输入流转单号 / 批次号，或组合设施+类别+时间段进行追溯" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../../api'

const route = useRoute()
const mode = ref('')
const data = ref({ legs: [], storages: [], disposals: [], timeline: [] })
const listRows = ref([])
const categories = ref([]); const facilities = ref([])
const q = reactive({ transfer_no: '', batch_no: '', facility_id: '', category_code: '' })
const range = ref(null)

async function search() {
  const params = { ...q }
  if (range.value) { params.start = range.value[0]; params.end = range.value[1] }
  if (!params.transfer_no && !params.batch_no && !params.facility_id && !params.category_code && !params.start) {
    return ElMessage.warning('请输入追溯条件')
  }
  try {
    const res = await http.get('/trace', { params })
    if (res.data.mode === 'list') { mode.value = 'list'; listRows.value = res.data.legs }
    else { mode.value = 'journey'; data.value = res.data }
  } catch (e) { ElMessage.error(e.message) }
}

async function searchOne(no) {
  q.transfer_no = no
  mode.value = ''
  await search()
}

onMounted(async () => {
  categories.value = (await http.get('/categories')).data
  facilities.value = (await http.get('/facilities', { params: { size: 200 } })).data.items
  if (route.query.transfer_no) { q.transfer_no = route.query.transfer_no; search() }
  else if (route.query.batch_no) { q.batch_no = route.query.batch_no; search() }
})
</script>

<style scoped>
.page-head { margin-bottom: 12px; }
.page-head h2 { font-size: 18px; color: #1f2d3d; }
.filter-card { margin-bottom: 12px; }
.filter-card :deep(.el-form-item) { margin-bottom: 0; }
.tl-detail { font-size: 12px; color: #606266; }
h4 { margin: 6px 0 8px; color: #303133; }
</style>
