/**
 * React Query hooks for parallel agent observability.
 */

import { useQuery } from '@tanstack/react-query'

export interface ParallelAgentInfo {
  agent_id: string
  status: string
  last_ping: string | null
  pid: number | null
  worktree_path: string | null
  feature_id: number | null
  feature_name: string | null
  api_port: number | null
  web_port: number | null
  log_file_path: string | null
}

export interface ParallelAgentsStatus {
  is_running: boolean
  active_count: number
  agents: ParallelAgentInfo[]
}

const API_BASE = '/api'

export function useParallelAgentsStatus(projectName: string | null, limit: number = 50) {
  return useQuery({
    queryKey: ['parallel-agents', 'status', projectName, limit],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: String(limit) })
      const response = await fetch(
        `${API_BASE}/projects/${encodeURIComponent(projectName!)}/parallel/agents?${params}`
      )
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }
      return response.json() as Promise<ParallelAgentsStatus>
    },
    enabled: !!projectName,
    refetchInterval: 2000,
  })
}

