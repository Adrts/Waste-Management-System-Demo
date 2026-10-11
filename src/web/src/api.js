import axios from 'axios'
import router from './router'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

http.interceptors.request.use(cfg => {
  const token = localStorage.getItem('wms_token')
  if (token) cfg.headers['X-Auth-Token'] = token
  return cfg
})

http.interceptors.response.use(
  res => {
    if (res.data && res.data.code === 401) {
      localStorage.removeItem('wms_token')
      router.push('/login')
      return Promise.reject(new Error('未登录'))
    }
    return res.data
  },
  err => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('wms_token')
      router.push('/login')
      return Promise.reject(new Error('未登录'))
    }
    const msg = err.response?.data?.detail || err.response?.data?.message || err.message
    return Promise.reject(new Error(msg))
  }
)

export default http
