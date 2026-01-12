/**
 * React Query hooks for server-side advanced settings.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import type { AdvancedSettings } from '../lib/types'

export function useAdvancedSettings() {
  return useQuery({
    queryKey: ['advanced-settings'],
    queryFn: api.getAdvancedSettings,
  })
}

export function useUpdateAdvancedSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (settings: AdvancedSettings) => api.updateAdvancedSettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['advanced-settings'] })
    },
  })
}

