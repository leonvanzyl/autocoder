/**
 * New Project Modal Component
 *
 * Multi-step modal for creating new projects:
 * 1. Enter project name
 * 2. Select project folder
 * 3. Git repository setup (new/existing/clone/none)
 * 4. Choose spec method (Claude or manual)
 * 5a. If Claude: Show SpecCreationChat
 * 5b. If manual: Create project and close
 */

import { useState } from 'react'
import { Bot, FileEdit, ArrowRight, ArrowLeft, Loader2, CheckCircle2, Folder, GitBranch, Check } from 'lucide-react'
import { useCreateProject } from '../hooks/useProjects'
import { SpecCreationChat } from './SpecCreationChat'
import { FolderBrowser } from './FolderBrowser'
import { startAgent, initGitRepo } from '../lib/api'
import type { GitRepoOption } from '../lib/types'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

type InitializerStatus = 'idle' | 'starting' | 'error'

type Step = 'name' | 'folder' | 'git' | 'method' | 'chat' | 'complete'
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
  const [step, setStep] = useState<Step>('name')
  const [projectName, setProjectName] = useState('')
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [_specMethod, setSpecMethod] = useState<SpecMethod | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [initializerStatus, setInitializerStatus] = useState<InitializerStatus>('idle')
  const [initializerError, setInitializerError] = useState<string | null>(null)
  const [yoloModeSelected, setYoloModeSelected] = useState(false)
  const [gitOption, setGitOption] = useState<GitRepoOption | null>(null)
  const [isExistingRepo, setIsExistingRepo] = useState(false)
  const [gitSetupPending, setGitSetupPending] = useState(false)

  // Suppress unused variable warning - specMethod may be used in future
  void _specMethod

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

  const handleFolderSelect = async (path: string) => {
    setProjectPath(path)
    setError(null)

    // Check if folder is already a git repo
    try {
      // We need to temporarily use a placeholder project name to check git status
      // The folder might already be a git repo
      const response = await fetch(`/api/filesystem/check-git?path=${encodeURIComponent(path)}`)
      if (response.ok) {
        const data = await response.json()
        if (data.isRepo) {
          setIsExistingRepo(true)
          setGitOption('existing')
        } else {
          setIsExistingRepo(false)
          setGitOption(null)
        }
      }
    } catch {
      // Ignore errors, assume not a git repo
      setIsExistingRepo(false)
      setGitOption(null)
    }

    changeStep('git')
  }

  const handleFolderCancel = () => {
    changeStep('name')
  }

  const handleGitSelect = async (option: GitRepoOption) => {
    setGitOption(option)
    setError(null)

    if (option === 'existing' || option === 'none') {
      // No git setup needed, proceed to method
      changeStep('method')
      return
    }

    if (option === 'new') {
      // Initialize git repo in the project directory
      setGitSetupPending(true)
      try {
        // Create project first to register it
        await createProject.mutateAsync({
          name: projectName.trim(),
          path: projectPath!,
          specMethod: 'manual', // We'll update this in method step
        })

        // Initialize git
        const result = await initGitRepo(projectName.trim(), { initialBranch: 'main' })
        if (!result.success) {
          setError(result.message || 'Failed to initialize git repository')
          setGitSetupPending(false)
          return
        }

        setGitSetupPending(false)
        changeStep('method')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initialize git')
        setGitSetupPending(false)
      }
      return
    }

    // Clone option would need additional UI for URL input
    // For now, proceed to method
    changeStep('method')
  }

  const handleGitBack = () => {
    changeStep('folder')
    setGitOption(null)
    setIsExistingRepo(false)
  }

  const handleMethodSelect = async (method: SpecMethod) => {
    setSpecMethod(method)

    if (!projectPath) {
      setError('Please select a project folder first')
      changeStep('folder')
      return
    }

    // Check if project was already created (in git step with 'new' option)
    const projectAlreadyCreated = gitOption === 'new'

    if (method === 'manual') {
      if (projectAlreadyCreated) {
        // Project already exists, just navigate
        changeStep('complete')
        setTimeout(() => {
          onProjectCreated(projectName.trim())
          handleClose()
        }, 1500)
      } else {
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
      }
    } else {
      if (projectAlreadyCreated) {
        // Project already exists, just show chat
        changeStep('chat')
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
    changeStep('name')
    setProjectName('')
    setProjectPath(null)
    setSpecMethod(null)
    setError(null)
    setInitializerStatus('idle')
    setInitializerError(null)
    setYoloModeSelected(false)
    setGitOption(null)
    setIsExistingRepo(false)
    setGitSetupPending(false)
    onClose()
  }

  const handleBack = () => {
    if (step === 'method') {
      changeStep('git')
      setSpecMethod(null)
    } else if (step === 'git') {
      changeStep('folder')
      setGitOption(null)
      setIsExistingRepo(false)
    } else if (step === 'folder') {
      changeStep('name')
      setProjectPath(null)
    }
  }

  // Full-screen chat view
  if (step === 'chat') {
    return (
      <div className="fixed inset-0 z-50 bg-background">
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
      <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col p-0">
          {/* Header */}
          <DialogHeader className="p-6 pb-4 border-b">
            <div className="flex items-center gap-3">
              <Folder size={24} className="text-primary" />
              <div>
                <DialogTitle>Select Project Location</DialogTitle>
                <DialogDescription>
                  Select the folder to use for project <span className="font-semibold font-mono">{projectName}</span>. Create a new folder or choose an existing one.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          {/* Folder Browser */}
          <div className="flex-1 overflow-hidden">
            <FolderBrowser
              onSelect={handleFolderSelect}
              onCancel={handleFolderCancel}
            />
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {step === 'name' && 'Create New Project'}
            {step === 'git' && 'Git Repository'}
            {step === 'method' && 'Choose Setup Method'}
            {step === 'complete' && 'Project Created!'}
          </DialogTitle>
        </DialogHeader>

        {/* Step 1: Project Name */}
        {step === 'name' && (
          <form onSubmit={handleNameSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="project-name">Project Name</Label>
              <Input
                id="project-name"
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="my-awesome-app"
                pattern="^[a-zA-Z0-9_-]+$"
                autoFocus
              />
              <p className="text-sm text-muted-foreground">
                Use letters, numbers, hyphens, and underscores only.
              </p>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <DialogFooter>
              <Button type="submit" disabled={!projectName.trim()}>
                Next
                <ArrowRight size={16} />
              </Button>
            </DialogFooter>
          </form>
        )}

        {/* Step 2: Git Repository */}
        {step === 'git' && (
          <div className="space-y-4">
            <DialogDescription>
              Set up version control for your project.
            </DialogDescription>

            <div className="space-y-3">
              {/* Existing repo (auto-detected) */}
              {isExistingRepo && (
                <Card
                  className="cursor-pointer hover:border-primary transition-colors border-primary"
                  onClick={() => !gitSetupPending && handleGitSelect('existing')}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <div className="p-2 bg-primary/10 rounded-lg">
                        <Check size={24} className="text-primary" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">Use Existing Repository</span>
                          <Badge variant="secondary">Detected</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          This folder is already a git repository. Autocoder will work in a separate branch.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* New repo */}
              {!isExistingRepo && (
                <Card
                  className="cursor-pointer hover:border-primary transition-colors"
                  onClick={() => !gitSetupPending && handleGitSelect('new')}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <div className="p-2 bg-primary/10 rounded-lg">
                        <GitBranch size={24} className="text-primary" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">Initialize New Repository</span>
                          <Badge>Recommended</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          Create a new git repository. Autocoder will work in a separate branch for safety.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* No git */}
              <Card
                className="cursor-pointer hover:border-primary transition-colors"
                onClick={() => !gitSetupPending && handleGitSelect('none')}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-secondary rounded-lg">
                      <Folder size={24} className="text-secondary-foreground" />
                    </div>
                    <div className="flex-1">
                      <span className="font-semibold">Skip Git Setup</span>
                      <p className="text-sm text-muted-foreground mt-1">
                        Work without version control. Changes will be made directly to the folder.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {gitSetupPending && (
              <div className="flex items-center justify-center gap-2 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span>Initializing repository...</span>
              </div>
            )}

            <DialogFooter className="sm:justify-start">
              <Button
                variant="ghost"
                onClick={handleGitBack}
                disabled={gitSetupPending}
              >
                <ArrowLeft size={16} />
                Back
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Spec Method */}
        {step === 'method' && (
          <div className="space-y-4">
            <DialogDescription>
              How would you like to define your project?
            </DialogDescription>

            <div className="space-y-3">
              {/* Claude option */}
              <Card
                className="cursor-pointer hover:border-primary transition-colors"
                onClick={() => !createProject.isPending && handleMethodSelect('claude')}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-primary/10 rounded-lg">
                      <Bot size={24} className="text-primary" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">Create with Claude</span>
                        <Badge>Recommended</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        Interactive conversation to define features and generate your app specification automatically.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Manual option */}
              <Card
                className="cursor-pointer hover:border-primary transition-colors"
                onClick={() => !createProject.isPending && handleMethodSelect('manual')}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-secondary rounded-lg">
                      <FileEdit size={24} className="text-secondary-foreground" />
                    </div>
                    <div className="flex-1">
                      <span className="font-semibold">Edit Templates Manually</span>
                      <p className="text-sm text-muted-foreground mt-1">
                        Edit the template files directly. Best for developers who want full control.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {createProject.isPending && (
              <div className="flex items-center justify-center gap-2 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span>Creating project...</span>
              </div>
            )}

            <DialogFooter className="sm:justify-start">
              <Button
                variant="ghost"
                onClick={handleBack}
                disabled={createProject.isPending}
              >
                <ArrowLeft size={16} />
                Back
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Complete */}
        {step === 'complete' && (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-full mb-4">
              <CheckCircle2 size={32} className="text-primary" />
            </div>
            <h3 className="font-semibold text-xl mb-2">{projectName}</h3>
            <p className="text-muted-foreground">
              Your project has been created successfully!
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm text-muted-foreground">Redirecting...</span>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
