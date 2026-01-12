import { useState, useEffect, useCallback } from 'react'
import { useProjects, useFeatures, useAgentStatus } from './hooks/useProjects'
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
import { DebugLogViewer } from './components/DebugLogViewer'
import { AgentThought } from './components/AgentThought'
import { AssistantFAB } from './components/AssistantFAB'
import { AssistantPanel } from './components/AssistantPanel'
import { AgentStatusGrid } from './components/AgentStatusGrid'
import { SettingsModal, type RunSettings } from './components/SettingsModal'
import { SettingsPage } from './pages/SettingsPage'
import { Plus, Loader2, FileText, Settings as SettingsIcon } from 'lucide-react'
import type { Feature } from './lib/types'

function App() {
  // Initialize selected project from localStorage
  const [selectedProject, setSelectedProject] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY)
    } catch {
      return null
    }
  })
  const [showAddFeature, setShowAddFeature] = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null)
  const [setupComplete, setSetupComplete] = useState(true) // Start optimistic
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPanelHeight, setDebugPanelHeight] = useState(288) // Default height
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [logsTab, setLogsTab] = useState<'live' | 'workers'>('live')
  const [showSettings, setShowSettings] = useState(false)
  const [route, setRoute] = useState<'main' | 'settings'>(() =>
    window.location.hash.startsWith('#/settings') ? 'settings' : 'main'
  )

  const [yoloEnabled, setYoloEnabled] = useState(false)
  const [runSettings, setRunSettings] = useState<RunSettings>({
    mode: 'standard',
    parallelCount: 3,
    parallelPreset: 'balanced',
  })

  const { data: projects, isLoading: projectsLoading } = useProjects()
  const { data: features } = useFeatures(selectedProject)
  const { data: agentStatusData } = useAgentStatus(selectedProject)
  const wsState = useProjectWebSocket(selectedProject)

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
      if ((e.key === 'a' || e.key === 'A') && selectedProject) {
        e.preventDefault()
        setAssistantOpen(prev => !prev)
      }

      // S : Open settings
      if ((e.key === 's' || e.key === 'S') && selectedProject) {
        e.preventDefault()
        setShowSettings(true)
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

      // Escape : Close modals
      if (e.key === 'Escape') {
        if (showSettings) {
          setShowSettings(false)
        } else if (assistantOpen) {
          setAssistantOpen(false)
        } else if (showAddFeature) {
          setShowAddFeature(false)
        } else if (selectedFeature) {
          setSelectedFeature(null)
        } else if (debugOpen) {
          setDebugOpen(false)
        } else if (route === 'settings') {
          window.location.hash = ''
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedProject, showAddFeature, selectedFeature, debugOpen, assistantOpen, showSettings, route])

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
                />
              )}

              {selectedProject && route === 'main' && (
                <>
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
            <SettingsPage
              initialTab={
                window.location.hash === '#/settings/advanced'
                  ? 'advanced'
                  : window.location.hash === '#/settings/models'
                    ? 'models'
                    : 'run'
              }
              yoloEnabled={yoloEnabled}
              runSettings={runSettings}
              onChangeRunSettings={(next) => setRunSettings(next)}
              onClose={() => (window.location.hash = '')}
            />
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
      {selectedProject && (
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
