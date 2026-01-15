/**
 * React Query hooks for diagnostics endpoints.
 */

import { useMutation, useQuery } from '@tanstack/react-query'
import * as api from '../lib/api'

export function useDiagnosticsFixturesDir() {
  return useQuery({
    queryKey: ['diagnostics-fixtures-dir'],
    queryFn: api.getDiagnosticsFixturesDir,
  })
}

export function useRunQAProviderE2E() {
  return useMutation({
    mutationFn: (req: api.RunQAProviderE2ERequest) => api.runQAProviderE2E(req),
  })
}

export function useRunParallelMiniE2E() {
  return useMutation({
    mutationFn: (req: api.RunParallelMiniE2ERequest) => api.runParallelMiniE2E(req),
  })
}

export function useDiagnosticsRuns(limit: number = 25) {
  return useQuery({
    queryKey: ['diagnostics-runs', limit],
    queryFn: () => api.listDiagnosticsRuns(limit),
  })
}

export function useDiagnosticsRunTail(name: string | null, maxChars: number = 8000) {
  return useQuery({
    queryKey: ['diagnostics-run-tail', name, maxChars],
    enabled: !!name,
    queryFn: () => api.tailDiagnosticsRun(name as string, maxChars),
  })
}
