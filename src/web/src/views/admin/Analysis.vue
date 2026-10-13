<template>
  <div>
    <div class="page-head"><h2>统计分析模块</h2></div>
    <el-card shadow="never">
      <el-result icon="info" title="建设中" sub-title="统计分析模块按项目计划暂缓实现，数据层与接口已预留">
        <template #extra>
          <div class="plan">
            <h4>规划能力（对应验收指标 A-1 ~ A-7）</h4>
            <ul>
              <li>描述性统计：按类别/区域/日的产生量、清运量、处置量、单车装载率、设施负荷率、运力利用率</li>
              <li>多元回归：分品类日清运量 ~ 经济指标 + 节日哑变量 + 台风临近指数（R² ≥ 0.6）</li>
              <li>时间序列预测：SARIMA / Holt-Winters 双模型滚动回测（7 天 MAPE ≤ 15%）</li>
              <li>马尔可夫链：改道/路径状态转移矩阵与稳态分布</li>
              <li>主成分分析：≥8 变量降维（累计方差 ≥ 80%，KMO ≥ 0.6）</li>
              <li>运力储备建议：预测日清运量 ÷ 单车日均有效运能 × 峰值系数 → 未来 7/30 天建议车辆数</li>
            </ul>
            <p class="note">数据基础已就绪：模拟数据已预埋春节 +30%、台风 +50%、周末 +10% 规律（见 data/meta.json 规律清单），可直接用于模型验证。</p>
          </div>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<style scoped>
.plan { text-align: left; max-width: 620px; }
.plan h4 { margin-bottom: 8px; }
.plan li { margin: 6px 0; color: #606266; font-size: 13px; }
.note { margin-top: 12px; font-size: 12px; color: #909399; }
</style>
