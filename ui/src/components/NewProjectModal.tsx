/**
 * New Project Modal Component
 *
 * Multi-step modal for creating new projects:
 * 1. Enter project name
 * 2. Select project folder
 * 3. Choose spec method (Claude or manual)
 * 4a. If Claude: Show SpecCreationChat
 * 4b. If manual: Create project and close
 */

import { useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Bot, FileEdit, ArrowRight, ArrowLeft, Loader2, CheckCircle2, Folder, Download } from 'lucide-react'
import { useCreateProject } from '../hooks/useProjects'
import { SpecCreationChat } from './SpecCreationChat'
import { FolderBrowser } from './FolderBrowser'
import { ImportProjectModal } from './ImportProjectModal'
import { startAgent } from '../lib/api'

type InitializerStatus = 'idle' | 'starting' | 'error'

type Step = 'choose' | 'name' | 'folder' | 'method' | 'chat' | 'complete' | 'import'
type ProjectType = 'new' | 'import'
type SpecMethod = 'claude' | 'manual'

interface NewProjectModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectCreated: (projectName: string) => void
  onStepChange?: (step: Step) => void
}

export function NewProjectModal({
  isOpen,
  onClose,
  onProjectCreated,
  onStepChange,
}: NewProjectModalProps) {
  const [step, setStep] = useState<Step>('choose')
  const [, setProjectType] = useState<ProjectType | null>(null)
  const [projectName, setProjectName] = useState('')
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [, setSpecMethod] = useState<SpecMethod | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [initializerStatus, setInitializerStatus] = useState<InitializerStatus>('idle')
  const [initializerError, setInitializerError] = useState<string | null>(null)
  const [yoloModeSelected, setYoloModeSelected] = useState(false)

  const createProject = useCreateProject()

  // Wrapper to notify parent of step changes
  const changeStep = (newStep: Step) => {
    setStep(newStep)
    onStepChange?.(newStep)
  }

  if (!isOpen) return null

  const handleNameSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = projectName.trim()

    if (!trimmed) {
      setError('Please enter a project name')
      return
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      setError('Project name can only contain letters, numbers, hyphens, and underscores')
      return
    }

    setError(null)
    changeStep('folder')
  }

  const handleFolderSelect = (path: string) => {
    setProjectPath(path)  // Use selected path directly - no subfolder creation
    changeStep('method')
  }

  const handleFolderCancel = () => {
    changeStep('name')
  }

  const handleMethodSelect = async (method: SpecMethod) => {
    setSpecMethod(method)

    if (!projectPath) {
      setError('Please select a project folder first')
      changeStep('folder')
      return
    }

    if (method === 'manual') {
      // Create project immediately with manual method
      try {
        const project = await createProject.mutateAsync({
          name: projectName.trim(),
          path: projectPath,
          specMethod: 'manual',
        })
        changeStep('complete')
        setTimeout(() => {
          onProjectCreated(project.name)
          handleClose()
        }, 1500)
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to create project')
      }
    } else {
      // Create project then show chat
      try {
        await createProject.mutateAsync({
          name: projectName.trim(),
          path: projectPath,
          specMethod: 'claude',
        })
        changeStep('chat')
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to create project')
      }
    }
  }

  const handleSpecComplete = async (_specPath: string, yoloMode: boolean = false) => {
    // Save yoloMode for retry
    setYoloModeSelected(yoloMode)
    // Auto-start the initializer agent
    setInitializerStatus('starting')
    try {
      // Use default concurrency of 3 to match AgentControl.tsx default
      await startAgent(projectName.trim(), {
        yoloMode,
        maxConcurrency: 3,
      })
      // Success - navigate to project
      changeStep('complete')
      setTimeout(() => {
        onProjectCreated(projectName.trim())
        handleClose()
      }, 1500)
    } catch (err) {
      setInitializerStatus('error')
      setInitializerError(err instanceof Error ? err.message : 'Failed to start agent')
    }
  }

  const handleRetryInitializer = () => {
    setInitializerError(null)
    setInitializerStatus('idle')
    handleSpecComplete('', yoloModeSelected)
  }

  const handleChatCancel = () => {
    // Go back to method selection but keep the project
    changeStep('method')
    setSpecMethod(null)
  }

  const handleExitToProject = () => {
    // Exit chat and go directly to project - user can start agent manually
    onProjectCreated(projectName.trim())
    handleClose()
  }

  const handleClose = () => {
    changeStep('choose')
    setProjectType(null)
    setProjectName('')
    setProjectPath(null)
    setSpecMethod(null)
    setError(null)
    setInitializerStatus('idle')
    setInitializerError(null)
    setYoloModeSelected(false)
    onClose()
  }

  const handleBack = () => {
    if (step === 'method') {
      changeStep('folder')
      setSpecMethod(null)
    } else if (step === 'folder') {
      changeStep('name')
      setProjectPath(null)
    } else if (step === 'name') {
      changeStep('choose')
      setProjectType(null)
    }
  }

  const handleProjectTypeSelect = (type: ProjectType) => {
    setProjectType(type)
    if (type === 'new') {
      changeStep('name')
    } else {
      changeStep('import')
    }
  }

  const handleImportComplete = (importedProjectName: string) => {
    onProjectCreated(importedProjectName)
    handleClose()
  }

  // Import project view
  if (step === 'import') {
    return (
      <ImportProjectModal
        isOpen={true}
        onClose={handleClose}
        onProjectImported={handleImportComplete}
      />
    )
  }

  // Full-screen chat view - use portal to render at body level
  if (step === 'chat') {
    return createPortal(
      <div className="fixed inset-0 z-50 bg-[var(--color-neo-bg)]">
        <SpecCreationChat
          projectName={projectName.trim()}
          onComplete={handleSpecComplete}
          onCancel={handleChatCancel}
          onExitToProject={handleExitToProject}
          initializerStatus={initializerStatus}
          initializerError={initializerError}
          onRetryInitializer={handleRetryInitializer}
        />
      </div>,
      document.body
    )
  }

  // Folder step uses larger modal
  if (step === 'folder') {
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-3xl max-h-[85vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <div className="flex items-center gap-3">
              <Folder size={24} className="text-[var(--color-neo-progress)]" />
              <div>
                <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
                  Select Project Location
                </h2>
                <p className="text-sm text-[var(--color-neo-text-secondary)]">
                  Select the folder to use for project <span className="font-bold font-mono">{projectName}</span>. Create a new folder or choose an existing one.
                </p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="neo-btn neo-btn-ghost p-2"
            >
              <X size={20} />
            </button>
          </div>

          {/* Folder Browser */}
          <div className="flex-1 overflow-hidden">
            <FolderBrowser
              onSelect={handleFolderSelect}
              onCancel={handleFolderCancel}
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="neo-modal-backdrop" onClick={handleClose}>
      <div
        className="neo-modal w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
          <h2 className="font-display font-bold text-xl text-[var(--color-neo-text)]">
            {step === 'choose' && 'New Project'}
            {step === 'name' && 'Create New Project'}
            {step === 'method' && 'Choose Setup Method'}
            {step === 'complete' && 'Project Created!'}
          </h2>
          <button
            onClick={handleClose}
            className="neo-btn neo-btn-ghost p-2"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Step 0: Choose project type */}
          {step === 'choose' && (
            <div>
              <p className="text-[var(--color-neo-text-secondary)] mb-6">
                What would you like to do?
              </p>

              <div className="space-y-4">
                {/* New project option */}
                <button
                  onClick={() => handleProjectTypeSelect('new')}
                  className="
                    w-full text-left p-4
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    transition-all duration-150
                    neo-card
                  "
                >
                  <div className="flex items-start gap-4">
                    <div
                      className="p-2 bg-[var(--color-neo-done)] border-2 border-[var(--color-neo-border)]"
                      style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                    >
                      <Bot size={24} className="text-[var(--color-neo-text-on-bright)]" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg text-[var(--color-neo-text)]">Create New Project</span>
                        <span className="neo-badge bg-[var(--color-neo-done)] text-[var(--color-neo-text-on-bright)] text-xs">
                          Recommended
                        </span>
                      </div>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Start from scratch with an interactive conversation to define your app.
                      </p>
                    </div>
                  </div>
                </button>

                {/* Import existing option */}
                <button
                  onClick={() => handleProjectTypeSelect('import')}
                  className="
                    w-full text-left p-4
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    transition-all duration-150
                    neo-card
                  "
                >
                  <div className="flex items-start gap-4">
                    <div
                      className="p-2 bg-[var(--color-neo-progress)] border-2 border-[var(--color-neo-border)]"
                      style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                    >
                      <Download size={24} className="text-[var(--color-neo-text-on-bright)]" />
                    </div>
                    <div className="flex-1">
                      <span className="font-bold text-lg text-[var(--color-neo-text)]">Import Existing Project</span>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Analyze an existing codebase and extract features automatically.
                      </p>
                    </div>
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* Step 1: Project Name */}
          {step === 'name' && (
            <form onSubmit={handleNameSubmit}>
              <div className="mb-6">
                <label className="block font-bold mb-2 text-[var(--color-neo-text)]">
                  Project Name
                </label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="my-awesome-app"
                  className="neo-input"
                  pattern="^[a-zA-Z0-9_-]+$"
                  autoFocus
                />
                <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2">
                  Use letters, numbers, hyphens, and underscores only.
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-[var(--color-neo-error-bg)] text-[var(--color-neo-error-text)] text-sm border-3 border-[var(--color-neo-error-border)]">
                  {error}
                </div>
              )}

              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={handleBack}
                  className="neo-btn neo-btn-ghost"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  type="submit"
                  className="neo-btn neo-btn-primary"
                  disabled={!projectName.trim()}
                >
                  Next
                  <ArrowRight size={16} />
                </button>
              </div>
            </form>
          )}

          {/* Step 2: Spec Method */}
          {step === 'method' && (
            <div>
              <p className="text-[var(--color-neo-text-secondary)] mb-6">
                How would you like to define your project?
              </p>

              <div className="space-y-4">
                {/* Claude option */}
                <button
                  onClick={() => handleMethodSelect('claude')}
                  disabled={createProject.isPending}
                  className="
                    w-full text-left p-4
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                    neo-card
                  "
                >
                  <div className="flex items-start gap-4">
                    <div
                      className="p-2 bg-[var(--color-neo-progress)] border-2 border-[var(--color-neo-border)]"
                      style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                    >
                      <Bot size={24} className="text-[var(--color-neo-text-on-bright)]" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg text-[var(--color-neo-text)]">Create with Claude</span>
                        <span className="neo-badge bg-[var(--color-neo-done)] text-[var(--color-neo-text-on-bright)] text-xs">
                          Recommended
                        </span>
                      </div>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Interactive conversation to define features and generate your app specification automatically.
                      </p>
                    </div>
                  </div>
                </button>

                {/* Manual option */}
                <button
                  onClick={() => handleMethodSelect('manual')}
                  disabled={createProject.isPending}
                  className="
                    w-full text-left p-4
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                    neo-card
                  "
                >
                  <div className="flex items-start gap-4">
                    <div
                      className="p-2 bg-[var(--color-neo-pending)] border-2 border-[var(--color-neo-border)]"
                      style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                    >
                      <FileEdit size={24} className="text-[var(--color-neo-text-on-bright)]" />
                    </div>
                    <div className="flex-1">
                      <span className="font-bold text-lg text-[var(--color-neo-text)]">Edit Templates Manually</span>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Edit the template files directly. Best for developers who want full control.
                      </p>
                    </div>
                  </div>
                </button>
              </div>

              {error && (
                <div className="mt-4 p-3 bg-[var(--color-neo-error-bg)] text-[var(--color-neo-error-text)] text-sm border-3 border-[var(--color-neo-error-border)]">
                  {error}
                </div>
              )}

              {createProject.isPending && (
                <div className="mt-4 flex items-center justify-center gap-2 text-[var(--color-neo-text-secondary)]">
                  <Loader2 size={16} className="animate-spin" />
                  <span>Creating project...</span>
                </div>
              )}

              <div className="flex justify-start mt-6">
                <button
                  onClick={handleBack}
                  className="neo-btn neo-btn-ghost"
                  disabled={createProject.isPending}
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Complete */}
          {step === 'complete' && (
            <div className="text-center py-8">
              <div
                className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-neo-done)] border-3 border-[var(--color-neo-border)] mb-4"
                style={{ boxShadow: 'var(--shadow-neo-md)' }}
              >
                <CheckCircle2 size={32} className="text-[var(--color-neo-text-on-bright)]" />
              </div>
              <h3 className="font-display font-bold text-xl mb-2">
                {projectName}
              </h3>
              <p className="text-[var(--color-neo-text-secondary)]">
                Your project has been created successfully!
              </p>
              <div className="mt-4 flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                <span className="text-sm">Redirecting...</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
