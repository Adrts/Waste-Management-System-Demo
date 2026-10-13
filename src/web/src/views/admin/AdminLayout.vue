<template>
  <el-container class="admin-shell">
    <el-aside width="210px" class="aside">
      <div class="logo" @click="$router.push('/dashboard')">
        <span class="logo-mark">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <circle cx="12" cy="12" r="9" fill="none" stroke="#fff" stroke-width="2.6" />
            <circle cx="12" cy="12" r="3.4" fill="#fff" />
          </svg>
        </span>
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
        <el-menu-item index="/admin/reports"><el-icon><Histogram /></el-icon>数据汇总</el-menu-item>
        <el-menu-item index="/admin/categories"><el-icon><CollectionTag /></el-icon>垃圾类别字典</el-menu-item>
        <el-menu-item index="/admin/facilities"><el-icon><OfficeBuilding /></el-icon>设施管理</el-menu-item>
        <el-menu-item index="/admin/vehicles"><el-icon><Van /></el-icon>车辆管理</el-menu-item>
        <el-menu-item index="/admin/analysis"><el-icon><DataAnalysis /></el-icon>统计分析</el-menu-item>
      </el-menu>
      <div class="aside-foot">
        <el-button text size="small" @click="$router.push('/dashboard')">
          <el-icon><Monitor /></el-icon><span>返回展板</span>
        </el-button>
      </div>
    </el-aside>

    <el-container class="right-col" direction="vertical">
      <header class="topbar">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="topbar-right">
          <el-button text size="small" class="topbar-btn" @click="logout">
            <el-icon><SwitchButton /></el-icon><span>退出登录</span>
          </el-button>
          <div class="user-chip">
            <span class="avatar">{{ (user.name || 'A')[0] }}</span>
            <span class="uname">{{ user.name || 'admin' }}</span>
          </div>
        </div>
      </header>
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const user = JSON.parse(localStorage.getItem('wms_user') || '{}')

const TITLES = {
  transfers: '流转单管理', storage: '暂存台账', disposal: '消耗记录', trace: '追溯查询',
  reports: '数据汇总', categories: '垃圾类别字典', facilities: '设施管理',
  vehicles: '车辆管理', analysis: '统计分析'
}
const currentTitle = computed(() => TITLES[route.path.split('/')[2]] || '数据管理')

function logout() {
  localStorage.removeItem('wms_token')
  localStorage.removeItem('wms_user')
  router.push('/login')
}
</script>

<style scoped>
.admin-shell { height: 100vh; background: #f0f2f5; }

/* ---------- 深色侧边栏 ---------- */
.aside {
  display: flex; flex-direction: column;
  background: linear-gradient(180deg, #0d1b2e, #0b1526);
  color: #cfe3f5;
}
.logo { display: flex; gap: 10px; align-items: center; padding: 18px 14px 14px; cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,.08); transition: opacity .2s ease; }
.logo:hover { opacity: .85; }
.logo-mark {
  width: 34px; height: 34px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(33, 84, 216, .45);
}
.logo-t1 { font-size: 14px; font-weight: 600; color: #f2f6fc; letter-spacing: 1px; }
.logo-t2 { font-size: 10px; color: #7a92b4; letter-spacing: 1px; margin-top: 2px; }
.menu { border-right: none; flex: 1; margin-top: 8px; padding: 0 8px; }
.menu :deep(.el-menu-item) {
  color: #93a7c4; height: 44px; margin: 3px 0; border-radius: 6px;
  transition: background .2s ease, color .2s ease, padding-left .2s ease;
}
.menu :deep(.el-menu-item:hover) { background: rgba(255,255,255,.07); color: #fff; }
.menu :deep(.el-menu-item.is-active) {
  color: #fff; background: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(33, 84, 216, .4);
}
.aside-foot { padding: 10px 14px; border-top: 1px solid rgba(255,255,255,.08); }
.aside-foot .el-button {
  color: #7a92b4; width: 100%; margin: 0;
  display: flex; align-items: center; justify-content: flex-start; gap: 8px;
  padding: 6px 8px; line-height: 1;
}
.aside-foot .el-button + .el-button { margin-left: 0; }
.aside-foot .el-icon { font-size: 15px; flex: none; }
.aside-foot .el-button:hover { color: #fff; }

/* ---------- 顶栏 ---------- */
.right-col { min-width: 0; }
.topbar {
  height: 52px; flex: none;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 18px; background: #fff;
  border-bottom: 1px solid #e8edf5;
  box-shadow: 0 1px 6px rgba(15, 34, 67, .04);
  position: relative; z-index: 5;
}
.topbar-right { display: flex; align-items: center; gap: 12px; }
.topbar-btn { color: #6b7a90; }
.topbar-btn:hover { color: var(--el-color-primary); }
.user-chip { display: flex; align-items: center; gap: 8px; padding: 4px 10px 4px 4px;
  border-radius: 999px; background: #f4f6fa; transition: background .2s ease; cursor: default; }
.user-chip:hover { background: #ecf0fb; }
.avatar {
  width: 28px; height: 28px; border-radius: 50%; flex: none;
  display: flex; align-items: center; justify-content: center;
  background: var(--el-color-primary); color: #fff; font-size: 13px;
}
.uname { font-size: 13px; color: #1f2d3d; }

.main { padding: 14px 18px; overflow: auto; background: #f0f2f5; }
</style>
