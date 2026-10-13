<template>
  <div class="login-page">
    <!-- 左侧蓝色面板（曲线右缘） -->
    <div class="pane-left">
      <!-- 白色 S 曲线仅覆盖面板右缘，蓝底为实色渐变，内容永不跨界 -->
      <svg class="curve" viewBox="0 0 120 100" preserveAspectRatio="none" aria-hidden="true">
        <path fill="#fff"
              d="M78,0 H120 V100 H62 C74,90 78,78 72,64 C66,50 54,46 56,32 C58,18 68,10 78,0 Z" />
      </svg>

      <div class="org">
        <span class="org-logo">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <circle cx="12" cy="12" r="9" fill="none" stroke="#fff" stroke-width="2.6" />
            <circle cx="12" cy="12" r="3.4" fill="#fff" />
          </svg>
        </span>
        <span>海口市城市管理局</span>
      </div>

      <div class="hero">
        <div class="hero-art" aria-hidden="true">
          <svg viewBox="0 0 200 200" width="78%" height="78%">
            <!-- 循环箭头 -->
            <g fill="none" stroke="rgba(255,255,255,.9)" stroke-width="7" stroke-linecap="round">
              <path d="M100 30 A70 70 0 0 1 168 92" />
              <path d="M170 108 A70 70 0 0 1 104 170" />
              <path d="M86 169 A70 70 0 0 1 31 96" />
            </g>
            <g fill="rgba(255,255,255,.9)">
              <path d="M100 30 l16 -9 l-2 19 Z" />
              <path d="M170 108 l10 15 l-19 1 Z" />
              <path d="M86 169 l-18 6 l7 -18 Z" />
            </g>
            <!-- 垃圾车 -->
            <g>
              <rect x="66" y="92" width="52" height="30" rx="4" fill="#fff" />
              <rect x="118" y="102" width="20" height="20" rx="3" fill="#e8f0ff" />
              <rect x="121" y="105" width="12" height="9" rx="1.5" fill="#2154d8" />
              <circle cx="82" cy="128" r="9" fill="#0e2a6e" />
              <circle cx="82" cy="128" r="4" fill="#cfe0ff" />
              <circle cx="128" cy="128" r="9" fill="#0e2a6e" />
              <circle cx="128" cy="128" r="4" fill="#cfe0ff" />
              <rect x="74" y="82" width="14" height="8" rx="2" fill="#ffd257" />
            </g>
            <!-- 分类桶 -->
            <g>
              <rect x="42" y="118" width="18" height="24" rx="3" fill="#59d08f" />
              <rect x="140" y="118" width="18" height="24" rx="3" fill="#7fb3ff" />
              <rect x="39" y="112" width="24" height="5" rx="2" fill="#3fae70" />
              <rect x="137" y="112" width="24" height="5" rx="2" fill="#5a8fe0" />
            </g>
          </svg>
        </div>
        <h1>海口市垃圾全生命周期管理系统</h1>
        <p>输入账号密码登录后开始使用！</p>
      </div>

      <i class="bubble b1"></i><i class="bubble b2"></i><i class="bubble b3"></i><i class="bubble b4"></i>
    </div>

    <!-- 右侧登录表单 -->
    <div class="pane-right">
      <div class="login-box">
        <h2 class="login-title fade-up">登录</h2>
        <el-form class="fade-up d1" @keyup.enter="doLogin">
          <el-form-item>
            <el-input v-model="form.username" placeholder="账号（演示：admin）" size="large"
                      autocomplete="username">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" show-password
                      placeholder="密码（演示：haikou123）" size="large"
                      autocomplete="current-password">
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="doLogin">
            登 录
          </el-button>
        </el-form>
        <div class="demo-chip fade-up d2">演示账号：admin · 密码：haikou123</div>
        <div class="foot fade-up d3">演示环境 · 单角色演示级登录 · 数据为缩比模拟数据</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../api'

const router = useRouter()
const form = reactive({ username: 'admin', password: '' })
const loading = ref(false)

