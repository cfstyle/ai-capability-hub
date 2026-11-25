import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import AdaptiveShell from '@/layout/AdaptiveShell.vue'

const routes: RouteRecordRaw[] = [
  // 1. 公开能力门户（面向非开发者与业务用户，完全免登录）
  {
    path: '/',
    name: 'Portal',
    component: () => import('@/views/portal/index.vue'),
    meta: { title: 'AI 能力门户', public: true },
  },
  {
    path: '/portal',
    redirect: '/',
  },

  // 2. 管理员登录
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '管理员登录', public: true },
  },

  // 3. 管理控制台（保持严格鉴权隔离）
  {
    path: '/admin',
    component: AdaptiveShell,
    redirect: '/admin/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '运行总览', icon: 'LayoutDashboard' },
      },
      {
        path: 'servers',
        name: 'Servers',
        redirect: '/admin/servers/list',
        meta: { title: 'MCP 服务', icon: 'Server' },
        children: [
          {
            path: 'list',
            name: 'ServerList',
            component: () => import('@/views/servers/list.vue'),
            meta: { title: '服务列表' },
          },
          {
            path: 'register',
            name: 'ServerRegister',
            component: () => import('@/views/servers/register.vue'),
            meta: { title: '服务注册' },
          },
          {
            path: 'publish',
            name: 'ServerPublish',
            component: () => import('@/views/servers/publish.vue'),
            meta: { title: '发布 MCP 插件' },
          },
          {
            path: ':id',
            name: 'ServerDetail',
            component: () => import('@/views/servers/detail.vue'),
            meta: { title: '服务详情', hidden: true },
          },
        ],
      },
      {
        path: 'tools',
        name: 'Tools',
        redirect: '/admin/tools/list',
        meta: { title: '工具目录', icon: 'Wrench' },
        children: [
          {
            path: 'list',
            name: 'ToolList',
            component: () => import('@/views/tools/list.vue'),
            meta: { title: '工具列表' },
          },
          {
            path: 'debug',
            name: 'ToolDebug',
            component: () => import('@/views/tools/debug.vue'),
            meta: { title: '在线调试' },
          },
        ],
      },
      {
        path: 'permissions',
        name: 'Permissions',
        component: () => import('@/views/permissions/index.vue'),
        meta: { title: '权限审批', icon: 'ShieldCheck' },
      },
      {
        path: 'audit',
        name: 'AuditLogs',
        component: () => import('@/views/audit/list.vue'),
        meta: { title: '调用审计', icon: 'ScrollText' },
      },
      {
        path: 'system',
        name: 'SystemStatus',
        component: () => import('@/views/system/index.vue'),
        meta: { title: '系统管理', icon: 'Settings' },
      },
    ],
  },

  // 4. 旧管理端路由平滑兼容重定向
  { path: '/dashboard', redirect: '/admin/dashboard' },
  { path: '/servers', redirect: '/admin/servers/list' },
  { path: '/servers/list', redirect: '/admin/servers/list' },
  { path: '/servers/register', redirect: '/admin/servers/register' },
  { path: '/servers/publish', redirect: '/admin/servers/publish' },
  { path: '/publish', redirect: '/admin/servers/publish' },
  { path: '/servers/:id', redirect: to => `/admin/servers/${to.params.id}` },
  { path: '/tools', redirect: '/admin/tools/list' },
  { path: '/tools/list', redirect: '/admin/tools/list' },
  { path: '/tools/debug', redirect: '/admin/tools/debug' },
  { path: '/audit', redirect: '/admin/audit' },
  { path: '/system', redirect: '/admin/system' },

  // 5. 兜底重定向回能力门户
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  // 公开免登页面放行
  if (to.meta.public) {
    next()
    return
  }
  // 管理后台严格鉴权拦截
  const apiKey = localStorage.getItem('hub_admin_api_key')
  if (!apiKey) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else {
    next()
  }
})

export default router
