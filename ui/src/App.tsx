import { useState, useEffect, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useProjects, useProject, useFeatures, useAgentStatus, useSetupStatus } from './hooks/useProjects'
import { useProjectWebSocket } from './hooks/useWebSocket'
import { useFeatureSound } from './hooks/useFeatureSound'
import { useCelebration } from './hooks/useCelebration'

const STORAGE_KEY = 'autonomous-coder-selected-project'
import { ProjectSelector } from './components/ProjectSelector'
import { KanbanBoard } from './components/KanbanBoard'
import { AgentControl } from './components/AgentControl'
import { ProgressDashboard } from './components/ProgressDashboard'
import { SetupWizard } from './components/SetupWizard'
import { AddFeatureForm } from './components/AddFeatureForm'
import { FeatureModal } from './components/FeatureModal'
import { StagedBacklogPanel } from './components/StagedBacklogPanel'
import { ExpandProjectModal } from './components/ExpandProjectModal'
import { DebugLogViewer } from './components/DebugLogViewer'
import { AgentThought } from './components/AgentThought'
import { AssistantFAB } from './components/AssistantFAB'
import { AssistantPanel } from './components/AssistantPanel'
import { AgentStatusGrid } from './components/AgentStatusGrid'
import { SettingsModal, type RunSettings } from './components/SettingsModal'
import { SettingsPage } from './pages/SettingsPage'
import { ProjectSetupRequired } from './components/ProjectSetupRequired'
import { SpecCreationChat } from './components/SpecCreationChat'
import { KnowledgeFilesModal } from './components/KnowledgeFilesModal'
import { Plus, Loader2, FileText, Settings as SettingsIcon, Sparkles, BookOpen } from 'lucide-react'
import type { Feature } from './lib/types'
import { startAgent } from './lib/api'

