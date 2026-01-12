/**
 * React Query hooks for worker log file management.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import type { PruneWorkerLogsRequest } from '../lib/types'

export function useWorkerLogs(projectName: string | null) {
  return useQuery({
    queryKey: ['worker-logs', projectName],
    queryFn: () => api.listWorkerLogs(projectName!),
    enabled: !!projectName,
    refetchInterval: 5000,
  })
}

export function useWorkerLogTail(projectName: string | null, filename: string | null, tail: number) {
  return useQuery({
    queryKey: ['worker-log', projectName, filename, tail],
    queryFn: () => api.getWorkerLogTail(projectName!, filename!, tail),
    enabled: !!projectName && !!filename,
    refetchInterval: 3000,
  })
}

export function usePruneWorkerLogs(projectName: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: PruneWorkerLogsRequest) => api.pruneWorkerLogs(projectName, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-logs', projectName] })
    },
  })
}

export function useDeleteWorkerLog(projectName: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (filename: string) => api.deleteWorkerLog(projectName, filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-logs', projectName] })
    },
  })
}

