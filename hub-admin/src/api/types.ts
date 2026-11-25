export type ServiceStatus = 'active' | 'inactive' | 'degraded' | 'pending'

export type ToolRiskLevel = 'L0' | 'L1' | 'L2' | 'L3'

export interface RegisteredService {
  id: string
  name: string
  description?: string
  endpoint_url: string
  version?: string
  owner?: string
  status: ServiceStatus
  category?: string
  auth_mode?: string
  auth_label?: string
  auth_guide?: string
  auth_entry_url?: string
  usage_examples?: string[]
  trusted_credential_recipient?: boolean
  trusted_credential_version?: string | null
  trusted_credential_endpoint_url?: string | null
  trusted_confirmed_by?: string | null
  trusted_confirmed_at?: string | null
  downstream_status?: 'available' | 'unavailable' | string
  downstream_error?: string | null
  credential_schema?: {
    enabled: boolean
    auth_type?: string
    instructions?: string
    fields?: Array<{ field_name: string; label: string; field_type: string; required: boolean; secret?: boolean }>
  } | null
  created_at: string
  updated_at: string
  tools_count?: number
  last_checked?: string
}

export interface ServiceRegistration {
  service_id: string
  name: string
  endpoint_url: string
  description?: string
  owner?: string
  category?: string
  auth_mode?: string
  auth_label?: string
  auth_guide?: string
  auth_entry_url?: string
  usage_examples?: string[]
}

export interface RegisteredTool {
  id: string
  service_id: string
  name: string
  description?: string
  input_schema: Record<string, unknown>
  risk_level: ToolRiskLevel
  requires_confirmation: boolean
  created_at: string
  namespace_name?: string
  is_published?: boolean
}

export interface ToolTestRequest {
  tool_name: string
  arguments: Record<string, unknown>
}

export interface ToolTestResponse {
  tool_name: string
  service_id: string
  status: 'success' | 'tool_error' | 'exception'
  duration_ms: number
  result?: unknown
  error?: string
}

export interface AuditLogItem {
  id?: string
  timestamp: string
  user_id: string
  client_id: string
  service_id: string
  tool_name: string
  params_summary: Record<string, unknown>
  result_status: string
  duration_ms: number
  trace_id?: string
}

export interface AuditLogsResponse {
  items: AuditLogItem[]
  total: number
}

export interface ServiceMetadataUpdate {
  name?: string
  description?: string
  owner?: string
}

export interface ToolPolicyUpdate {
  risk_level: ToolRiskLevel
  requires_confirmation: boolean
}

export interface DashboardSummary {
  servers_total: number
  servers_active: number
  servers_inactive: number
  servers_degraded: number
  tools_total: number
  calls_total?: number
  calls_success?: number
  calls_failed?: number
}

export interface SystemStatus {
  hub_name: string
  hub_version: string
  status: 'ok' | 'ready' | 'degraded'
  database: string
  mcp_endpoint: string
  upstream_services_count: number
}
