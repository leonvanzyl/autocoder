/**
 * React Query hooks for project data
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/api";
import type {
  FeatureCreate,
  FeatureUpdate,
  ModelsResponse,
  Settings,
  SettingsUpdate,
} from "../lib/types";

// ============================================================================
// Projects
// ============================================================================

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: api.listProjects,
  });
}

export function useProject(name: string | null) {
  return useQuery({
    queryKey: ["project", name],
    queryFn: () => api.getProject(name!),
    enabled: !!name,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      name,
      path,
      specMethod,
    }: {
      name: string;
      path: string;
      specMethod?: "claude" | "manual";
    }) => api.createProject(name, path, specMethod),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) => api.deleteProject(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useCloneProjectRepository(projectName: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ repoUrl, targetDir }: { repoUrl: string; targetDir?: string }) => {
      if (!projectName) {
        throw new Error("No project selected");
      }
      return api.cloneProjectRepository(projectName, repoUrl, targetDir);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      if (projectName) {
        queryClient.invalidateQueries({ queryKey: ["project", projectName] });
      }
    },
  });
}

// ============================================================================
// Features
// ============================================================================

export function useFeatures(projectName: string | null) {
  return useQuery({
    queryKey: ["features", projectName],
    queryFn: () => api.listFeatures(projectName!),
    enabled: !!projectName,
    refetchInterval: 5000, // Refetch every 5 seconds for real-time updates
  });
}

export function useCreateFeature(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (feature: FeatureCreate) =>
      api.createFeature(projectName, feature),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["features", projectName] });
    },
  });
}

export function useDeleteFeature(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (featureId: number) =>
      api.deleteFeature(projectName, featureId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["features", projectName] });
    },
  });
}

export function useSkipFeature(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (featureId: number) => api.skipFeature(projectName, featureId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["features", projectName] });
    },
  });
}

export function useUpdateFeature(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      featureId,
      update,
    }: {
      featureId: number;
      update: FeatureUpdate;
    }) => api.updateFeature(projectName, featureId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["features", projectName] });
    },
  });
}

// ============================================================================
// Agent
// ============================================================================

export function useAgentStatus(projectName: string | null) {
  return useQuery({
    queryKey: ["agent-status", projectName],
    queryFn: () => api.getAgentStatus(projectName!),
    enabled: !!projectName,
    refetchInterval: 3000, // Poll every 3 seconds
  });
}

export function useStartAgent(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (
      options: {
        yoloMode?: boolean;
        parallelMode?: boolean;
        maxConcurrency?: number;
        testingAgentRatio?: number;
      } = {},
    ) => api.startAgent(projectName, options),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-status", projectName],
      });
    },
  });
}

export function useStopAgent(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.stopAgent(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-status", projectName],
      });
      // Invalidate schedule status to reflect manual stop override
      queryClient.invalidateQueries({ queryKey: ["nextRun", projectName] });
    },
  });
}

export function usePauseAgent(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.pauseAgent(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-status", projectName],
      });
    },
  });
}

export function useResumeAgent(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.resumeAgent(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["agent-status", projectName],
      });
    },
  });
}

// ============================================================================
// Setup
// ============================================================================

export function useSetupStatus() {
  return useQuery({
    queryKey: ["setup-status"],
    queryFn: api.getSetupStatus,
    staleTime: 60000, // Cache for 1 minute
  });
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.healthCheck,
    retry: false,
  });
}

// ============================================================================
// Filesystem
// ============================================================================

export function useListDirectory(path?: string) {
  return useQuery({
    queryKey: ["filesystem", "list", path],
    queryFn: () => api.listDirectory(path),
  });
}

export function useCreateDirectory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (path: string) => api.createDirectory(path),
    onSuccess: (_, path) => {
      // Invalidate parent directory listing
      const parentPath = path.split("/").slice(0, -1).join("/") || undefined;
      queryClient.invalidateQueries({
        queryKey: ["filesystem", "list", parentPath],
      });
    },
  });
}

export function useValidatePath() {
  return useMutation({
    mutationFn: (path: string) => api.validatePath(path),
  });
}

// ============================================================================
// Settings
// ============================================================================

// Default models response for placeholder (until API responds)
const DEFAULT_MODELS: ModelsResponse = {
  models: [
    { id: "claude-opus-4-5-20251101", name: "Claude Opus 4.5" },
    { id: "claude-sonnet-4-5-20250929", name: "Claude Sonnet 4.5" },
  ],
  default: "claude-opus-4-5-20251101",
};

const DEFAULT_SETTINGS: Settings = {
  yolo_mode: false,
  model: "claude-opus-4-5-20251101",
  glm_mode: false,
  ollama_mode: false,
  testing_agent_ratio: 1,
};

export function useAvailableModels() {
  return useQuery({
    queryKey: ["available-models"],
    queryFn: api.getAvailableModels,
    staleTime: 300000, // Cache for 5 minutes - models don't change often
    retry: 1,
    placeholderData: DEFAULT_MODELS,
  });
}

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: api.getSettings,
    staleTime: 60000, // Cache for 1 minute
    retry: 1,
    placeholderData: DEFAULT_SETTINGS,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (settings: SettingsUpdate) => api.updateSettings(settings),
    onMutate: async (newSettings) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["settings"] });

      // Snapshot previous value
      const previous = queryClient.getQueryData<Settings>(["settings"]);

      // Optimistically update
      queryClient.setQueryData<Settings>(["settings"], (old) => ({
        ...DEFAULT_SETTINGS,
        ...old,
        ...newSettings,
      }));

      return { previous };
    },
    onError: (_err, _newSettings, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(["settings"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}
