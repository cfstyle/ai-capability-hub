import http, { CustomRequestConfig } from './http'
import type { RegisteredService, ServiceRegistration, ServiceStatus } from './types'

export function listServices(status?: ServiceStatus, config?: CustomRequestConfig): Promise<RegisteredService[]> {
  return http.get<RegisteredService[]>('/services', { ...config, params: status ? { status } : {} })
}

export function getService(serviceId: string, config?: CustomRequestConfig): Promise<RegisteredService> {
  return http.get<RegisteredService>(`/services/${serviceId}`, config)
}

export function registerService(data: ServiceRegistration): Promise<RegisteredService> {
  return http.post<RegisteredService>('/services/register', data)
}

export function updateServiceStatus(serviceId: string, status: ServiceStatus): Promise<RegisteredService> {
  return http.put<RegisteredService>(`/services/${serviceId}/status`, { status })
}

export function updateServiceCredentialTrust(serviceId: string, trusted: boolean): Promise<RegisteredService> {
  return http.put<RegisteredService>(`/services/${serviceId}/credential-trust`, { trusted })
}

export function updateServiceMetadata(
  serviceId: string,
  data: {
    name?: string
    description?: string
    owner?: string
    category?: string
    auth_mode?: string
    auth_label?: string
    auth_guide?: string
    auth_entry_url?: string
    usage_examples?: string[]
  }
): Promise<RegisteredService> {
  return http.patch<RegisteredService>(`/services/${serviceId}`, data)
}

export function refreshServiceTools(serviceId: string): Promise<{ service_id: string; tools_discovered: number; status: string }> {
  return http.post<{ service_id: string; tools_discovered: number; status: string }>(`/services/${serviceId}/refresh`)
}

export function testServerConnection(serviceId: string): Promise<{ success: boolean; latency_ms?: number; message?: string }> {
  return http.post<{ success: boolean; latency_ms?: number; message?: string }>(
    `/services/${serviceId}/test`,
    {},
    { silent: true }
  )
}

export interface PluginInspectResult {
  valid: boolean
  service_id: string
  name: string
  version: string
  description: string
  author: string
  port: number
  tools: Array<{ name: string; description: string; risk_level: string }>
  file_count: number
  prefix: string
  manifest: Record<string, any>
}

export function downloadPluginTemplate(): Promise<Blob> {
  return http.get('/plugins/template/download', {
    responseType: 'blob',
  })
}

export function inspectPlugin(file: File): Promise<PluginInspectResult> {
  const formData = new FormData()
  formData.append('file', file)
  return http.post<PluginInspectResult>('/plugins/inspect', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function publishPlugin(formData: FormData): Promise<RegisteredService> {
  return http.post<RegisteredService>('/plugins/publish', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
}

export function getDeveloperGuide(): Promise<{ content: string }> {
  return http.get<{ content: string }>('/portal/docs/developer-guide', { baseURL: '' })
}

