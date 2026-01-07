/**
 * Model Settings API Hook
 * =======================
 *
 * React Query hooks for managing AI model selection settings.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export interface ModelSettings {
  preset: string;
  available_models: string[];
  category_mapping: Record<string, string>;
  fallback_model: string;
  auto_detect_simple: boolean;
}

export interface PresetInfo {
  name: string;
  description: string;
  models: string[];
  best_for: string;
}

export interface PresetsResponse {
  presets: Record<string, PresetInfo>;
}

// API base URL
const API_BASE = '/api';

// Get current model settings
export function useModelSettings() {
  return useQuery({
    queryKey: ['model-settings'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/model-settings`);
      if (!response.ok) {
        throw new Error('Failed to fetch model settings');
      }
      return response.json() as Promise<ModelSettings>;
    },
  });
}

// Update model settings
export function useUpdateModelSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (settings: Partial<ModelSettings>) => {
      const response = await fetch(`${API_BASE}/model-settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        throw new Error('Failed to update model settings');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-settings'] });
    },
  });
}

// Apply preset
export function useApplyPreset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (preset: string) => {
      const response = await fetch(`${API_BASE}/model-settings/preset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset }),
      });

      if (!response.ok) {
        throw new Error('Failed to apply preset');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-settings'] });
    },
  });
}

// Get available presets
export function usePresets() {
  return useQuery({
    queryKey: ['model-presets'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/model-settings/presets`);
      if (!response.ok) {
        throw new Error('Failed to fetch presets');
      }
      return response.json() as Promise<PresetsResponse>;
    },
  });
}

// Test model selection for a feature
export function useTestModelSelection() {
  return useMutation({
    mutationFn: async (feature: { category: string; description: string; name: string }) => {
      const response = await fetch(`${API_BASE}/model-settings/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(feature),
      });

      if (!response.ok) {
        throw new Error('Failed to test model selection');
      }

      return response.json();
    },
  });
}
