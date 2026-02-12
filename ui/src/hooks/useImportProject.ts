/**
 * Hook for managing project import workflow
 *
 * Handles:
 * - Stack detection via API
 * - Feature extraction
 * - Feature creation in database
 */

import { useState, useCallback } from 'react'

// API base path (relative since frontend is served from same origin)
const API_BASE = '/api'

// API response types
interface StackInfo {
  name: string
  category: string
  confidence: number
}

interface AnalyzeResponse {
  project_dir: string
  detected_stacks: StackInfo[]
  primary_frontend: string | null
  primary_backend: string | null
  database: string | null
  routes_count: number
  components_count: number
  endpoints_count: number
  summary: string
}

interface DetectedFeature {
  category: string
  name: string
  description: string
  steps: string[]
  source_type: string
  source_file: string | null
  confidence: number
}

interface ExtractFeaturesResponse {
  features: DetectedFeature[]
  count: number
  by_category: Record<string, number>
  summary: string
}

interface CreateFeaturesResponse {
  created: number
  project_name: string
  message: string
}

// Hook state
interface ImportState {
  step: 'idle' | 'analyzing' | 'detected' | 'extracting' | 'extracted' | 'creating' | 'complete' | 'error'
  projectPath: string | null
  analyzeResult: AnalyzeResponse | null
  featuresResult: ExtractFeaturesResponse | null
  createResult: CreateFeaturesResponse | null
  error: string | null
  selectedFeatures: DetectedFeature[]
}

export interface UseImportProjectReturn {
  state: ImportState
  analyze: (path: string) => Promise<boolean>
  extractFeatures: () => Promise<boolean>
  createFeatures: (projectName: string) => Promise<boolean>
  toggleFeature: (feature: DetectedFeature) => void
  selectAllFeatures: () => void
  deselectAllFeatures: () => void
  reset: () => void
}

const initialState: ImportState = {
  step: 'idle',
  projectPath: null,
  analyzeResult: null,
  featuresResult: null,
  createResult: null,
  error: null,
  selectedFeatures: [],
}

export function useImportProject(): UseImportProjectReturn {
  const [state, setState] = useState<ImportState>(initialState)

  const analyze = useCallback(async (path: string): Promise<boolean> => {
    setState(prev => ({ ...prev, step: 'analyzing', projectPath: path, error: null }))

    try {
      const response = await fetch(`${API_BASE}/import/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to analyze project')
      }

      const result: AnalyzeResponse = await response.json()
      setState(prev => ({
        ...prev,
        step: 'detected',
        analyzeResult: result,
      }))
      return true
    } catch (err) {
      setState(prev => ({
        ...prev,
        step: 'error',
        error: err instanceof Error ? err.message : 'Analysis failed',
      }))
      return false
    }
  }, [])

  const extractFeatures = useCallback(async (): Promise<boolean> => {
    if (!state.projectPath) return false

    setState(prev => ({ ...prev, step: 'extracting', error: null }))

    try {
      const response = await fetch(`${API_BASE}/import/extract-features`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: state.projectPath }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to extract features')
      }

      const result: ExtractFeaturesResponse = await response.json()
      setState(prev => ({
        ...prev,
        step: 'extracted',
        featuresResult: result,
        selectedFeatures: result.features, // Select all by default
      }))
      return true
    } catch (err) {
      setState(prev => ({
        ...prev,
        step: 'error',
        error: err instanceof Error ? err.message : 'Feature extraction failed',
      }))
      return false
    }
  }, [state.projectPath])

  const createFeatures = useCallback(async (projectName: string): Promise<boolean> => {
    if (!state.selectedFeatures.length) return false

    setState(prev => ({ ...prev, step: 'creating', error: null }))

    try {
      const features = state.selectedFeatures.map(f => ({
        category: f.category,
        name: f.name,
        description: f.description,
        steps: f.steps,
      }))

      const response = await fetch(`${API_BASE}/import/create-features`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: projectName, features }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to create features')
      }

      const result: CreateFeaturesResponse = await response.json()
      setState(prev => ({
        ...prev,
        step: 'complete',
        createResult: result,
      }))
      return true
    } catch (err) {
      setState(prev => ({
        ...prev,
        step: 'error',
        error: err instanceof Error ? err.message : 'Feature creation failed',
      }))
      return false
    }
  }, [state.selectedFeatures])

  const toggleFeature = useCallback((feature: DetectedFeature) => {
    setState(prev => {
      const isSelected = prev.selectedFeatures.some(
        f => f.name === feature.name && f.category === feature.category
      )

      if (isSelected) {
        return {
          ...prev,
          selectedFeatures: prev.selectedFeatures.filter(
            f => !(f.name === feature.name && f.category === feature.category)
          ),
        }
      } else {
        return {
          ...prev,
          selectedFeatures: [...prev.selectedFeatures, feature],
        }
      }
    })
  }, [])

  const selectAllFeatures = useCallback(() => {
    setState(prev => ({
      ...prev,
      selectedFeatures: prev.featuresResult?.features || [],
    }))
  }, [])

  const deselectAllFeatures = useCallback(() => {
    setState(prev => ({
      ...prev,
      selectedFeatures: [],
    }))
  }, [])

  const reset = useCallback(() => {
    setState(initialState)
  }, [])

  return {
    state,
    analyze,
    extractFeatures,
    createFeatures,
    toggleFeature,
    selectAllFeatures,
    deselectAllFeatures,
    reset,
  }
}
