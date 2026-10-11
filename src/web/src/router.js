import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue') },
  { path: '/dashboard', component: () => import('./views/Dashboard.vue') },
  {
    path: '/admin',
    component: () => import('./views/admin/AdminLayout.vue'),
    redirect: '/admin/transfers',
    children: [
      { path: 'transfers', component: () => import('./views/admin/Transfers.vue') },
      { path: 'storage', component: () => import('./views/admin/Storage.vue') },
      { path: 'disposal', component: () => import('./views/admin/Disposal.vue') },
      { path: 'trace', component: () => import('./views/admin/Trace.vue') },
      { path: 'categories', component: () => import('./views/admin/Categories.vue') },
      { path: 'facilities', component: () => import('./views/admin/Facilities.vue') },
      { path: 'vehicles', component: () => import('./views/admin/Vehicles.vue') },
      { path: 'analysis', component: () => import('./views/admin/Analysis.vue') }
    ]
  },
  { path: '/', redirect: '/dashboard' },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(to => {
  if (to.path !== '/login' && !localStorage.getItem('wms_token')) return '/login'
})

export default router
