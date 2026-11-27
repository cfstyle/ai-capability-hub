import axios, { AxiosError, InternalAxiosRequestConfig, AxiosRequestConfig } from 'axios'
import { useToast } from '@/composables/useToast'

const toast = useToast()

export interface CustomRequestConfig extends AxiosRequestConfig {
  silent?: boolean
}

interface CustomInternalRequestConfig extends InternalAxiosRequestConfig {
  silent?: boolean
}

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const instance = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

function isEmbeddedMode(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const params = new URLSearchParams(window.location.search)
    return params.get('embed') === '1' || window.self !== window.top
  } catch {
    return false
  }
}

function isAdminRequestContext(url?: string): boolean {
  const path = typeof window !== 'undefined' ? window.location.pathname : ''
  if (path.includes('/admin')) {
    return true
  }
  const reqUrl = (url || '').trim()
  return (
    reqUrl.startsWith('/admin') ||
    reqUrl.startsWith('/services') ||
    reqUrl.startsWith('/servers') ||
    reqUrl.startsWith('/tools') ||
    reqUrl.startsWith('/audit-logs') ||
    reqUrl.startsWith('/dashboard') ||
    reqUrl.startsWith('/system') ||
    reqUrl.startsWith('/plugins')
  )
}

// Request Interceptor: 严格区分管理端与员工门户上下文，防止 Token 串用
instance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const adminCtx = isAdminRequestContext(config.url)
    if (adminCtx) {
      const rgoneAdminToken = localStorage.getItem('rgone_admin_token')
      const apiKey = localStorage.getItem('hub_admin_api_key')
      if (rgoneAdminToken) {
        config.headers['Authorization'] = `Bearer ${rgoneAdminToken}`
      } else if (apiKey) {
        config.headers['X-API-Key'] = apiKey
        config.headers['Authorization'] = `Bearer ${apiKey}`
      }
    } else {
      const rgoneEmpToken = localStorage.getItem('rgone_emp_token')
      const portalToken = localStorage.getItem('portal_token')
      const token = rgoneEmpToken || portalToken
      if (token) {
        config.headers['Authorization'] = `Bearer ${token}`
      }
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response Interceptor: Error handling (统一收拢到 MdSnackbar / useToast 全局提示)
instance.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error: AxiosError<{ detail?: string }>) => {
    // 若请求配置了 silent: true，则不弹出全局提示，交由业务层自行处理
    const isSilent = (error.config as CustomInternalRequestConfig)?.silent

    const status = error.response?.status
    let detail = error.response?.data?.detail || error.message || '网络请求错误'

    // Vite proxy ECONNREFUSED 错误识别
    const rawData = String(error.response?.data || '')
    if (status === 500 && (rawData.includes('ECONNREFUSED') || rawData.includes('http proxy error'))) {
      detail = '后端服务未启动：无法连接 Hub Core (http://127.0.0.1:8080)'
    }

    if (status === 401) {
      const adminCtx = isAdminRequestContext(error.config?.url)
      if (isEmbeddedMode()) {
        // 嵌入 RgOne iframe 模式下：严禁跳转 Hub 登录页，通知父窗口弹出小秘书登录框
        if (!adminCtx) {
          localStorage.removeItem('rgone_emp_token')
          localStorage.removeItem('portal_token')
        }
        try {
          window.parent.postMessage(
            {
              type: 'RGONE_OPEN_LOGIN',
              mode: adminCtx ? 'admin' : 'employee',
              reason: 'unauthorized',
            },
            window.location.origin
          )
        } catch {
          // ignore cross-origin postMessage error
        }
      } else if (window.location.pathname.includes('/admin') && !window.location.pathname.endsWith('/login')) {
        window.location.href = `${import.meta.env.BASE_URL}login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
      }
    }

    if (!isSilent) {
      // 标记错误对象已由全局拦截器弹出提示，防止业务层 catch 二次重复弹窗
      ;(error as any).__toastShown = true

      if (status === 401) {
        toast.error(`认证失败: ${detail}`)
      } else if (status === 403) {
        toast.error(`权限不足: ${detail}`)
      } else if (status === 404) {
        toast.warning(`资源不存在: ${detail}`)
      } else {
        toast.error(`请求失败 (${status || 'ERROR'}): ${detail}`)
      }
    }

    return Promise.reject(error)
  }
)

export const http = {
  get: <T = unknown>(url: string, config?: CustomRequestConfig): Promise<T> =>
    instance.get(url, config) as unknown as Promise<T>,
  post: <T = unknown>(url: string, data?: unknown, config?: CustomRequestConfig): Promise<T> =>
    instance.post(url, data, config) as unknown as Promise<T>,
  put: <T = unknown>(url: string, data?: unknown, config?: CustomRequestConfig): Promise<T> =>
    instance.put(url, data, config) as unknown as Promise<T>,
  patch: <T = unknown>(url: string, data?: unknown, config?: CustomRequestConfig): Promise<T> =>
    instance.patch(url, data, config) as unknown as Promise<T>,
  delete: <T = unknown>(url: string, config?: CustomRequestConfig): Promise<T> =>
    instance.delete(url, config) as unknown as Promise<T>,
}

export default http
