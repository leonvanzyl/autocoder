/**
 * Import Project Modal Component
 *
 * Multi-step wizard for importing existing projects:
 * 1. Select project folder
 * 2. Analyze and detect tech stack
 * 3. Extract features from codebase
 * 4. Review and select features to import
 * 5. Create features in database
 */

import { useState } from 'react'
import {
  X,
  Folder,
  Search,
  Layers,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
  ArrowLeft,
  Code,
  Database,
  Server,
  Layout,
  CheckSquare,
  Square,
  ChevronDown,
  ChevronRight,
  Trash2,
} from 'lucide-react'
import { useImportProject } from '../hooks/useImportProject'
import { useCreateProject, useDeleteProject, useProjects } from '../hooks/useProjects'
import { FolderBrowser } from './FolderBrowser'
import { ConfirmDialog } from './ConfirmDialog'

type Step = 'folder' | 'analyzing' | 'detected' | 'features' | 'register' | 'complete' | 'error'

interface ImportProjectModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectImported: (projectName: string) => void
}

export function ImportProjectModal({
  isOpen,
  onClose,
  onProjectImported,
}: ImportProjectModalProps) {
  const [step, setStep] = useState<Step>('folder')
  const [projectName, setProjectName] = useState('')
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [projectToDelete, setProjectToDelete] = useState<string | null>(null)

  // Fetch existing projects to check for conflicts
  const { data: existingProjects } = useProjects()

  const {
    state,
    analyze,
    extractFeatures,
    createFeatures,
    toggleFeature,
    selectAllFeatures,
    deselectAllFeatures,
    reset,
  } = useImportProject()

  const createProject = useCreateProject()
  const deleteProject = useDeleteProject()

  if (!isOpen) return null

  const handleFolderSelect = async (path: string) => {
    setStep('analyzing')
    await analyze(path)
    if (state.step !== 'error') {
      setStep('detected')
    }
  }

  const handleExtractFeatures = async () => {
    const result = await extractFeatures()
    if (result) {
      setStep('features')
      // Expand all categories by default using the returned result
      if (result && result.by_category) {
        setExpandedCategories(new Set(Object.keys(result.by_category)))
      }
    }
  }

  const handleContinueToRegister = () => {
    // Generate default project name from path
    const pathParts = state.projectPath?.split(/[/\\]/) || []
    const defaultName = pathParts[pathParts.length - 1] || 'imported-project'
    setProjectName(defaultName.replace(/[^a-zA-Z0-9_-]/g, '-'))
    setStep('register')
  }

  const handleRegisterAndCreate = async () => {
    if (!projectName.trim() || !state.projectPath) return

    setRegisterError(null)
    const trimmedName = projectName.trim()
    let projectCreated = false

    try {
      // First register the project
      await createProject.mutateAsync({
        name: trimmedName,
        path: state.projectPath,
        specMethod: 'manual',
      })
      projectCreated = true

      // Then create features
      await createFeatures(trimmedName)

      if (state.step !== 'error') {
        setStep('complete')
        setTimeout(() => {
          onProjectImported(trimmedName)
          handleClose()
        }, 1500)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to register project'

      if (projectCreated) {
        // Project was created but features failed to import
        setRegisterError(`Project created but feature import failed: ${errorMessage}`)
        setStep('error')
        // Optionally attempt cleanup - uncomment to enable automatic deletion
        // try {
        //   await deleteProject.mutateAsync(trimmedName)
        // } catch (deleteErr) {
        //   console.error('Failed to cleanup project after feature import error:', deleteErr)
        // }
      } else {
        // Project creation itself failed
        setRegisterError(errorMessage)
        setStep('error')
      }
    }
  }

  const handleClose = () => {
    setStep('folder')
    setProjectName('')
    setExpandedCategories(new Set())
    setRegisterError(null)
    reset()
    onClose()
  }

  const handleDeleteExistingProject = async () => {
    if (!projectToDelete) return


    try {
      await deleteProject.mutateAsync(projectToDelete)
      setShowDeleteConfirm(false)
      setProjectToDelete(null)
      
      // Refresh the import step to reflect the deletion
      if (step === 'register') {
        // Stay on register step so user can now create the project with same name
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete project'
      setRegisterError(`Delete failed: ${errorMessage}`)
      setShowDeleteConfirm(false)
      setProjectToDelete(null)
    }
  }

  const handleBack = () => {
    if (step === 'detected') {
      setStep('folder')
      reset()
    } else if (step === 'features') {
      setStep('detected')
    } else if (step === 'register') {
      setStep('features')
    }
  }

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  const getStackIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'frontend':
        return <Layout size={16} className="text-[var(--color-neo-progress)]" />
      case 'backend':
        return <Server size={16} className="text-[var(--color-neo-done)]" />
      case 'database':
        return <Database size={16} className="text-[var(--color-neo-pending)]" />
      default:
        return <Code size={16} className="text-[var(--color-neo-text-secondary)]" />
    }
  }

  // Folder selection step
  if (step === 'folder') {
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-3xl max-h-[85vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <div className="flex items-center gap-3">
              <Folder size={24} className="text-[var(--color-neo-progress)]" />
              <div>
                <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
                  Import Existing Project
                </h2>
                <p className="text-sm text-[var(--color-neo-text-secondary)]">
                  Select the folder containing your existing project
                </p>
              </div>
            </div>
            <button onClick={handleClose} className="neo-btn neo-btn-ghost p-2">
              <X size={20} />
            </button>
          </div>

          <div className="flex-1 overflow-hidden">
            <FolderBrowser
              onSelect={handleFolderSelect}
              onCancel={handleClose}
            />
          </div>
        </div>
      </div>
    )
  }

  // Analyzing step
  if (step === 'analyzing' || state.step === 'analyzing') {
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
              Analyzing Project
            </h2>
            <button onClick={handleClose} className="neo-btn neo-btn-ghost p-2">
              <X size={20} />
            </button>
          </div>

          <div className="p-6 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-neo-progress)] border-3 border-[var(--color-neo-border)] mb-4 animate-pulse">
              <Search size={32} className="text-[var(--color-neo-text-on-bright)]" />
            </div>
            <h3 className="font-bold text-lg mb-2">Detecting Tech Stack</h3>
            <p className="text-[var(--color-neo-text-secondary)] mb-4">
              Scanning your project for frameworks, routes, and components...
            </p>
            <Loader2 size={24} className="animate-spin mx-auto text-[var(--color-neo-progress)]" />
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (state.step === 'error') {
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
              Error
            </h2>
            <button onClick={handleClose} className="neo-btn neo-btn-ghost p-2">
              <X size={20} />
            </button>
          </div>

          <div className="p-6 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-neo-error-bg)] border-3 border-[var(--color-neo-error-border)] mb-4">
              <AlertCircle size={32} className="text-[var(--color-neo-error-text)]" />
            </div>
            <h3 className="font-bold text-lg mb-2">Analysis Failed</h3>
            <p className="text-[var(--color-neo-error-text)] mb-4">{state.error}</p>
            <button onClick={handleBack} className="neo-btn neo-btn-secondary">
              <ArrowLeft size={16} />
              Try Again
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Detection results step
  if (step === 'detected' && state.analyzeResult) {
    const result = state.analyzeResult
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-2xl max-h-[85vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <div className="flex items-center gap-3">
              <Layers size={24} className="text-[var(--color-neo-done)]" />
              <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
                Stack Detected
              </h2>
            </div>
            <button onClick={handleClose} className="neo-btn neo-btn-ghost p-2">
              <X size={20} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            {/* Summary */}
            <div className="mb-6 p-4 bg-[var(--color-neo-bg-secondary)] border-3 border-[var(--color-neo-border)]">
              <p className="text-sm text-[var(--color-neo-text-secondary)]">{result.summary}</p>
            </div>

            {/* Detected Stacks */}
            <h3 className="font-bold mb-3">Detected Technologies</h3>
            <div className="grid grid-cols-2 gap-3 mb-6">
              {result.detected_stacks.map((stack, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 p-3 neo-card"
                >
                  {getStackIcon(stack.category)}
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-sm truncate">{stack.name}</div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">
                      {stack.category}
                    </div>
                  </div>
                  <div className="text-xs font-mono bg-[var(--color-neo-done)] text-white px-2 py-0.5">
                    {Math.round(stack.confidence * 100)}%
                  </div>
                </div>
              ))}
            </div>

            {/* Stats */}
            <h3 className="font-bold mb-3">Codebase Analysis</h3>
            <div className="grid grid-cols-3 gap-3 mb-6">
              <div className="text-center p-3 neo-card">
                <div className="text-2xl font-bold text-[var(--color-neo-progress)]">
                  {result.routes_count}
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">Routes</div>
              </div>
              <div className="text-center p-3 neo-card">
                <div className="text-2xl font-bold text-[var(--color-neo-done)]">
                  {result.endpoints_count}
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">Endpoints</div>
              </div>
              <div className="text-center p-3 neo-card">
                <div className="text-2xl font-bold text-[var(--color-neo-pending)]">
                  {result.components_count}
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">Components</div>
              </div>
            </div>
          </div>

          <div className="flex justify-between p-4 border-t-3 border-[var(--color-neo-border)]">
            <button onClick={handleBack} className="neo-btn neo-btn-ghost">
              <ArrowLeft size={16} />
              Back
            </button>
            <button
              onClick={handleExtractFeatures}
              className="neo-btn neo-btn-primary"
              disabled={state.step === 'extracting'}
            >
              {state.step === 'extracting' ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Extracting...
                </>
              ) : (
                <>
                  Extract Features
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Features review step
  if (step === 'features' && state.featuresResult) {
    const result = state.featuresResult
    const categories = Object.keys(result.by_category)

    // Group features by category
    const featuresByCategory: Record<string, typeof result.features> = {}
    result.features.forEach(f => {
      if (!featuresByCategory[f.category]) {
        featuresByCategory[f.category] = []
      }
      featuresByCategory[f.category].push(f)
    })

    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-3xl max-h-[85vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <div className="flex items-center gap-3">
              <CheckSquare size={24} className="text-[var(--color-neo-done)]" />
              <div>
                <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
                  Review Features
                </h2>
                <p className="text-sm text-[var(--color-neo-text-secondary)]">
                  {state.selectedFeatures.length} of {result.count} features selected
                </p>
              </div>
            </div>
            <button onClick={handleClose} className="neo-btn neo-btn-ghost p-2">
              <X size={20} />
            </button>
          </div>

          {/* Selection controls */}
          <div className="flex items-center gap-2 p-4 border-b border-[var(--color-neo-border)]">
            <button
              onClick={selectAllFeatures}
              className="neo-btn neo-btn-ghost text-sm"
            >
              Select All
            </button>
            <button
              onClick={deselectAllFeatures}
              className="neo-btn neo-btn-ghost text-sm"
            >
              Deselect All
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {categories.map(category => (
              <div key={category} className="mb-4">
                <button
                  onClick={() => toggleCategory(category)}
                  className="flex items-center gap-2 w-full p-2 hover:bg-[var(--color-neo-bg-secondary)] transition-colors"
                >
                  {expandedCategories.has(category) ? (
                    <ChevronDown size={16} />
                  ) : (
                    <ChevronRight size={16} />
                  )}
                  <span className="font-bold">{category}</span>
                  <span className="text-sm text-[var(--color-neo-text-secondary)]">
                    ({featuresByCategory[category]?.length || 0})
                  </span>
                </button>

                {expandedCategories.has(category) && (
                  <div className="ml-6 mt-2 space-y-2">
                    {featuresByCategory[category]?.map((feature, i) => {
                      const isSelected = state.selectedFeatures.some(
                        f => f.name === feature.name && f.category === feature.category
                      )
                      return (
                        <div
                          key={i}
                          onClick={() => toggleFeature(feature)}
                          className={`
                            flex items-start gap-3 p-3 cursor-pointer transition-all
                            border-2 border-[var(--color-neo-border)]
                            ${isSelected
                              ? 'bg-[var(--color-neo-done-light)] border-[var(--color-neo-done)]'
                              : 'bg-white hover:bg-[var(--color-neo-bg-secondary)]'
                            }
                          `}
                        >
                          {isSelected ? (
                            <CheckSquare size={18} className="text-[var(--color-neo-done)] flex-shrink-0 mt-0.5" />
                          ) : (
                            <Square size={18} className="text-[var(--color-neo-text-secondary)] flex-shrink-0 mt-0.5" />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-sm">{feature.name}</div>
                            <div className="text-xs text-[var(--color-neo-text-secondary)] truncate">
                              {feature.description}
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-xs px-1.5 py-0.5 bg-[var(--color-neo-bg-secondary)] border border-[var(--color-neo-border)]">
                                {feature.source_type}
                              </span>
                              {feature.source_file && (
                                <span className="text-xs text-[var(--color-neo-text-secondary)] font-mono truncate">
                                  {feature.source_file}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex justify-between p-4 border-t-3 border-[var(--color-neo-border)]">
            <button onClick={handleBack} className="neo-btn neo-btn-ghost">
              <ArrowLeft size={16} />
              Back
            </button>
            <button
              onClick={handleContinueToRegister}
              className="neo-btn neo-btn-primary"
              disabled={state.selectedFeatures.length === 0}
            >
              Continue
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Register project step
  if (step === 'register') {
    // Check if project name already exists
    const existingProject = existingProjects?.find(p => p.name === projectName)
    const nameConflict = !!existingProject


    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
              Register Project
            </h2>
            <button onClick={handleClose} className="neo-btn neo-btn-ghost p-2">
              <X size={20} />
            </button>
          </div>

          <div className="p-6">
            <div className="mb-6">
              <label className="block font-bold mb-2 text-[var(--color-neo-text)]">
                Project Name
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="my-project"
                className="neo-input"
                pattern="^[a-zA-Z0-9_-]+$"
                autoFocus
                disabled={createProject.isPending}
              />
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2">
                Use letters, numbers, hyphens, and underscores only.
              </p>
              {nameConflict && (
                <div className="mt-3 p-3 bg-[var(--color-neo-error-bg)] border-3 border-[var(--color-neo-error-border)] rounded">
                  <p className="text-sm text-[var(--color-neo-error-text)] font-bold mb-1">
                    Project name already exists!
                  </p>
                  <p className="text-xs text-[var(--color-neo-error-text)] mb-2">
                    A project named "{projectName}" is already registered.
                  </p>
                  <button
                    onClick={() => {
                      setProjectToDelete(projectName)
                      setShowDeleteConfirm(true)
                    }}
                    className="neo-btn neo-btn-destructive text-sm"
                    disabled={deleteProject.isPending}
                  >
                    {deleteProject.isPending ? (
                      <>
                        <Loader2 size={14} className="animate-spin mr-1" />
                        Deleting...
                      </>
                    ) : (
                      <>
                        <Trash2 size={14} className="mr-1" />
                        Delete Existing Project
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>

            <div className="mb-6 p-4 bg-[var(--color-neo-bg-secondary)] border-3 border-[var(--color-neo-border)]">
              <div className="text-sm">
                <div className="flex justify-between mb-1">
                  <span>Features to create:</span>
                  <span className="font-bold">{state.selectedFeatures.length}</span>
                </div>
                <div className="flex justify-between">
                  <span>Project path:</span>
                  <span className="font-mono text-xs truncate max-w-[200px]">
                    {state.projectPath}
                  </span>
                </div>
              </div>
            </div>

            {(registerError || state.error) && (
              <div className="mb-4 p-3 bg-[var(--color-neo-error-bg)] text-[var(--color-neo-error-text)] text-sm border-3 border-[var(--color-neo-error-border)]">
                {registerError || state.error}
              </div>
            )}

            <div className="flex justify-between">
              <button onClick={handleBack} className="neo-btn neo-btn-ghost">
                <ArrowLeft size={16} />
                Back
              </button>
              <button
                onClick={handleRegisterAndCreate}
                className="neo-btn neo-btn-primary"
                disabled={!projectName.trim() || createProject.isPending || state.step === 'creating'}
              >
                {createProject.isPending || state.step === 'creating' ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    Import Project
                    <CheckCircle2 size={16} />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Complete step
  if (step === 'complete') {
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
              Import Complete
            </h2>
          </div>

          <div className="p-6 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-neo-done)] border-3 border-[var(--color-neo-border)] mb-4">
              <CheckCircle2 size={32} className="text-[var(--color-neo-text-on-bright)]" />
            </div>
            <h3 className="font-display font-bold text-xl mb-2">{projectName}</h3>
            <p className="text-[var(--color-neo-text-secondary)] mb-2">
              Project imported successfully!
            </p>
            <p className="text-sm text-[var(--color-neo-text-secondary)]">
              {state.createResult?.created} features created
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Redirecting...</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Delete confirmation dialog
  if (showDeleteConfirm) {
    return (
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title="Delete Existing Project"
        message={`Are you sure you want to delete "${projectToDelete}"? This will:

• Remove the project from the registry
• Disconnect all WebSocket connections
• Stop any running agent processes
• Delete all database files (features.db, assistant.db)
• Stop any dev servers
• Preserve the project files on disk`}
        confirmLabel="Delete Project"
        cancelLabel="Cancel"
        variant="danger"
        isLoading={deleteProject.isPending}
        onConfirm={handleDeleteExistingProject}
        onCancel={() => {
          setShowDeleteConfirm(false)
          setProjectToDelete(null)
        }}
      />
    )
  }

  return null
}
