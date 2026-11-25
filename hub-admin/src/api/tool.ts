import http from './http'
import type { RegisteredTool, ToolPolicyUpdate, ToolTestResponse } from './types'

export function listTools(serviceId?: string): Promise<RegisteredTool[]> {
  return http.get<RegisteredTool[]>('/tools', { params: serviceId ? { service_id: serviceId } : {} })
}

export function getTool(toolId: string): Promise<RegisteredTool> {
  return http.get<RegisteredTool>(`/tools/${toolId}`).catch(async () => {
    const all = await listTools()
    const found = all.find((t) => t.id === toolId || t.name === toolId || `${t.service_id}__${t.name}` === toolId)
    if (!found) throw new Error(`Tool not found: ${toolId}`)
    return found
  })
}

export function testTool(toolId: string, params: Record<string, any>): Promise<ToolTestResponse> {
  return http.post<ToolTestResponse>(`/tools/${toolId}/test`, { arguments: params })
}

export function updateToolPolicy(
  toolId: string,
  data: ToolPolicyUpdate
): Promise<RegisteredTool> {
  return http.patch<RegisteredTool>(`/tools/${toolId}/policy`, data)
}
