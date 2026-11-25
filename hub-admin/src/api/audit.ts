import http from './http'
import type { AuditLogsResponse } from './types'

export function listAuditLogs(params?: {
  service_id?: string
  tool_name?: string
  status?: string
  limit?: number
  offset?: number
}): Promise<AuditLogsResponse> {
  return http.get<AuditLogsResponse>('/audit-logs', { params, silent: true }).catch(() => {
    return { items: [], total: 0 }
  })
}