function App() {
  const queryClient = useQueryClient()
  // Initialize selected project from localStorage
  const [selectedProject, setSelectedProject] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY)
    } catch {
      return null
    }
  })
  const [showAddFeature, setShowAddFeature] = useState(false)
  const [showExpandProject, setShowExpandProject] = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null)
  const [setupComplete, setSetupComplete] = useState(true) // Start optimistic
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPanelHeight, setDebugPanelHeight] = useState(288) // Default height
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [isSpecCreating, setIsSpecCreating] = useState(false)
  const [logsTab, setLogsTab] = useState<'live' | 'workers' | 'devserver' | 'terminal'>('live')
  const [showSettings, setShowSettings] = useState(false)
  const [route, setRoute] = useState<'main' | 'settings'>(() =>
    window.location.hash.startsWith('#/settings') ? 'settings' : 'main'
  )
  const [showSpecChat, setShowSpecChat] = useState(false)
  const [specInitializerStatus, setSpecInitializerStatus] = useState<'idle' | 'starting' | 'error'>('idle')
  const [specInitializerError, setSpecInitializerError] = useState<string | null>(null)
  const [specYoloSelected, setSpecYoloSelected] = useState(false)
  const [showKnowledgeModal, setShowKnowledgeModal] = useState(false)
  const [setupBannerDismissedUntil, setSetupBannerDismissedUntil] = useState<number | null>(null)

  const [yoloEnabled, setYoloEnabled] = useState(false)
  const [runSettings, setRunSettings] = useState<RunSettings>({
    mode: 'standard',
    parallelCount: 3,
    parallelPreset: 'balanced',
  })

  const { data: projects, isLoading: projectsLoading } = useProjects()
  const { data: projectDetail } = useProject(selectedProject)
  const { data: features } = useFeatures(selectedProject)
  const { data: agentStatusData } = useAgentStatus(selectedProject)
  const { data: setupStatus } = useSetupStatus()
  const wsState = useProjectWebSocket(selectedProject)
  const selectedProjectData = projects?.find((p) => p.name === selectedProject) ?? null
  const setupRequired = Boolean(
    selectedProjectData?.setup_required ?? (selectedProjectData ? !selectedProjectData.has_spec : false)
  )
  const canExpandProject = Boolean(selectedProjectData?.has_spec) && !setupRequired

  useEffect(() => {
    if (!selectedProject) {
      setSetupBannerDismissedUntil(null)
      return
    }
    try {
      const raw = localStorage.getItem(`autocoder-setup-dismissed:${selectedProject}`)
      setSetupBannerDismissedUntil(raw ? Number(raw) : null)
    } catch {
      setSetupBannerDismissedUntil(null)
    }
  }, [selectedProject])

  useEffect(() => {
    if (!selectedProject || setupRequired) return
    try {
      localStorage.removeItem(`autocoder-setup-dismissed:${selectedProject}`)
      setSetupBannerDismissedUntil(null)
    } catch {
      // ignore
    }
  }, [selectedProject, setupRequired])

  const showSetupBanner = setupRequired && (!setupBannerDismissedUntil || setupBannerDismissedUntil < Date.now())

  // Play sounds when features move between columns
  useFeatureSound(features)

  // Celebrate when all features are complete
  useCelebration(features, selectedProject)

  // Persist selected project to localStorage
  const handleSelectProject = useCallback((project: string | null) => {
    setSelectedProject(project)
    try {
      if (project) {
        localStorage.setItem(STORAGE_KEY, project)
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
    } catch {
      // localStorage not available
    }
  }, [])

  // Validate stored project exists (clear if project was deleted)
  useEffect(() => {
    if (selectedProject && projects && !projects.some(p => p.name === selectedProject)) {
      handleSelectProject(null)
    }
  }, [selectedProject, projects, handleSelectProject])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      // Esc: leave Settings page
      if (e.key === 'Escape' && route === 'settings') {
        e.preventDefault()
        window.location.hash = ''
        return
      }

      // Shortcuts below only apply on the main view
      if (route !== 'main') {
        return
      }

      // D : Toggle debug window
      if (e.key === 'd' || e.key === 'D') {
        e.preventDefault()
        setLogsTab('live')
        setDebugOpen(prev => !prev)
      }

      // N : Add new feature (when project selected)
      if ((e.key === 'n' || e.key === 'N') && selectedProject) {
        e.preventDefault()
        setShowAddFeature(true)
      }

      // A : Toggle assistant panel (when project selected)
      if ((e.key === 'a' || e.key === 'A') && selectedProject && !isSpecCreating) {
        e.preventDefault()
        setAssistantOpen(prev => !prev)
      }

      // S : Open settings
      if ((e.key === 's' || e.key === 'S') && selectedProject) {
        e.preventDefault()
        setShowSettings(true)
      }

      // K : Knowledge files
      if ((e.key === 'k' || e.key === 'K') && selectedProject) {
        e.preventDefault()
        setShowKnowledgeModal(true)
      }

      // P : Quick access to run settings (back-compat shortcut)
      if ((e.key === 'p' || e.key === 'P') && selectedProject) {
        e.preventDefault()
        setShowSettings(true)
      }

      // L : Toggle worker logs (when project selected)
      if ((e.key === 'l' || e.key === 'L') && selectedProject) {
        e.preventDefault()
        setLogsTab('workers')
        setDebugOpen(true)
      }

      // T : Toggle terminal tab
      if ((e.key === 't' || e.key === 'T') && selectedProject) {
        e.preventDefault()
        setLogsTab('terminal')
        setDebugOpen(true)
      }

      // E : Expand project (when project selected)
      if ((e.key === 'e' || e.key === 'E') && selectedProject) {
        e.preventDefault()
        setShowExpandProject(true)
      }

      // Escape : Close modals
      if (e.key === 'Escape') {
        if (showSpecChat) {
          setShowSpecChat(false)
          setIsSpecCreating(false)
          setSpecInitializerStatus('idle')
          setSpecInitializerError(null)
        } else if (showKnowledgeModal) {
          setShowKnowledgeModal(false)
        } else if (showSettings) {
          setShowSettings(false)
        } else if (assistantOpen) {
          setAssistantOpen(false)
        } else if (showAddFeature) {
          setShowAddFeature(false)
        } else if (showExpandProject) {
          setShowExpandProject(false)
        } else if (selectedFeature) {
          setSelectedFeature(null)
        } else if (debugOpen) {
          setDebugOpen(false)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedProject, showAddFeature, showExpandProject, selectedFeature, debugOpen, assistantOpen, showSettings, showSpecChat, showKnowledgeModal, route])

  // Hash-based routing (no router dependency)
  useEffect(() => {
    const onHash = () => {
      setRoute(window.location.hash.startsWith('#/settings') ? 'settings' : 'main')
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // Persist run settings locally (best-effort)
  useEffect(() => {
    try {
      localStorage.setItem('autocoder-yolo-enabled', yoloEnabled ? '1' : '0')
      localStorage.setItem('autocoder-run-mode', runSettings.mode)
      localStorage.setItem('autocoder-parallel-count', String(runSettings.parallelCount))
      localStorage.setItem('autocoder-parallel-preset', runSettings.parallelPreset)
    } catch {
      // ignore
    }
  }, [yoloEnabled, runSettings])

  // Load persisted run settings on first mount
  useEffect(() => {
    try {
      const y = localStorage.getItem('autocoder-yolo-enabled')
      const mode = localStorage.getItem('autocoder-run-mode') as RunSettings['mode'] | null
      const countRaw = localStorage.getItem('autocoder-parallel-count')
      const preset = localStorage.getItem('autocoder-parallel-preset') as RunSettings['parallelPreset'] | null

      const count = countRaw ? Number(countRaw) : NaN

      if (y === '1') setYoloEnabled(true)
      setRunSettings((prev) => ({
        mode: mode === 'parallel' || mode === 'standard' ? mode : prev.mode,
        parallelCount: Number.isFinite(count) ? Math.max(1, Math.min(5, count)) : prev.parallelCount,
        parallelPreset: preset ?? prev.parallelPreset,
      }))
    } catch {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Combine WebSocket progress with feature data
  const progress = wsState.progress.total > 0 ? wsState.progress : {
    passing: features?.done.length ?? 0,
    total: (features?.pending.length ?? 0) + (features?.in_progress.length ?? 0) + (features?.done.length ?? 0),
    percentage: 0,
  }

  if (progress.total > 0 && progress.percentage === 0) {
    progress.percentage = Math.round((progress.passing / progress.total) * 100 * 10) / 10
  }

  const handleSpecComplete = async (_specPath: string, yoloMode: boolean = false) => {
    if (!selectedProject) return
    setSpecYoloSelected(yoloMode)
    setSpecInitializerStatus('starting')
    setSpecInitializerError(null)
    try {
      await startAgent(selectedProject, { yolo_mode: yoloMode })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['project', selectedProject] })
      setSpecInitializerStatus('idle')
      setTimeout(() => {
        setShowSpecChat(false)
        setIsSpecCreating(false)
      }, 500)
    } catch (err: any) {
      setSpecInitializerStatus('error')
      setSpecInitializerError(err instanceof Error ? err.message : String(err))
    }
  }

  const handleSpecRetry = () => {
    setSpecInitializerError(null)
    setSpecInitializerStatus('idle')
    handleSpecComplete('', specYoloSelected)
  }

  const closeSpecChat = () => {
    setShowSpecChat(false)
    setIsSpecCreating(false)
    setSpecInitializerStatus('idle')
    setSpecInitializerError(null)
  }

  if (!setupComplete) {
    return <SetupWizard onComplete={() => setSetupComplete(true)} />
  }

  return (
    <div className="min-h-screen bg-[var(--color-neo-bg)]">
      {/* Header */}
      <header className="bg-[var(--color-neo-text)] text-white border-b-4 border-[var(--color-neo-border)]">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Logo and Title */}
            <h1 className="font-display text-2xl font-bold tracking-tight uppercase">
              Autonomous Coder
            </h1>

            {/* Controls */}
            <div className="flex items-center gap-4">
              {route === 'settings' ? (
                <button
                  onClick={() => {
                    window.location.hash = ''
                  }}
                  className="neo-btn text-sm bg-white text-[var(--color-neo-text)] flex items-center gap-2"
                  title="Back"
                >
                  <span className="hidden sm:inline">Back</span>
                  <span className="font-mono text-xs">Esc</span>
                </button>
              ) : (
                <ProjectSelector
                  projects={projects ?? []}
                  selectedProject={selectedProject}
                  onSelectProject={handleSelectProject}
                  isLoading={projectsLoading}
                  onSpecCreatingChange={(v) => setIsSpecCreating(v)}
                />
              )}

              {selectedProject && route === 'main' && (
                <>
                  {setupStatus?.glm_mode || setupStatus?.custom_api ? (
                    <span
                      className={`neo-badge ${setupStatus?.glm_mode ? 'bg-purple-600 text-white' : 'bg-indigo-600 text-white'}`}
                      title={setupStatus?.glm_mode ? 'GLM / custom Anthropic-compatible endpoint enabled' : 'Custom API endpoint enabled'}
                    >
                      {setupStatus?.glm_mode ? 'GLM' : 'ALT API'}
                    </span>
                  ) : null}
                  <button
                    onClick={() => setShowAddFeature(true)}
                    className="neo-btn neo-btn-primary text-sm flex items-center gap-2"
                    title="Press N"
                    aria-label="Add feature"
                  >
                    <Plus size={18} />
                    <span className="hidden sm:inline">Add Feature</span>
                    <kbd className="hidden md:inline ml-1.5 px-1.5 py-0.5 text-xs bg-black/20 rounded font-mono">
                      N
                    </kbd>
                  </button>

                  <button
                    onClick={() => setShowExpandProject(true)}
                    disabled={!canExpandProject}
                    className={`neo-btn text-sm flex items-center gap-2 ${
                      canExpandProject
                        ? 'bg-[var(--color-neo-progress)] text-[var(--color-neo-text)]'
                        : 'bg-white/60 text-[var(--color-neo-text-secondary)] cursor-not-allowed'
                    }`}
                    title={canExpandProject ? 'Expand Project (Press E)' : 'Create a spec first to expand'}
                    aria-label="Expand project"
                  >
                    <Sparkles size={18} />
                    <span className="hidden sm:inline">Expand</span>
                    <kbd className="hidden md:inline ml-1.5 px-1.5 py-0.5 text-xs bg-black/20 rounded font-mono">
                      E
                    </kbd>
                  </button>

                  <button
                    onClick={() => {
                      setShowSettings(true)
                    }}
                    className="neo-btn text-sm bg-[var(--color-neo-accent)] text-white flex items-center gap-2"
                    title="Settings (Press S)"
                    aria-label="Settings"
                  >
                    <SettingsIcon size={18} />
                    <span className="hidden sm:inline">Settings</span>
                    <kbd className="hidden md:inline ml-1.5 px-1.5 py-0.5 text-xs bg-black/20 rounded font-mono">
                      S
                    </kbd>
                  </button>

                  <button
                    onClick={() => setShowKnowledgeModal(true)}
                    className="neo-btn text-sm bg-[var(--color-neo-card)] text-[var(--color-neo-text)] flex items-center gap-2"
                    title="Knowledge Files (Press K)"
                    aria-label="Knowledge files"
                  >
                    <BookOpen size={18} />
                    <span className="hidden sm:inline">Knowledge</span>
                    <kbd className="hidden md:inline ml-1.5 px-1.5 py-0.5 text-xs bg-black/20 rounded font-mono">
                      K
                    </kbd>
                  </button>

                  <button
                    onClick={() => {
                      setLogsTab('workers')
                      setDebugOpen(true)
                    }}
                    className="neo-btn text-sm bg-[var(--color-neo-bg)] text-[var(--color-neo-text)] px-3"
                    title="Worker Logs (Press L)"
                  >
                    <FileText size={18} />
                    <span className="sr-only">Logs</span>
                  </button>

                  <AgentControl
                    projectName={selectedProject}
                    status={wsState.agentStatus}
                    yoloMode={agentStatusData?.yolo_mode ?? false}
                    parallelMode={agentStatusData?.parallel_mode ?? false}
                    parallelCount={agentStatusData?.parallel_count ?? null}
                    modelPreset={agentStatusData?.model_preset ?? null}
                    yoloEnabled={yoloEnabled}
                    onToggleYolo={() => {
                      setYoloEnabled((prev) => {
                        const next = !prev
                        if (next) {
                          setRunSettings((s) => ({ ...s, mode: 'standard' }))
                        }
                        return next
                      })
                    }}
                    runMode={runSettings.mode}
                    parallelCountSetting={runSettings.parallelCount}
                    parallelPresetSetting={runSettings.parallelPreset}
                  />
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main
        className="max-w-7xl mx-auto px-4 py-8"
        style={{ paddingBottom: debugOpen ? debugPanelHeight + 32 : undefined }}
      >
        {route === 'settings' ? (
          <div className="max-w-6xl mx-auto">
            {selectedProject ? (
              <SettingsPage
                initialTab={
                  window.location.hash === '#/settings/advanced'
                    ? 'advanced'
                    : window.location.hash === '#/settings/models'
                      ? 'models'
                      : window.location.hash === '#/settings/generate'
                        ? 'generate'
                        : window.location.hash === '#/settings/config'
                          ? 'config'
                          : window.location.hash === '#/settings/diagnostics'
                            ? 'diagnostics'
                        : 'run'
                }
                projectName={selectedProject}
                yoloEnabled={yoloEnabled}
                runSettings={runSettings}
                onChangeRunSettings={(next) => setRunSettings(next)}
                onClose={() => (window.location.hash = '')}
              />
            ) : (
              <div className="neo-card p-6">
                <div className="font-display font-bold uppercase mb-2">Select a project</div>
                <div className="text-sm text-[var(--color-neo-text-secondary)]">
                  Settings are project-scoped. Go back and pick a project first.
                </div>
              </div>
            )}
          </div>
        ) : !selectedProject ? (
          <div className="neo-empty-state mt-12">
            <h2 className="font-display text-2xl font-bold mb-2">
              Welcome to Autonomous Coder
            </h2>
            <p className="text-[var(--color-neo-text-secondary)] mb-4">
              Select a project from the dropdown above or create a new one to get started.
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {showSetupBanner && selectedProject && (
              <ProjectSetupRequired
                projectName={selectedProject}
                promptsDir={projectDetail?.prompts_dir ?? ''}
                onCreateSpec={() => {
                  setShowSpecChat(true)
                  setIsSpecCreating(true)
                }}
                onOpenSettings={() => {
                  window.location.hash = '#/settings/generate'
                }}
                onDismiss={() => {
                  if (!selectedProject) return
                  const until = Date.now() + 24 * 60 * 60 * 1000
                  setSetupBannerDismissedUntil(until)
                  try {
                    localStorage.setItem(`autocoder-setup-dismissed:${selectedProject}`, String(until))
                  } catch {
                    // ignore
                  }
                }}
              />
            )}
            {/* Progress Dashboard */}
            <ProgressDashboard
              passing={progress.passing}
              total={progress.total}
              percentage={progress.percentage}
              isConnected={wsState.isConnected}
            />

            {/* Agent Status Grid - show when parallel agents are running */}
            {selectedProject && <AgentStatusGrid projectName={selectedProject} />}

            {/* Agent Thought - shows latest agent narrative */}
            <AgentThought
              logs={wsState.logs}
              agentStatus={wsState.agentStatus}
            />

            {/* Initializing Features State - show when agent is running but no features yet */}
            {features &&
             features.pending.length === 0 &&
             features.in_progress.length === 0 &&
             features.done.length === 0 &&
             (features.staged?.length ?? 0) === 0 &&
             wsState.agentStatus === 'running' && (
              <div className="neo-card p-8 text-center">
                <Loader2 size={32} className="animate-spin mx-auto mb-4 text-[var(--color-neo-progress)]" />
                <h3 className="font-display font-bold text-xl mb-2">
                  Initializing Features...
                </h3>
                <p className="text-[var(--color-neo-text-secondary)]">
                  The agent is reading your spec and creating features. This may take a moment.
                </p>
              </div>
            )}

            {selectedProject && features && (features.staged?.length ?? 0) > 0 && (
              <StagedBacklogPanel projectName={selectedProject} stagedCount={features.staged.length} />
            )}

            {/* Kanban Board */}
            <KanbanBoard
              features={features}
              onFeatureClick={setSelectedFeature}
            />
          </div>
        )}
      </main>

      {/* Add Feature Modal */}
      {showAddFeature && selectedProject && (
        <AddFeatureForm
          projectName={selectedProject}
          onClose={() => setShowAddFeature(false)}
        />
      )}

      {/* Spec Creation Modal (existing project) */}
      {showSpecChat && selectedProject && (
        <div className="fixed inset-0 z-50 bg-[var(--color-neo-bg)]">
          <SpecCreationChat
            projectName={selectedProject}
            onComplete={handleSpecComplete}
            onCancel={closeSpecChat}
            onExitToProject={closeSpecChat}
            initializerStatus={specInitializerStatus}
            initializerError={specInitializerError}
            onRetryInitializer={handleSpecRetry}
          />
        </div>
      )}

      {/* Expand Project Modal */}
      {showExpandProject && selectedProject && (
        <ExpandProjectModal
          isOpen={showExpandProject}
          projectName={selectedProject}
          onClose={() => setShowExpandProject(false)}
          onFeaturesAdded={() => {
            queryClient.invalidateQueries({ queryKey: ['features', selectedProject] })
          }}
        />
      )}

      {/* Feature Detail Modal */}
      {selectedFeature && selectedProject && (
        <FeatureModal
          feature={selectedFeature}
          projectName={selectedProject}
          onClose={() => setSelectedFeature(null)}
        />
      )}

      {/* Settings Modal */}
      {showSettings && selectedProject && (
        <SettingsModal
          onClose={() => setShowSettings(false)}
          yoloEnabled={yoloEnabled}
          settings={runSettings}
          onChange={(next) => setRunSettings(next)}
          onOpenSettingsPage={() => {
            setShowSettings(false)
            window.location.hash = '#/settings'
          }}
        />
      )}

      {/* Knowledge Files Modal */}
      {showKnowledgeModal && selectedProject && (
        <KnowledgeFilesModal
          projectName={selectedProject}
          isOpen={showKnowledgeModal}
          onClose={() => setShowKnowledgeModal(false)}
        />
      )}

      {/* Debug Log Viewer - fixed to bottom */}
      {selectedProject && (
        <DebugLogViewer
          logs={wsState.logs}
          isOpen={debugOpen}
          onToggle={() => setDebugOpen(!debugOpen)}
          onClear={wsState.clearLogs}
          onHeightChange={setDebugPanelHeight}
          projectName={selectedProject}
          openTab={logsTab}
        />
      )}

      {/* Assistant FAB and Panel */}
      {selectedProject && !isSpecCreating && (
        <>
          <AssistantFAB
            onClick={() => setAssistantOpen(!assistantOpen)}
            isOpen={assistantOpen}
          />
          <AssistantPanel
            projectName={selectedProject}
            isOpen={assistantOpen}
            onClose={() => setAssistantOpen(false)}
          />
        </>
      )}
    </div>
  )
}

export default App
