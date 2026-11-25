import axios, { AxiosError, InternalAxiosRequestConfig, AxiosRequestConfig } from 'axios'
import { useToast } from '@/composables/useToast'

const toast = useToast()

export interface CustomRequestConfig extends AxiosRequestConfig {
  silent?: boolean
}

interface CustomInternalRequestConfig extends InternalAxiosRequestConfig {
  silent?: boolean
}

const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request Interceptor: Attach API Key or Token
instance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const apiKey = localStorage.getItem('hub_admin_api_key')
    const portalToken = localStorage.getItem('portal_token')
    if (apiKey) {
      config.headers['X-API-Key'] = apiKey
      config.headers['Authorization'] = `Bearer ${apiKey}`
    } else if (portalToken) {
      config.headers['Authorization'] = `Bearer ${portalToken}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response Interceptor: Error handling (统一收拢到 MdSnackbar / useToast 全局提示，杜绝旧项目顶部粉色消息框)
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

    if (!isSilent) {
      // 标记错误对象已由全局拦截器弹出提示，防止业务层 catch 二次重复弹窗
      ;(error as any).__toastShown = true

      if (status === 401) {
        toast.error(`认证失败: ${detail}`)
        // 仅在访问管理后台页面时才强制跳转登录，匿名访问公开页面时不扰乱用户
        if (window.location.pathname.startsWith('/admin') && window.location.pathname !== '/login') {
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
        }
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
