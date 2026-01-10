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
import { X, Bot, FileEdit, ArrowRight, ArrowLeft, Loader2, CheckCircle2, Folder, Check } from 'lucide-react'
import { useCreateProject } from '../hooks/useProjects'
import { SpecCreationChat } from './SpecCreationChat'
import { FolderBrowser } from './FolderBrowser'
import { startAgent } from '../lib/api'
import type {
  TechStackConfig,
  FrameworkChoice,
  TestingFramework,
  FrameworkOption,
  DatabaseOption,
  TestingOption,
} from '../lib/types'

type InitializerStatus = 'idle' | 'starting' | 'error'

type Step = 'name' | 'folder' | 'techStack' | 'techOptions' | 'method' | 'chat' | 'complete'

// Framework options for tech stack selection
const FRAMEWORK_OPTIONS: FrameworkOption[] = [
  {
    id: 'react_node',
    name: 'React + Node.js',
    description: 'Full-stack JavaScript with Express backend',
    icon: 'react',
    isDefault: true,
  },
  {
    id: 'laravel_react',
    name: 'Laravel + React',
    description: 'PHP backend with React (Inertia.js)',
    icon: 'laravel',
  },
  {
    id: 'laravel_vue',
    name: 'Laravel + Vue',
    description: 'PHP backend with Vue (Inertia.js)',
    icon: 'laravel',
  },
  {
    id: 'laravel_livewire',
    name: 'Laravel + Livewire',
    description: 'PHP full-stack with reactive components',
    icon: 'laravel',
  },
  {
    id: 'laravel_api',
    name: 'Laravel API Only',
    description: 'PHP API backend without frontend',
    icon: 'laravel',
  },
]

// Database options
const DATABASE_OPTIONS: DatabaseOption[] = [
  { id: 'sqlite', name: 'SQLite', description: 'File-based, zero config', isDefault: true },
  { id: 'mysql', name: 'MySQL', description: 'Popular relational database' },
  { id: 'postgresql', name: 'PostgreSQL', description: 'Advanced open-source database' },
  { id: 'mariadb', name: 'MariaDB', description: 'MySQL fork with enhancements' },
]

// Testing framework options
const TESTING_OPTIONS: TestingOption[] = [
  { id: 'vitest', name: 'Vitest', description: 'Fast Vite-native testing', forFramework: 'nodejs', isDefault: true },
  { id: 'jest', name: 'Jest', description: 'Feature-rich testing framework', forFramework: 'nodejs' },
  { id: 'pest', name: 'Pest', description: 'Elegant PHP testing', forFramework: 'laravel', isDefault: true },
  { id: 'phpunit', name: 'PHPUnit', description: 'Standard PHP testing', forFramework: 'laravel' },
]

// Helper to check if framework is Laravel-based
function isLaravelFramework(framework: FrameworkChoice): boolean {
  return framework.startsWith('laravel')
}

// Get default testing framework based on stack
function getDefaultTesting(framework: FrameworkChoice): TestingFramework {
  return isLaravelFramework(framework) ? 'pest' : 'vitest'
}

