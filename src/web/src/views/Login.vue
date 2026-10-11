<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <div class="logo">⬡</div>
        <h1>海口市垃圾全生命周期管理系统</h1>
        <p>Waste Full-Lifecycle Management System · DEMO</p>
      </div>
      <el-form @keyup.enter="doLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名（演示：admin）" size="large">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" show-password
                    placeholder="密码（演示：haikou123）" size="large">
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="doLogin">
          登 录
        </el-button>
      </el-form>
      <div class="tips">单角色演示级登录 · 数据为缩比模拟数据</div>
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
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
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
.login-wrap {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background:
    radial-gradient(1000px 500px at 20% 0%, rgba(34,211,238,.12), transparent 60%),
    radial-gradient(900px 500px at 90% 100%, rgba(16,185,129,.10), transparent 55%),
    linear-gradient(160deg, #0a1424, #0b1526 60%, #081120);
}
.login-card {
  width: 400px; padding: 44px 40px 30px; border-radius: 14px;
  background: rgba(14, 30, 50, .8); border: 1px solid rgba(56,116,163,.45);
  box-shadow: 0 20px 60px rgba(0,0,0,.45);
}
.brand { text-align: center; margin-bottom: 26px; }
.logo {
  width: 56px; height: 56px; margin: 0 auto 12px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center; font-size: 30px; color: #35e2d4;
  background: linear-gradient(145deg, rgba(53,226,212,.15), rgba(47,125,246,.15));
  border: 1px solid rgba(53,226,212,.4);
}
.brand h1 { font-size: 19px; color: #e8f4fd; letter-spacing: 1px; }
.brand p { font-size: 11px; color: #6b8ba6; margin-top: 6px; letter-spacing: 1px; }
.login-btn { width: 100%; margin-top: 6px; letter-spacing: 6px; }
.tips { text-align: center; margin-top: 18px; font-size: 12px; color: #5c7a94; }
</style>
