/**
 * Parallel Agents API Hook
 * =======================
 *
 * React Query hooks for managing parallel agent execution.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export interface AgentStatus {
  agent_id: string;
  feature_id: number;
  feature_name: string;
  status: 'running' | 'completed' | 'failed';
  model_used: string;
  progress: number;
}

export interface ParallelAgentsStatus {
  project_dir: string;
  parallel_count: number;
  running_agents: AgentStatus[];
  completed_count: number;
  failed_count: number;
  is_running: boolean;
}

export interface StartAgentsRequest {
  project_dir: string;
  parallel_count: number;
  preset?: string;
  models?: string[];
}

// API base URL
const API_BASE = '/api';

// Start parallel agents
export function useStartAgents() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: StartAgentsRequest) => {
      const response = await fetch(`${API_BASE}/parallel-agents/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error('Failed to start agents');
      }

      return response.json();
    },
    onSuccess: (data, variables) => {
      // Invalidate status query for this project
      queryClient.invalidateQueries({
        queryKey: ['parallel-agents', 'status', variables.project_dir],
      });
    },
  });
}

// Stop parallel agents
export function useStopAgents() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (projectDir: string) => {
      const response = await fetch(`${API_BASE}/parallel-agents/stop?project_dir=${encodeURIComponent(projectDir)}`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to stop agents');
      }

      return response.json();
    },
    onSuccess: (data, variables) => {
      // Invalidate status query for this project
      queryClient.invalidateQueries({
        queryKey: ['parallel-agents', 'status', variables],
      });
    },
  });
}

// Get parallel agents status
export function useParallelAgentsStatus(projectDir: string, parallelCount?: number) {
  return useQuery({
    queryKey: ['parallel-agents', 'status', projectDir, parallelCount],
    queryFn: async () => {
      const params = new URLSearchParams({
        project_dir: projectDir,
      });

      if (parallelCount !== undefined) {
        params.append('parallel_count', parallelCount.toString());
      }

      const response = await fetch(`${API_BASE}/parallel-agents/status?${params}`);
      if (!response.ok) {
        throw new Error('Failed to fetch agent status');
      }
      return response.json() as Promise<ParallelAgentsStatus>;
    },
    refetchInterval: 2000, // Poll every 2 seconds
  });
}

// Update parallel configuration
export function useUpdateParallelConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      projectDir,
      config,
    }: {
      projectDir: string;
      config: { parallel_count: number; preset?: string; models?: string[] };
    }) => {
      const response = await fetch(`${API_BASE}/parallel-agents/config?project_dir=${encodeURIComponent(projectDir)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error('Failed to update config');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-settings'] });
    },
  });
}

// Get available presets
export function useParallelPresets() {
  return useQuery({
    queryKey: ['parallel-presets'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/parallel-agents/presets`);
      if (!response.ok) {
        throw new Error('Failed to fetch presets');
      }
      return response.json();
    },
  });
}
