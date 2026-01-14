import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'

export function useAutocoderYaml(projectName: string) {
  return useQuery({
    queryKey: ['project-config', projectName, 'autocoder-yaml'],
    queryFn: () => api.getAutocoderYaml(projectName),
    enabled: !!projectName,
  })
}

export function useUpdateAutocoderYaml(projectName: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (content: string) => api.updateAutocoderYaml(projectName, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-config', projectName, 'autocoder-yaml'] })
    },
  })
}

