/**
 * React Query hooks for project data
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import type { FeatureCreate } from '../lib/types'

// ============================================================================
// Projects
// ============================================================================

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: api.listProjects,
  })
}

export function useProject(name: string | null) {
  return useQuery({
    queryKey: ['project', name],
    queryFn: () => api.getProject(name!),
    enabled: !!name,
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ name, path, specMethod }: { name: string; path: string; specMethod?: 'claude' | 'manual' }) =>
      api.createProject(name, path, specMethod),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (name: string) => api.deleteProject(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

// ============================================================================
// Features
// ============================================================================

export function useFeatures(projectName: string | null) {
  return useQuery({
    queryKey: ['features', projectName],
    queryFn: () => api.listFeatures(projectName!),
    enabled: !!projectName,
    refetchInterval: 5000, // Refetch every 5 seconds for real-time updates
  })
}

export function useCreateFeature(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (feature: FeatureCreate) => api.createFeature(projectName, feature),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
    },
  })
}

export function useDeleteFeature(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (featureId: number) => api.deleteFeature(projectName, featureId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
    },
  })
}

export function useSkipFeature(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (featureId: number) => api.skipFeature(projectName, featureId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
    },
  })
}

// ============================================================================
// Agent
// ============================================================================

export function useAgentStatus(projectName: string | null) {
  return useQuery({
    queryKey: ['agent-status', projectName],
    queryFn: () => api.getAgentStatus(projectName!),
    enabled: !!projectName,
    refetchInterval: 3000, // Poll every 3 seconds
  })
}

export function useStartAgent(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (yoloMode: boolean = false) => api.startAgent(projectName, yoloMode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-status', projectName] })
    },
  })
}

export function useStopAgent(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.stopAgent(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-status', projectName] })
    },
  })
}

export function usePauseAgent(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.pauseAgent(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-status', projectName] })
    },
  })
}

export function useResumeAgent(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.resumeAgent(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-status', projectName] })
    },
  })
}

// ============================================================================
// Setup
// ============================================================================

export function useSetupStatus() {
  return useQuery({
    queryKey: ['setup-status'],
    queryFn: api.getSetupStatus,
    staleTime: 60000, // Cache for 1 minute
  })
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.healthCheck,
    retry: false,
  })
}

// ============================================================================
// Filesystem
// ============================================================================

export function useListDirectory(path?: string) {
  return useQuery({
    queryKey: ['filesystem', 'list', path],
    queryFn: () => api.listDirectory(path),
  })
}

export function useCreateDirectory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (path: string) => api.createDirectory(path),
    onSuccess: (_, path) => {
      // Invalidate parent directory listing
      const parentPath = path.split('/').slice(0, -1).join('/') || undefined
      queryClient.invalidateQueries({ queryKey: ['filesystem', 'list', parentPath] })
    },
  })
}

export function useValidatePath() {
  return useMutation({
    mutationFn: (path: string) => api.validatePath(path),
  })
}
