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
import { X, Bot, FileEdit, ArrowRight, ArrowLeft, Loader2, CheckCircle2, Folder, Settings2 } from 'lucide-react'
import { useCreateProject, useProjects } from '../hooks/useProjects'
import { SpecCreationChat } from './SpecCreationChat'
import { FolderBrowser } from './FolderBrowser'
import { getAutocoderYaml, startAgent, updateAutocoderYaml } from '../lib/api'

type InitializerStatus = 'idle' | 'starting' | 'error'

type Step = 'name' | 'folder' | 'setup' | 'method' | 'chat' | 'complete'
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
  const [initAutocoderYaml, setInitAutocoderYaml] = useState(true)
  const [configSource, setConfigSource] = useState<'template' | 'copy'>('template')
  const [copyFromProject, setCopyFromProject] = useState('')
  const [workerProvider, setWorkerProvider] = useState<'claude' | 'codex_cli' | 'gemini_cli' | 'multi_cli'>('claude')
  const [workerPatchIterations, setWorkerPatchIterations] = useState(2)
  const [workerPatchAgents, setWorkerPatchAgents] = useState('codex,gemini')
  const [initializerProvider, setInitializerProvider] = useState<'claude' | 'codex_cli' | 'gemini_cli' | 'multi_cli'>('claude')
  const [initializerAgents, setInitializerAgents] = useState('codex,gemini')
  const [initializerSynthesizer, setInitializerSynthesizer] = useState<'none' | 'claude' | 'codex' | 'gemini'>('claude')
  const [initializerTimeoutS, setInitializerTimeoutS] = useState(300)
  const [initializerStageThreshold, setInitializerStageThreshold] = useState(120)
  const [initializerEnqueueCount, setInitializerEnqueueCount] = useState(30)

  // Suppress unused variable warning - specMethod may be used in future
  void _specMethod

  const createProject = useCreateProject()
  const projectsQ = useProjects()

  if (!isOpen) return null

  const setStepAndNotify = (next: Step) => {
    setStep(next)
    onStepChange?.(next)
  }

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
    setStepAndNotify('folder')
  }

  const handleFolderSelect = (path: string) => {
    // Append project name to the selected path
    const fullPath = path.endsWith('/') ? `${path}${projectName.trim()}` : `${path}/${projectName.trim()}`
    setProjectPath(fullPath)
    setStepAndNotify('setup')
  }

  const handleFolderCancel = () => {
    setStepAndNotify('name')
  }

  const buildAutocoderYamlTemplate = (): string => {
    const agents = workerPatchAgents
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 10)
    const agentsYaml = agents.length ? agents.join(', ') : 'codex, gemini'
    const iters = Math.max(1, Math.min(20, Math.trunc(workerPatchIterations || 2)))
    const initAgents = initializerAgents
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 10)
    const initAgentsYaml = initAgents.length ? initAgents.join(', ') : 'codex, gemini'
    return (
      `# autocoder.yaml\n` +
      `# Project-level AutoCoder defaults.\n` +
      `#\n` +
      `# If preset/commands are omitted, Gatekeeper will infer a preset and synthesize\n` +
      `# deterministic verification commands.\n` +
      `\n` +
      `worker:\n` +
      `  provider: ${workerProvider}\n` +
      `  patch_max_iterations: ${iters}\n` +
      `  patch_agents: [${agentsYaml}]\n` +
      `\n` +
      `initializer:\n` +
      `  provider: ${initializerProvider}\n` +
      `  agents: [${initAgentsYaml}]\n` +
      `  synthesizer: ${initializerSynthesizer}\n` +
      `  timeout_s: ${Math.max(30, Math.min(3600, Math.trunc(initializerTimeoutS || 300)))}\n` +
      `  stage_threshold: ${Math.max(0, Math.trunc(initializerStageThreshold || 0))}\n` +
      `  enqueue_count: ${Math.max(0, Math.trunc(initializerEnqueueCount || 0))}\n`
    )
  }

  const maybeInitProjectConfig = async (name: string) => {
    if (!initAutocoderYaml) return

    try {
      if (configSource === 'copy' && copyFromProject) {
        const other = await getAutocoderYaml(copyFromProject)
        const content = (other.content || '').trim()
        if (content) {
          await updateAutocoderYaml(name, content.endsWith('\n') ? content : content + '\n')
          return
        }
      }
      await updateAutocoderYaml(name, buildAutocoderYamlTemplate())
    } catch (e: unknown) {
      // Non-fatal: project can still run without autocoder.yaml.
      setError(e instanceof Error ? e.message : 'Failed to initialize autocoder.yaml')
    }
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
        })
        await maybeInitProjectConfig(project.name)
        setStepAndNotify('complete')
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
        const project = await createProject.mutateAsync({
          name: projectName.trim(),
          path: projectPath,
          specMethod: 'claude',
        })
        await maybeInitProjectConfig(project.name)
        setStepAndNotify('chat')
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
      await startAgent(projectName.trim(), { yolo_mode: yoloMode })
      // Success - navigate to project
      setStepAndNotify('complete')
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
    setStepAndNotify('method')
    setSpecMethod(null)
  }

  const handleExitToProject = () => {
    // Exit chat and go directly to project - user can start agent manually
    onProjectCreated(projectName.trim())
    handleClose()
  }

  const handleClose = () => {
    setStepAndNotify('name')
    setProjectName('')
    setProjectPath(null)
    setSpecMethod(null)
    setError(null)
    setInitializerStatus('idle')
    setInitializerError(null)
    setYoloModeSelected(false)
    setInitAutocoderYaml(true)
    setConfigSource('template')
    setCopyFromProject('')
    setWorkerProvider('claude')
    setWorkerPatchIterations(2)
    setWorkerPatchAgents('codex,gemini')
    setInitializerProvider('claude')
    setInitializerAgents('codex,gemini')
    setInitializerSynthesizer('claude')
    setInitializerTimeoutS(300)
    setInitializerStageThreshold(120)
    setInitializerEnqueueCount(30)
    onClose()
  }

  const handleBack = () => {
    if (step === 'method') {
      setStep('setup')
      setSpecMethod(null)
    } else if (step === 'setup') {
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
            {step === 'name' && 'Create New Project'}
            {step === 'setup' && 'Project Setup'}
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
          {step === 'setup' && (
            <div>
              <p className="text-[var(--color-neo-text-secondary)] mb-6">
                Optionally configure project defaults (you can edit later).
              </p>

              <div className="neo-card p-4 mb-6">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-[var(--color-neo-accent)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                    <Settings2 size={20} className="text-white" />
                  </div>
                  <div className="flex-1">
                    <div className="font-display font-bold uppercase">Setup Wizard</div>
                    <div className="text-sm text-[var(--color-neo-text-secondary)]">
                      Creates <span className="font-mono">autocoder.yaml</span> with per-project defaults (recommended for parallel runs).
                    </div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-1 gap-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Create autocoder.yaml</span>
                    <input
                      type="checkbox"
                      checked={initAutocoderYaml}
                      onChange={(e) => setInitAutocoderYaml(e.target.checked)}
                      className="w-5 h-5"
                    />
                  </label>

                  {initAutocoderYaml && (
                    <>
                      <div className="neo-card p-3">
                        <div className="text-xs font-display font-bold uppercase mb-2">Source</div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            className={`neo-btn text-sm ${configSource === 'template' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
                            onClick={() => setConfigSource('template')}
                            type="button"
                          >
                            Template
                          </button>
                          <button
                            className={`neo-btn text-sm ${configSource === 'copy' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
                            onClick={() => setConfigSource('copy')}
                            type="button"
                          >
                            Copy from project
                          </button>
                        </div>
                      </div>

                      {configSource === 'copy' ? (
                        <div className="neo-card p-3">
                          <div className="text-xs font-display font-bold uppercase mb-2">Copy From</div>
                          <select
                            value={copyFromProject}
                            onChange={(e) => setCopyFromProject(e.target.value)}
                            className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                            disabled={projectsQ.isLoading || projectsQ.isFetching}
                          >
                            <option value="">Select a project…</option>
                            {(projectsQ.data || [])
                              .map((p) => p.name)
                              .filter((n) => n)
                              .sort()
                              .map((name) => (
                                <option key={name} value={name}>
                                  {name}
                                </option>
                              ))}
                          </select>
                          <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                            Copies the entire <span className="font-mono">autocoder.yaml</span> (commands/review/worker).
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="neo-card p-3">
                            <div className="text-xs font-display font-bold uppercase mb-2">Worker</div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              <div>
                                <div className="text-xs font-display font-bold uppercase mb-1">Provider</div>
                                <select
                                  value={workerProvider}
                                  onChange={(e) => setWorkerProvider(e.target.value as any)}
                                  className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                                >
                                  <option value="claude">claude (Claude Agent SDK)</option>
                                  <option value="codex_cli">codex_cli (patch worker)</option>
                                  <option value="gemini_cli">gemini_cli (patch worker)</option>
                                  <option value="multi_cli">multi_cli (patch worker)</option>
                                </select>
                              </div>

                              <div>
                                <div className="text-xs font-display font-bold uppercase mb-1">Patch iterations</div>
                                <input
                                  type="number"
                                  value={workerPatchIterations}
                                  min={1}
                                  max={20}
                                  onChange={(e) => setWorkerPatchIterations(Number(e.target.value))}
                                  className="neo-input"
                                />
                              </div>

                              {workerProvider === 'multi_cli' && (
                                <div className="md:col-span-2">
                                  <div className="text-xs font-display font-bold uppercase mb-1">Patch order (csv)</div>
                                  <input
                                    value={workerPatchAgents}
                                    onChange={(e) => setWorkerPatchAgents(e.target.value)}
                                    placeholder="codex,gemini"
                                    className="neo-input"
                                  />
                                </div>
                              )}
                            </div>
                            <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                              Gatekeeper still infers verification commands if you don’t set <span className="font-mono">preset</span>/<span className="font-mono">commands</span>.
                            </div>
                          </div>
                          <div className="neo-card p-3">
                            <div className="text-xs font-display font-bold uppercase mb-2">Initializer</div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              <div>
                                <div className="text-xs font-display font-bold uppercase mb-1">Provider</div>
                                <select
                                  value={initializerProvider}
                                  onChange={(e) => setInitializerProvider(e.target.value as any)}
                                  className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                                >
                                  <option value="claude">claude (Claude Agent SDK)</option>
                                  <option value="codex_cli">codex_cli</option>
                                  <option value="gemini_cli">gemini_cli</option>
                                  <option value="multi_cli">multi_cli</option>
                                </select>
                              </div>
                              <div>
                                <div className="text-xs font-display font-bold uppercase mb-1">Synthesizer</div>
                                <select
                                  value={initializerSynthesizer}
                                  onChange={(e) => setInitializerSynthesizer(e.target.value as any)}
                                  className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                                >
                                  <option value="claude">claude</option>
                                  <option value="none">none</option>
                                  <option value="codex">codex</option>
                                  <option value="gemini">gemini</option>
                                </select>
                              </div>
                              <div className="md:col-span-2">
                                <div className="text-xs font-display font-bold uppercase mb-1">Agents (csv)</div>
                                <input
                                  value={initializerAgents}
                                  onChange={(e) => setInitializerAgents(e.target.value)}
                                  placeholder="codex,gemini"
                                  className="neo-input"
                                />
                              </div>
                              <div>
                                <div className="text-xs font-display font-bold uppercase mb-1">Timeout (s)</div>
                                <input
                                  type="number"
                                  value={initializerTimeoutS}
                                  min={30}
                                  max={3600}
                                  onChange={(e) => setInitializerTimeoutS(Number(e.target.value))}
                                  className="neo-input"
                                />
                              </div>
                              <div>
                                <div className="text-xs font-display font-bold uppercase mb-1">Stage threshold</div>
                                <input
                                  type="number"
                                  value={initializerStageThreshold}
                                  min={0}
                                  max={100000}
                                  onChange={(e) => setInitializerStageThreshold(Number(e.target.value))}
                                  className="neo-input"
                                />
                              </div>
                              <div className="md:col-span-2">
                                <div className="text-xs font-display font-bold uppercase mb-1">Enqueue count</div>
                                <input
                                  type="number"
                                  value={initializerEnqueueCount}
                                  min={0}
                                  max={100000}
                                  onChange={(e) => setInitializerEnqueueCount(Number(e.target.value))}
                                  className="neo-input"
                                />
                              </div>
                            </div>
                            <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                              Large backlogs get staged; only the top enqueue count stays active.
                            </div>
                          </div>
                        </>
                      )}
                    </>
                  )}
                </div>
              </div>

              <div className="flex justify-between mt-6">
                <button onClick={handleBack} className="neo-btn neo-btn-ghost">
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  onClick={() => setStep('method')}
                  className="neo-btn neo-btn-primary"
                  type="button"
                  disabled={!projectPath}
                >
                  Next
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Spec Method */}
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
                    border-3 border-[var(--color-neo-border)]
                    bg-[var(--color-neo-card)]
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
                    border-3 border-[var(--color-neo-border)]
                    bg-[var(--color-neo-card)]
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

          {/* Step 4: Complete */}
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
