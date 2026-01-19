/**
 * React Query hooks for the Mission Control activity feed.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'

export function useActivityEvents(
  projectName: string | null,
  opts: { limit?: number; enabled?: boolean; refetchInterval?: number } = {}
) {
  const limit = opts.limit ?? 200
  const enabled = (opts.enabled ?? true) && !!projectName
  const refetchInterval = opts.refetchInterval ?? 2500

  return useQuery({
    queryKey: ['activity', projectName, limit],
    queryFn: () => api.listActivityEvents(projectName!, { limit }),
    enabled,
    refetchInterval,
  })
}

export function useClearActivityEvents(projectName: string | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      if (!projectName) return { deleted: 0 }
      return api.clearActivityEvents(projectName)
    },
    onSuccess: () => {
      if (!projectName) return
      queryClient.invalidateQueries({ queryKey: ['activity', projectName] })
    },
  })
}

