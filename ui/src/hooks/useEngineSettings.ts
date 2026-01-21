/**
 * Engine Settings API Hook
 * ========================
 *
 * Per-project engine chain configuration.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import type { EngineSettings } from '../lib/types'

export function useEngineSettings(projectName?: string | null) {
  return useQuery({
    queryKey: ['engine-settings', projectName ?? null],
    enabled: !!projectName,
    queryFn: () => api.getEngineSettings(projectName as string),
  })
}

export function useUpdateEngineSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ projectName, settings }: { projectName: string; settings: EngineSettings }) => {
      return api.updateEngineSettings(projectName, settings)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['engine-settings'] })
    },
  })
}