type SpecMethod = 'claude' | 'manual'

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
  const [techStack, setTechStack] = useState<TechStackConfig>({
    framework: 'react_node',
    database: 'sqlite',
    testing: 'vitest',
  })

  // Suppress unused variable warning - specMethod may be used in future
  void _specMethod

  // Get testing options for current framework
  const availableTestingOptions = TESTING_OPTIONS.filter(
    opt => opt.forFramework === (isLaravelFramework(techStack.framework) ? 'laravel' : 'nodejs')
  )

  const createProject = useCreateProject()

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
    setStep('techStack')
  }

  const handleFrameworkSelect = (framework: FrameworkChoice) => {
    // Update framework and set default testing for that framework
    setTechStack(prev => ({
      ...prev,
      framework,
      testing: getDefaultTesting(framework),
    }))
    setStep('techOptions')
  }

  const handleTechOptionsConfirm = () => {
    setStep('method')
  }

  const handleFolderCancel = () => {
    setStep('name')
  }

  const handleMethodSelect = async (method: SpecMethod) => {
    setSpecMethod(method)

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
          techStack,
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
          techStack,
        })
        setStep('chat')
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
    setTechStack({
      framework: 'react_node',
      database: 'sqlite',
      testing: 'vitest',
    })
    onClose()
  }

  const handleBack = () => {
    if (step === 'method') {
      setStep('techOptions')
      setSpecMethod(null)
    } else if (step === 'techOptions') {
      setStep('techStack')
    } else if (step === 'techStack') {
      setStep('folder')
    } else if (step === 'folder') {
      setStep('name')
      setProjectPath(null)
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
            {step === 'techStack' && 'Choose Tech Stack'}
            {step === 'techOptions' && 'Configure Options'}
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

          {/* Step 2: Tech Stack Selection */}
          {step === 'techStack' && (
            <div>
              <p className="text-[var(--color-neo-text-secondary)] mb-6">
                Select the framework for your project
              </p>

              <div className="grid grid-cols-1 gap-3">
                {FRAMEWORK_OPTIONS.map((option) => {
                  const isSelected = techStack.framework === option.id
                  const isLaravel = option.icon === 'laravel'

                  return (
                    <button
                      key={option.id}
                      onClick={() => handleFrameworkSelect(option.id)}
                      className={`
                        w-full text-left p-4
                        border-3 border-[var(--color-neo-border)]
                        shadow-[4px_4px_0px_rgba(0,0,0,1)]
                        hover:translate-x-[-2px] hover:translate-y-[-2px]
                        hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
                        transition-all duration-150
                        ${isSelected ? 'bg-[var(--color-neo-progress)]' : 'bg-white'}
                      `}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`
                          w-10 h-10 flex items-center justify-center
                          border-2 border-[var(--color-neo-border)]
                          shadow-[2px_2px_0px_rgba(0,0,0,1)]
                          font-bold text-lg
                          ${isLaravel ? 'bg-[#FF2D20] text-white' : 'bg-[#61DAFB] text-[#1a1a1a]'}
                        `}>
                          {isLaravel ? 'L' : 'R'}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className={`font-bold ${isSelected ? 'text-white' : 'text-[#1a1a1a]'}`}>
                              {option.name}
                            </span>
                            {option.isDefault && (
                              <span className="neo-badge bg-[var(--color-neo-done)] text-xs">
                                Default
                              </span>
                            )}
                            {isSelected && (
                              <Check size={18} className="text-white ml-auto" />
                            )}
                          </div>
                          <p className={`text-sm mt-0.5 ${isSelected ? 'text-white/80' : 'text-[var(--color-neo-text-secondary)]'}`}>
                            {option.description}
                          </p>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>

              <div className="flex justify-start mt-6">
                <button
                  onClick={handleBack}
                  className="neo-btn neo-btn-ghost"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Tech Options (Database & Testing) */}
          {step === 'techOptions' && (
            <div>
              <p className="text-[var(--color-neo-text-secondary)] mb-6">
                Configure database and testing options
              </p>

              {/* Database Selection */}
              <div className="mb-6">
                <label className="block font-bold mb-2 text-[#1a1a1a]">
                  Database
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {DATABASE_OPTIONS.map((option) => {
                    const isSelected = techStack.database === option.id
                    return (
                      <button
                        key={option.id}
                        onClick={() => setTechStack(prev => ({ ...prev, database: option.id }))}
                        className={`
                          p-3 text-left
                          border-2 border-[var(--color-neo-border)]
                          shadow-[2px_2px_0px_rgba(0,0,0,1)]
                          transition-all duration-150
                          ${isSelected
                            ? 'bg-[var(--color-neo-progress)] text-white'
                            : 'bg-white hover:bg-gray-50'
                          }
                        `}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`font-bold text-sm ${isSelected ? 'text-white' : 'text-[#1a1a1a]'}`}>{option.name}</span>
                          {isSelected && <Check size={14} />}
                        </div>
                        <p className={`text-xs mt-0.5 ${isSelected ? 'text-white/80' : 'text-[var(--color-neo-text-secondary)]'}`}>
                          {option.description}
                        </p>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Testing Framework Selection */}
              <div className="mb-6">
                <label className="block font-bold mb-2 text-[#1a1a1a]">
                  Testing Framework
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {availableTestingOptions.map((option) => {
                    const isSelected = techStack.testing === option.id
                    return (
                      <button
                        key={option.id}
                        onClick={() => setTechStack(prev => ({ ...prev, testing: option.id }))}
                        className={`
                          p-3 text-left
                          border-2 border-[var(--color-neo-border)]
                          shadow-[2px_2px_0px_rgba(0,0,0,1)]
                          transition-all duration-150
                          ${isSelected
                            ? 'bg-[var(--color-neo-progress)] text-white'
                            : 'bg-white hover:bg-gray-50'
                          }
                        `}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`font-bold text-sm ${isSelected ? 'text-white' : 'text-[#1a1a1a]'}`}>{option.name}</span>
                          {isSelected && <Check size={14} />}
                        </div>
                        <p className={`text-xs mt-0.5 ${isSelected ? 'text-white/80' : 'text-[var(--color-neo-text-secondary)]'}`}>
                          {option.description}
                        </p>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="flex justify-between mt-6">
                <button
                  onClick={handleBack}
                  className="neo-btn neo-btn-ghost"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  onClick={handleTechOptionsConfirm}
                  className="neo-btn neo-btn-primary"
                >
                  Next
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* Step 4: Spec Method */}
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
