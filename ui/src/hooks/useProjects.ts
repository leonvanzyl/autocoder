/**
 * React Query hooks for project data
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import type { DevServerConfig, FeatureCreate, FeatureUpdate, ModelsResponse, ProjectSettingsUpdate, ProvidersResponse, Settings, SettingsUpdate } from '../lib/types'

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

export function useResetProject(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (fullReset: boolean) => api.resetProject(projectName, fullReset),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['project', projectName] })
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
      queryClient.invalidateQueries({ queryKey: ['agent-status', projectName] })
    },
  })
}

export function useUpdateProjectSettings(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (settings: ProjectSettingsUpdate) =>
      api.updateProjectSettings(projectName, settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['project', projectName] })
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

export function useUpdateFeature(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ featureId, update }: { featureId: number; update: FeatureUpdate }) =>
      api.updateFeature(projectName, featureId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
    },
  })
}

export function useResolveHumanInput(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ featureId, fields }: { featureId: number; fields: Record<string, string | boolean | string[]> }) =>
      api.resolveHumanInput(projectName, featureId, { fields }),
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
    mutationFn: (options: {
      yoloMode?: boolean
      parallelMode?: boolean
      maxConcurrency?: number
      testingAgentRatio?: number
    } = {}) => api.startAgent(projectName, options),
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
      // Invalidate schedule status to reflect manual stop override
      queryClient.invalidateQueries({ queryKey: ['nextRun', projectName] })
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

export function useGracefulPauseAgent(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.gracefulPauseAgent(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-status', projectName] })
    },
  })
}

export function useGracefulResumeAgent(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.gracefulResumeAgent(projectName),
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

// ============================================================================
// Settings
// ============================================================================

// Default models response for placeholder (until API responds)
const DEFAULT_MODELS: ModelsResponse = {
  models: [
    { id: 'claude-opus-4-6', name: 'Claude Opus' },
    { id: 'claude-sonnet-4-5-20250929', name: 'Claude Sonnet' },
  ],
  default: 'claude-opus-4-6',
}

const DEFAULT_SETTINGS: Settings = {
  yolo_mode: false,
  model: 'claude-opus-4-6',
  glm_mode: false,
  ollama_mode: false,
  testing_agent_ratio: 1,
  playwright_headless: true,
  batch_size: 3,
  agent_session_logging: true,
  api_provider: 'claude',
  api_base_url: null,
  api_has_auth_token: false,
  api_model: null,
}

const DEFAULT_PROVIDERS: ProvidersResponse = {
  providers: [
    { id: 'claude', name: 'Claude (Anthropic)', base_url: null, models: DEFAULT_MODELS.models, default_model: 'claude-opus-4-6', requires_auth: false },
  ],
  current: 'claude',
}

export function useAvailableProviders() {
  return useQuery({
    queryKey: ['available-providers'],
    queryFn: api.getAvailableProviders,
    staleTime: 300000,
    retry: 1,
    placeholderData: DEFAULT_PROVIDERS,
  })
}

export function useAvailableModels() {
  return useQuery({
    queryKey: ['available-models'],
    queryFn: api.getAvailableModels,
    staleTime: 300000, // Cache for 5 minutes - models don't change often
    retry: 1,
    placeholderData: DEFAULT_MODELS,
  })
}

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: api.getSettings,
    staleTime: 60000, // Cache for 1 minute
    retry: 1,
    placeholderData: DEFAULT_SETTINGS,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (settings: SettingsUpdate) => api.updateSettings(settings),
    onMutate: async (newSettings) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['settings'] })

      // Snapshot previous value
      const previous = queryClient.getQueryData<Settings>(['settings'])

      // Optimistically update
      queryClient.setQueryData<Settings>(['settings'], (old) => ({
        ...DEFAULT_SETTINGS,
        ...old,
        ...newSettings,
      }))

      return { previous }
    },
    onError: (_err, _newSettings, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(['settings'], context.previous)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      queryClient.invalidateQueries({ queryKey: ['available-models'] })
      queryClient.invalidateQueries({ queryKey: ['available-providers'] })
    },
  })
}

// ============================================================================
// Dev Server Config
// ============================================================================

// Default config for placeholder (until API responds)
const DEFAULT_DEV_SERVER_CONFIG: DevServerConfig = {
  detected_type: null,
  detected_command: null,
  custom_command: null,
  effective_command: null,
}

export function useDevServerConfig(projectName: string | null) {
  return useQuery({
    queryKey: ['dev-server-config', projectName],
    queryFn: () => api.getDevServerConfig(projectName!),
    enabled: !!projectName,
    staleTime: 30_000,
    placeholderData: DEFAULT_DEV_SERVER_CONFIG,
  })
}

export function useUpdateDevServerConfig(projectName: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (customCommand: string | null) =>
      api.updateDevServerConfig(projectName, customCommand),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dev-server-config', projectName] })
    },
  })
}
