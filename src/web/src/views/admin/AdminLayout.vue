<template>
  <el-container class="admin-shell">
    <el-aside width="200px" class="aside">
      <div class="logo" @click="$router.push('/dashboard')">
        <span class="logo-mark">⬡</span>
        <div>
          <div class="logo-t1">垃圾全生命周期</div>
          <div class="logo-t2">数据管理 · DEMO</div>
        </div>
      </div>
      <el-menu :default-active="$route.path" router class="menu" background-color="transparent">
        <el-menu-item index="/admin/transfers"><el-icon><Tickets /></el-icon>流转单管理</el-menu-item>
        <el-menu-item index="/admin/storage"><el-icon><Box /></el-icon>暂存台账</el-menu-item>
        <el-menu-item index="/admin/disposal"><el-icon><CircleCheck /></el-icon>消耗记录</el-menu-item>
        <el-menu-item index="/admin/trace"><el-icon><Search /></el-icon>追溯查询</el-menu-item>
        <el-menu-item index="/admin/categories"><el-icon><CollectionTag /></el-icon>垃圾类别字典</el-menu-item>
        <el-menu-item index="/admin/facilities"><el-icon><OfficeBuilding /></el-icon>设施管理</el-menu-item>
        <el-menu-item index="/admin/vehicles"><el-icon><Van /></el-icon>车辆管理</el-menu-item>
        <el-menu-item index="/admin/analysis"><el-icon><DataAnalysis /></el-icon>统计分析</el-menu-item>
      </el-menu>
      <div class="aside-foot">
        <el-button text size="small" @click="$router.push('/dashboard')">
          <el-icon><Monitor /></el-icon><span>返回展板</span>
        </el-button>
        <el-button text size="small" @click="logout">
          <el-icon><SwitchButton /></el-icon><span>退出登录</span>
        </el-button>
      </div>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
function logout() {
  localStorage.removeItem('wms_token')
  router.push('/login')
}
</script>

<style scoped>
.admin-shell { height: 100vh; background: #f3f6fa; }
.aside {
  display: flex; flex-direction: column;
  background: linear-gradient(180deg, #10304d, #0b2238);
  color: #cfe3f5;
}
.logo { display: flex; gap: 10px; align-items: center; padding: 18px 14px 14px; cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,.08); }
.logo-mark { font-size: 26px; color: #35e2d4; }
.logo-t1 { font-size: 14px; font-weight: 600; color: #eaf4fd; }
.logo-t2 { font-size: 10px; color: #7fa6c4; letter-spacing: 1px; }
.menu { border-right: none; flex: 1; margin-top: 8px; }
.menu :deep(.el-menu-item) { color: #a9c4da; height: 44px; }
.menu :deep(.el-menu-item.is-active) { color: #35e2d4; background: rgba(53,226,212,.12); border-right: 3px solid #35e2d4; }
.menu :deep(.el-menu-item:hover) { background: rgba(255,255,255,.06); }
.aside-foot { padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; border-top: 1px solid rgba(255,255,255,.08); }
.aside-foot .el-button {
  color: #7fa6c4; width: 100%; margin: 0;
  display: flex; align-items: center; justify-content: flex-start; gap: 8px;
  padding: 6px 8px; line-height: 1;
}
.aside-foot .el-button + .el-button { margin-left: 0; }
.aside-foot .el-icon { font-size: 15px; flex: none; }
.aside-foot .el-button:hover { color: #35e2d4; }
.main { padding: 14px 18px; overflow: auto; background: #f3f6fa; }
</style>
