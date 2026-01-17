import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listKnowledgeFiles,
  getKnowledgeFile,
  putKnowledgeFile,
  deleteKnowledgeFile,
} from '../lib/api'

export function useKnowledgeFiles(projectName: string | null) {
  return useQuery({
    queryKey: ['knowledge-files', projectName],
    queryFn: () => listKnowledgeFiles(projectName!),
    enabled: !!projectName,
  })
}

export function useKnowledgeFile(projectName: string | null, filename: string | null) {
  return useQuery({
    queryKey: ['knowledge-file', projectName, filename],
    queryFn: () => getKnowledgeFile(projectName!, filename!),
    enabled: !!projectName && !!filename,
  })
}

export function useSaveKnowledgeFile(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ filename, content }: { filename: string; content: string }) =>
      putKnowledgeFile(projectName, filename, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-files', projectName] })
    },
  })
}

export function useDeleteKnowledgeFile(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (filename: string) => deleteKnowledgeFile(projectName, filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-files', projectName] })
    },
  })
}