async function doLogin() {
  if (!form.username || !form.password) return ElMessage.warning('请输入账号和密码')
  loading.value = true
  try {
    const res = await http.post('/auth/login', form)
    localStorage.setItem('wms_token', res.data.token)
    localStorage.setItem('wms_user', JSON.stringify(res.data.user))
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { height: 100vh; display: flex; overflow: hidden; background: #fff; }

/* ---------- 左侧蓝色面板 ---------- */
.pane-left {
  position: relative; flex: 1 1 58%; min-width: 0;
  background: linear-gradient(155deg, #1e46b8 0%, #2154d8 55%, #2f6ae4 100%);
}
.curve {
  position: absolute; top: 0; right: 0; height: 100%;
  width: clamp(110px, 16vw, 220px);
  display: block; pointer-events: none;
}

.org {
  position: relative; z-index: 2;
  display: flex; align-items: center; gap: 10px;
  padding: 26px 40px 0;
  padding-right: clamp(56px, 7.5vw, 104px);
  color: #fff; font-size: 16px; font-weight: 600; letter-spacing: 2px;
  white-space: nowrap;
  animation: fadeUp .6s ease both;
}
.org-logo {
  width: 34px; height: 34px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, .16);
  border: 1px solid rgba(255, 255, 255, .35);
}

.hero {
  position: relative; z-index: 2;
  padding: 9vh clamp(64px, 9vw, 126px) 0 12%;
  max-width: 640px;
}
.hero-art {
  width: min(240px, 72%); aspect-ratio: 1; height: auto; margin-bottom: 34px;
  border-radius: 18px;
  background: linear-gradient(155deg, rgba(255, 255, 255, .16), rgba(255, 255, 255, .06));
  border: 1px solid rgba(255, 255, 255, .28);
  box-shadow: 0 18px 46px rgba(10, 28, 90, .35);
  display: flex; align-items: center; justify-content: center;
  animation: heroFloat 6s ease-in-out infinite;
}
.hero h1 {
  font-size: 26px; color: #fff; letter-spacing: 3px; font-weight: 700;
  animation: fadeUp .7s .15s ease both;
}
.hero p {
  margin-top: 12px; font-size: 14px; color: rgba(255, 255, 255, .78); letter-spacing: 1px;
  animation: fadeUp .7s .28s ease both;
}

/* 漂浮气泡（纯 CSS，低开销） */
.bubble {
  position: absolute; z-index: 1; border-radius: 50%;
  background: rgba(255, 255, 255, .10);
  pointer-events: none;
}
.b1 { width: 130px; height: 130px; left: 8%; bottom: 12%; animation: floatY 9s ease-in-out infinite alternate; }
.b2 { width: 56px; height: 56px; left: 38%; top: 14%; animation: floatY 7s 1s ease-in-out infinite alternate; }
.b3 { width: 90px; height: 90px; left: 52%; bottom: 6%; animation: floatY 11s .5s ease-in-out infinite alternate; }
.b4 { width: 30px; height: 30px; left: 26%; top: 42%; animation: floatY 6s 2s ease-in-out infinite alternate; }

/* ---------- 右侧表单 ---------- */
.pane-right {
  flex: 1 1 42%; min-width: 0;
  display: flex; align-items: center; justify-content: center;
  background: #fff; position: relative;
}
.login-box { width: 340px; padding-bottom: 6vh; }
.login-title { font-size: 26px; font-weight: 700; color: #1f2d3d; letter-spacing: 4px; margin-bottom: 28px; }
.login-btn {
  width: 100%; margin-top: 6px; letter-spacing: 8px;
  box-shadow: 0 8px 18px rgba(33, 84, 216, .28);
  transition: transform .2s ease, box-shadow .2s ease;
}
.login-btn:hover { transform: translateY(-2px); box-shadow: 0 12px 24px rgba(33, 84, 216, .36); }
.login-btn:active { transform: none; }
.demo-chip {
  margin-top: 22px; text-align: center; font-size: 12px; color: #2154d8;
  background: #ecf0fb; border: 1px dashed #c2cdf2; border-radius: 999px; padding: 7px 10px;
}
.foot { margin-top: 18px; text-align: center; font-size: 12px; color: #6b7a90; }

/* 动画延迟工具 */
.d1 { animation-delay: .12s; }
.d2 { animation-delay: .24s; }
.d3 { animation-delay: .36s; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: none; }
}
@keyframes floatY {
  from { transform: translateY(-12px); }
  to { transform: translateY(12px); }
}
@keyframes heroFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

@media (max-width: 860px) {
  .pane-left { display: none; }
}
</style>
