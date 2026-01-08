/**
 * New Project Modal Component
 *
 * Multi-step modal for creating new projects:
 * 1. Enter project name
 * 2. Select project folder
 * 3. Choose spec method (Claude, manual, or import existing)
 * 4a. If Claude: Show SpecCreationChat
 * 4b. If manual: Create project and close
 * 4c. If import: Select existing folder and import
 */

import { useState } from 'react'
import { X, Bot, FileEdit, ArrowRight, ArrowLeft, Loader2, CheckCircle2, Folder, FolderInput } from 'lucide-react'
import { useCreateProject, useImportProject } from '../hooks/useProjects'
import { SpecCreationChat } from './SpecCreationChat'
import { FolderBrowser } from './FolderBrowser'
import { startAgent } from '../lib/api'

type InitializerStatus = 'idle' | 'starting' | 'error'

type Step = 'name' | 'folder' | 'method' | 'chat' | 'complete' | 'import-folder' | 'import-name'
type SpecMethod = 'claude' | 'manual' | 'import'

interface NewProjectModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectCreated: (projectName: string) => void
}

export function NewProjectModal({
  isOpen,
  onClose,
  onProjectCreated,
}: NewProjectModalProps) {
  const [step, setStep] = useState<Step>('name')
  const [projectName, setProjectName] = useState('')
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [_specMethod, setSpecMethod] = useState<SpecMethod | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [initializerStatus, setInitializerStatus] = useState<InitializerStatus>('idle')
  const [initializerError, setInitializerError] = useState<string | null>(null)
  const [yoloModeSelected, setYoloModeSelected] = useState(false)

  // Suppress unused variable warning - specMethod may be used in future
  void _specMethod

  const createProject = useCreateProject()
  const importProject = useImportProject()

  // State for import flow
  const [importPath, setImportPath] = useState<string | null>(null)

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
    setStep('folder')
  }

  const handleFolderSelect = (path: string) => {
    // Append project name to the selected path
    const fullPath = path.endsWith('/') ? `${path}${projectName.trim()}` : `${path}/${projectName.trim()}`
    setProjectPath(fullPath)
    setStep('method')
  }

  const handleFolderCancel = () => {
    setStep('name')
  }

  const handleMethodSelect = async (method: SpecMethod) => {
    setSpecMethod(method)

    if (method === 'import') {
      // Switch to import flow
      setStep('import-folder')
      return
    }

    if (!projectPath) {
      setError('Please select a project folder first')
      setStep('folder')
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
        setStep('complete')
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
        setStep('chat')
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to create project')
      }
    }
  }

  const handleImportFolderSelect = (path: string) => {
    setImportPath(path)
    // Extract folder name as default project name (handle both / and \ for cross-platform)
    const folderName = path.split(/[/\\]/).pop() || ''
    // Sanitize folder name for project name
    const sanitized = folderName
      .replace(/[^a-zA-Z0-9_-]/g, '-')
      .replace(/-+/g, '-')  // Collapse multiple hyphens
      .replace(/^-+|-+$/g, '')  // Trim leading/trailing hyphens
      .toLowerCase()
    setProjectName(sanitized || 'imported-project')
    setStep('import-name')
  }

  const handleImportFolderCancel = () => {
    setStep('method')
    setImportPath(null)
  }

  const handleImportSubmit = async (e: React.FormEvent) => {
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

    if (!importPath) {
      setError('No folder selected')
      return
    }

    setError(null)

    try {
      const project = await importProject.mutateAsync({
        name: trimmed,
        path: importPath,
      })
      setStep('complete')
      setTimeout(() => {
        onProjectCreated(project.name)
        handleClose()
      }, 1500)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to import project')
    }
  }

  const handleSpecComplete = async (_specPath: string, yoloMode: boolean = false) => {
    // Save yoloMode for retry
    setYoloModeSelected(yoloMode)
    // Auto-start the initializer agent
    setInitializerStatus('starting')
    try {
      await startAgent(projectName.trim(), yoloMode)
      // Success - navigate to project
      setStep('complete')
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
    setStep('method')
    setSpecMethod(null)
  }

  const handleExitToProject = () => {
    // Exit chat and go directly to project - user can start agent manually
    onProjectCreated(projectName.trim())
    handleClose()
  }

  const handleClose = () => {
    setStep('name')
    setProjectName('')
    setProjectPath(null)
    setSpecMethod(null)
    setError(null)
    setInitializerStatus('idle')
    setInitializerError(null)
    setYoloModeSelected(false)
    setImportPath(null)
    onClose()
  }

  const handleBack = () => {
    if (step === 'method') {
      setStep('folder')
      setSpecMethod(null)
    } else if (step === 'folder') {
      setStep('name')
      setProjectPath(null)
    } else if (step === 'import-name') {
      setStep('import-folder')
      setError(null)
    } else if (step === 'import-folder') {
      setStep('method')
      setImportPath(null)
    }
  }

  // Full-screen chat view
  if (step === 'chat') {
    return (
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
      </div>
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
                <h2 className="font-display font-bold text-xl text-[#1a1a1a]">
                  Select Project Location
                </h2>
                <p className="text-sm text-[#4a4a4a]">
                  A folder named <span className="font-bold font-mono">{projectName}</span> will be created inside the selected directory
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

  // Import folder selection step
  if (step === 'import-folder') {
    return (
      <div className="neo-modal-backdrop" onClick={handleClose}>
        <div
          className="neo-modal w-full max-w-3xl max-h-[85vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
            <div className="flex items-center gap-3">
              <FolderInput size={24} className="text-[var(--color-neo-accent)]" />
              <div>
                <h2 className="font-display font-bold text-xl text-[#1a1a1a]">
                  Import Existing Project
                </h2>
                <p className="text-sm text-[#4a4a4a]">
                  Select the folder containing your existing project
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
              onSelect={handleImportFolderSelect}
              onCancel={handleImportFolderCancel}
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
          <h2 className="font-display font-bold text-xl text-[#1a1a1a]">
            {step === 'name' && 'Create New Project'}
            {step === 'method' && 'Choose Setup Method'}
            {step === 'import-name' && 'Confirm Project Name'}
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
          {/* Step 1: Project Name */}
          {step === 'name' && (
            <form onSubmit={handleNameSubmit}>
              <div className="mb-6">
                <label className="block font-bold mb-2 text-[#1a1a1a]">
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
                <div className="mb-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
                  {error}
                </div>
              )}

              <div className="flex justify-end">
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
                  className={`
                    w-full text-left p-4
                    border-3 border-[var(--color-neo-border)]
                    bg-white
                    shadow-[4px_4px_0px_rgba(0,0,0,1)]
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                  `}
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-[var(--color-neo-progress)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                      <Bot size={24} className="text-white" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg text-[#1a1a1a]">Create with Claude</span>
                        <span className="neo-badge bg-[var(--color-neo-done)] text-xs">
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
                  className={`
                    w-full text-left p-4
                    border-3 border-[var(--color-neo-border)]
                    bg-white
                    shadow-[4px_4px_0px_rgba(0,0,0,1)]
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                  `}
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-[var(--color-neo-pending)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                      <FileEdit size={24} />
                    </div>
                    <div className="flex-1">
                      <span className="font-bold text-lg text-[#1a1a1a]">Edit Templates Manually</span>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Edit the template files directly. Best for developers who want full control.
                      </p>
                    </div>
                  </div>
                </button>

                {/* Divider */}
                <div className="flex items-center gap-4 py-2">
                  <div className="flex-1 h-[2px] bg-[var(--color-neo-border)]"></div>
                  <span className="text-sm text-[var(--color-neo-text-secondary)]">or</span>
                  <div className="flex-1 h-[2px] bg-[var(--color-neo-border)]"></div>
                </div>

                {/* Import Existing option */}
                <button
                  onClick={() => handleMethodSelect('import')}
                  disabled={createProject.isPending}
                  className={`
                    w-full text-left p-4
                    border-3 border-[var(--color-neo-border)]
                    bg-white
                    shadow-[4px_4px_0px_rgba(0,0,0,1)]
                    hover:translate-x-[-2px] hover:translate-y-[-2px]
                    hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
                    transition-all duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                  `}
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-[var(--color-neo-accent)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                      <FolderInput size={24} className="text-white" />
                    </div>
                    <div className="flex-1">
                      <span className="font-bold text-lg text-[#1a1a1a]">Import Existing Project</span>
                      <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                        Import an existing codebase. Claude will analyze it and create features for management.
                      </p>
                    </div>
                  </div>
                </button>
              </div>

              {error && (
                <div className="mt-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
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

          {/* Import Name Step */}
          {step === 'import-name' && (
            <form onSubmit={handleImportSubmit}>
              <div className="mb-4 p-3 bg-[var(--color-neo-bg)] border-2 border-[var(--color-neo-border)]">
                <p className="text-sm text-[var(--color-neo-text-secondary)]">
                  Importing from: <span className="font-mono font-bold">{importPath}</span>
                </p>
              </div>

              <div className="mb-6">
                <label className="block font-bold mb-2 text-[#1a1a1a]">
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
                />
                <p className="text-sm text-[var(--color-neo-text-secondary)] mt-2">
                  Use letters, numbers, hyphens, and underscores only.
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-[var(--color-neo-danger)] text-white text-sm border-2 border-[var(--color-neo-border)]">
                  {error}
                </div>
              )}

              {importProject.isPending && (
                <div className="mb-4 flex items-center justify-center gap-2 text-[var(--color-neo-text-secondary)]">
                  <Loader2 size={16} className="animate-spin" />
                  <span>Importing project...</span>
                </div>
              )}

              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={handleBack}
                  className="neo-btn neo-btn-ghost"
                  disabled={importProject.isPending}
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  type="submit"
                  className="neo-btn neo-btn-primary"
                  disabled={!projectName.trim() || importProject.isPending}
                >
                  Import Project
                  <ArrowRight size={16} />
                </button>
              </div>
            </form>
          )}

          {/* Step 3: Complete */}
          {step === 'complete' && (
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-neo-done)] border-3 border-[var(--color-neo-border)] shadow-[4px_4px_0px_rgba(0,0,0,1)] mb-4">
                <CheckCircle2 size={32} />
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
