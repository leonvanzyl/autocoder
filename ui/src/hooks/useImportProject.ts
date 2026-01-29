/**
 * Hook for managing project import workflow
 *
 * Handles:
 * - Stack detection via API
 * - Feature extraction
 * - Feature creation in database
 */

import { useState, useCallback } from 'react'
import { API_BASE_URL } from '../lib/api'

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
  analyze: (path: string) => Promise<AnalyzeResponse | null>
  extractFeatures: () => Promise<ExtractFeaturesResponse | null>
  createFeatures: (projectName: string) => Promise<void>
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

  const analyze = useCallback(async (path: string) => {
    setState(prev => ({ ...prev, step: 'analyzing', projectPath: path, error: null }))

    try {
      const response = await fetch(`${API_BASE_URL}/api/import/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })

      if (!response.ok) {
        let errorMessage = 'Failed to analyze project'
        try {
          const text = await response.text()
          try {
            const error = JSON.parse(text)
            errorMessage = error.detail || errorMessage
          } catch {
            // JSON parsing failed, use raw text
            errorMessage = `${errorMessage}: ${response.status} ${text}`
          }
        } catch {
          errorMessage = `${errorMessage}: ${response.status}`
        }
        throw new Error(errorMessage)
      }

      const result: AnalyzeResponse = await response.json()
      setState(prev => ({
        ...prev,
        step: 'detected',
        analyzeResult: result,
      }))
      return result
    } catch (err) {
      setState(prev => ({
        ...prev,
        step: 'error',
        error: err instanceof Error ? err.message : 'Analysis failed',
      }))
      return null
    }
  }, [])

  const extractFeatures = useCallback(async () => {
    if (!state.projectPath) return null

    setState(prev => ({ ...prev, step: 'extracting', error: null }))

    try {
      const response = await fetch(`${API_BASE_URL}/api/import/extract-features`, {
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
      return result
    } catch (err) {
      setState(prev => ({
        ...prev,
        step: 'error',
        error: err instanceof Error ? err.message : 'Feature extraction failed',
      }))
      return null
    }
  }, [state.projectPath])

  const createFeatures = useCallback(async (projectName: string) => {
    if (!state.selectedFeatures.length) return

    setState(prev => ({ ...prev, step: 'creating', error: null }))

    try {
      const features = state.selectedFeatures.map(f => ({
        category: f.category,
        name: f.name,
        description: f.description,
        steps: f.steps,
      }))

      const response = await fetch(`${API_BASE_URL}/api/import/create-features`, {
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
    } catch (err) {
      setState(prev => ({
        ...prev,
        step: 'error',
        error: err instanceof Error ? err.message : 'Feature creation failed',
      }))
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
