import http from './http'

export interface PortalTrendItem {
  date: string
  calls: number
  success_calls: number
}

export interface PortalOverview {
  services_count: number
  tools_count: number
  total_calls: number
  active_services_count: number
  health_rate: number
  daily_trends: PortalTrendItem[]
}

export interface CredentialFieldSchema {
  field_name: string
  label: string
  field_type: 'text' | 'password'
  required: boolean
  secret: boolean
  description?: string
  placeholder?: string
}

export interface ServiceCredentialSchema {
  enabled: boolean
  auth_type: string
  instructions: string
  fields: CredentialFieldSchema[]
}

export interface UserMcpDetail {
  service_id: string
  service_name: string
  category: string
  endpoint_url: string
  requires_credentials: boolean
  credential_status: string // "not_required", "saved", "verified", "invalid", "unbound", "missing"
  service_status?: string
  downstream_status?: string // "available", "unavailable"
  downstream_error?: string | null
  credential_summary: Record<string, any>
  credential_version: number
  approved_tools: string[]
  pending_tools: string[]
  updated_at?: string
}

export interface PortalCapabilityCard {
  id: string
  name: string
  description: string
  category: string
  tools_count: number
  status: 'active' | 'inactive' | 'degraded' | 'pending'
  auth_mode: string
  auth_label: string
  auth_guide?: string
  auth_entry_url?: string
  credential_schema?: ServiceCredentialSchema | null
  call_count: number
  recent_calls_7d: number
  last_active_at: string | null
  created_at: string
}

export interface PortalToolItem {
  id?: string
  name: string
  namespace_name: string
  description: string
  risk_level: string
  requires_confirmation: boolean
  requires_credentials?: boolean
  input_schema: Record<string, any>
}

export interface PermissionRequest {
  id: string
  user_id: string
  user_name: string
  service_id: string
  service_name: string
  tool_ids: string[]
  tool_names: string[]
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  reviewed_by?: string | null
  reviewed_at?: string | null
  comment?: string | null
}

export interface PermissionRequestCreate {
  user_id: string
  user_name?: string
  service_id: string
  tool_ids: string[]
  reason: string
  credentials?: Record<string, any>
}

export interface PermissionRequestReview {
  status: 'approved' | 'rejected'
  reviewer?: string
  comment?: string
}

export interface UserClientConfig {
  user_id: string
  token: string
  gateway_url: string
  config_templates: {
    cursor: {
      mcpServers: {
        [key: string]: {
          url: string
          headers: {
            Authorization: string
          }
        }
      }
    }
    claude: {
      mcpServers: {
        [key: string]: {
          url: string
          headers: {
            Authorization: string
          }
        }
      }
    }
  }
}

export interface PortalCapabilityDetail {
  id: string
  name: string
  description: string
  category: string
  version: string
  status: 'active' | 'inactive' | 'degraded' | 'pending'
  created_at: string
  auth_mode: string
  auth_label: string
  auth_guide: string
  auth_entry_url: string
  credential_schema?: ServiceCredentialSchema | null
  usage_examples: string[]
  gateway_url: string
  protocol: string
  tools: PortalToolItem[]
  total_calls: number
  recent_calls_7d: number
  daily_trends: PortalTrendItem[]
  last_active_at: string | null
}

export interface PortalCapabilitiesQuery {
  q?: string
  category?: string
  sort_by?: 'popular' | 'recent_active' | 'newest' | 'name'
}

export interface PortalLoginResponse {
  user_id: string
  user_name: string
  role: string
  token: string
}

export const portalLogin = (userId: string, userName?: string): Promise<PortalLoginResponse> => {
  return http.post<PortalLoginResponse>('/portal/auth/login', { user_id: userId, user_name: userName })
}

export const getPortalOverview = (): Promise<PortalOverview> => {
  return http.get<PortalOverview>('/portal/overview')
}

export const getPortalCapabilities = (params?: PortalCapabilitiesQuery): Promise<PortalCapabilityCard[]> => {
  return http.get<PortalCapabilityCard[]>('/portal/capabilities', { params })
}

export const getPortalCapabilityDetail = (id: string): Promise<PortalCapabilityDetail> => {
  return http.get<PortalCapabilityDetail>(`/portal/capabilities/${encodeURIComponent(id)}`)
}

export const getPortalMyConfig = (userId?: string): Promise<UserClientConfig> => {
  return http.get<UserClientConfig>('/portal/my-config', { params: { user_id: userId } })
}

export const getPortalMyGrants = (userId?: string): Promise<{ user_id: string; granted_tool_ids: string[] }> => {
  return http.get<{ user_id: string; granted_tool_ids: string[] }>('/portal/my-grants', { params: { user_id: userId } })
}

export const createPortalPermissionRequest = (data: PermissionRequestCreate): Promise<PermissionRequest> => {
  return http.post<PermissionRequest>('/portal/permission-requests', data)
}

export const getPortalMyRequests = (userId?: string): Promise<PermissionRequest[]> => {
  return http.get<PermissionRequest[]>('/portal/my-requests', { params: { user_id: userId } })
}

// 管理端审批 API
export const getAdminPermissionRequests = (params?: { user_id?: string; status?: string }): Promise<PermissionRequest[]> => {
  return http.get<PermissionRequest[]>('/admin/permission-requests', { params })
}

export const reviewAdminPermissionRequest = (id: string, data: PermissionRequestReview): Promise<PermissionRequest> => {
  return http.post<PermissionRequest>(`/admin/permission-requests/${encodeURIComponent(id)}/review`, data)
}

export const getPortalMyMcps = (probe: boolean = true): Promise<UserMcpDetail[]> => {
  return http.get<UserMcpDetail[]>('/portal/my-mcps', { params: { probe } })
}

export const updatePortalServiceBinding = (serviceId: string, credentials: Record<string, any>): Promise<any> => {
  return http.post<any>(`/portal/my-mcps/${encodeURIComponent(serviceId)}/binding`, { credentials })
}

export const unbindPortalServiceBinding = (serviceId: string): Promise<any> => {
  return http.delete<any>(`/portal/my-mcps/${encodeURIComponent(serviceId)}/binding`)
}
