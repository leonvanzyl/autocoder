/**
 * Hook for managing assistant conversations
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listAssistantConversations, deleteAssistantConversation } from '../lib/api'

export function useAssistantConversations(projectName: string | null) {
  const queryClient = useQueryClient()

  const conversations = useQuery({
    queryKey: ['assistant-conversations', projectName],
    queryFn: () => {
      if (!projectName) throw new Error('Project name required')
      return listAssistantConversations(projectName)
    },
    enabled: !!projectName,
    staleTime: 1000 * 60, // 1 minute
  })

  const deleteConversation = useMutation({
    mutationFn: (conversationId: number) => {
      if (!projectName) throw new Error('Project name required')
      return deleteAssistantConversation(projectName, conversationId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['assistant-conversations', projectName],
      })
    },
  })

  return {
    conversations: conversations.data || [],
    isLoading: conversations.isLoading,
    error: conversations.error,
    deleteConversation: deleteConversation.mutateAsync,
    isDeleting: deleteConversation.isPending,
    deleteError: deleteConversation.error,
    refetch: conversations.refetch,
  }
}
