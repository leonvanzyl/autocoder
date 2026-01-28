/**
 * React Query hooks for assistant conversation management
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/api";

/**
 * List all conversations for a project
 */
export function useConversations(projectName: string | null) {
  return useQuery({
    queryKey: ["conversations", projectName],
    queryFn: () => api.listAssistantConversations(projectName!),
    enabled: !!projectName,
    staleTime: 30000, // Cache for 30 seconds
  });
}

/**
 * Get a single conversation with all its messages
 */
export function useConversation(
  projectName: string | null,
  conversationId: number | null,
) {
  return useQuery({
    queryKey: ["conversation", projectName, conversationId],
    queryFn: () => api.getAssistantConversation(projectName!, conversationId!),
    enabled: !!projectName && !!conversationId,
    staleTime: 30_000, // Cache for 30 seconds
  });
}

/**
 * Delete a conversation
 */
export function useDeleteConversation(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (conversationId: number) =>
      api.deleteAssistantConversation(projectName, conversationId),
    onSuccess: (_, deletedId) => {
      // Invalidate conversations list
      queryClient.invalidateQueries({
        queryKey: ["conversations", projectName],
      });
      // Remove the specific conversation from cache
      queryClient.removeQueries({
        queryKey: ["conversation", projectName, deletedId],
      });
    },
  });
}
