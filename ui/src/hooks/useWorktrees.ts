/**
 * React Query hooks for worktree maintenance endpoints.
 */

import { useMutation, useQuery } from '@tanstack/react-query'
import * as api from '../lib/api'

export function useCleanupQueue(projectName: string | null) {
  return useQuery({
    queryKey: ['cleanup-queue', projectName],
    enabled: !!projectName,
    queryFn: () => api.getCleanupQueue(projectName!),
    refetchInterval: 5000,
  })
}

export function useProcessCleanupQueue(projectName: string) {
  return useMutation({
    mutationFn: (maxItems: number = 5) => api.processCleanupQueue(projectName, { max_items: maxItems }),
  })
}

export function useClearCleanupQueue(projectName: string) {
  return useMutation({
    mutationFn: () => api.clearCleanupQueue(projectName),
  })
}

