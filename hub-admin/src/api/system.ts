import axios from 'axios'
import http from './http'
import { listServices } from './server'
import { listTools } from './tool'
import type { DashboardSummary, SystemStatus } from './types'

export async function getHealthz(): Promise<{ status: string }> {
  const res = await axios.get('/healthz')
  return res.data
}

export async function getReadyz(): Promise<{ status: string; error?: string }> {
  const res = await axios.get('/readyz')
  return res.data
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return http.get<SystemStatus>('/system/status', { silent: true }).catch(async () => {
    const [health, ready, services] = await Promise.all([
      getHealthz().catch(() => ({ status: 'error' })),
      getReadyz().catch((e: Error) => ({ status: 'degraded', error: e.message })),
      listServices(undefined, { silent: true }).catch(() => []),
    ])

    return {
      hub_name: 'AI Capability Hub',
      hub_version: '0.3.0',
      status: ready.status === 'ready' ? 'ready' : (health.status === 'ok' ? 'ok' : 'degraded'),
      database: 'SQLite (data/hub.db)',
      mcp_endpoint: '/mcp',
      upstream_services_count: services.length,
    }
  })
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return http.get<DashboardSummary>('/dashboard/summary', { silent: true }).catch(async () => {
    const [services, tools] = await Promise.all([
      listServices(undefined, { silent: true }).catch(() => []),
      listTools().catch(() => []),
    ])

    const active = services.filter((s) => s.status === 'active').length
    const inactive = services.filter((s) => s.status === 'inactive').length
    const degraded = services.filter((s) => s.status === 'degraded').length

    return {
      servers_total: services.length,
      servers_active: active,
      servers_inactive: inactive,
      servers_degraded: degraded,
      tools_total: tools.length,
    }
  })
}
