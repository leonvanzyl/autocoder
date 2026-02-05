import { useState, useEffect, useCallback } from 'react'
import { useQueryClient, useQuery } from '@tanstack/react-query'
import { useProjects, useFeatures, useAgentStatus, useSettings } from './hooks/useProjects'
import { useProjectWebSocket } from './hooks/useWebSocket'
import { useFeatureSound } from './hooks/useFeatureSound'
import { useCelebration } from './hooks/useCelebration'
import { useTheme } from './hooks/useTheme'
import { ProjectSelector } from './components/ProjectSelector'
import { KanbanBoard } from './components/KanbanBoard'
import { AgentControl } from './components/AgentControl'
import { ProgressDashboard } from './components/ProgressDashboard'
import { SetupWizard } from './components/SetupWizard'
import { AddFeatureForm } from './components/AddFeatureForm'
import { FeatureModal } from './components/FeatureModal'
import { DebugLogViewer, type TabType } from './components/DebugLogViewer'
import { AgentMissionControl } from './components/AgentMissionControl'
import { CelebrationOverlay } from './components/CelebrationOverlay'
import { AssistantFAB } from './components/AssistantFAB'
import { AssistantPanel } from './components/AssistantPanel'
import { ExpandProjectModal } from './components/ExpandProjectModal'
import { SpecCreationChat } from './components/SpecCreationChat'
import { SettingsModal } from './components/SettingsModal'
import { DevServerControl } from './components/DevServerControl'
import { ViewToggle, type ViewMode } from './components/ViewToggle'
import { DependencyGraph } from './components/DependencyGraph'
import { KeyboardShortcutsHelp } from './components/KeyboardShortcutsHelp'
import { ThemeSelector } from './components/ThemeSelector'
import { ResetProjectModal } from './components/ResetProjectModal'
import { ProjectSetupRequired } from './components/ProjectSetupRequired'
import { getDependencyGraph, startAgent } from './lib/api'
import { Loader2, Settings, Moon, Sun, RotateCcw, BookOpen } from 'lucide-react'
import type { Feature } from './lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const STORAGE_KEY = 'autoforge-selected-project'
const VIEW_MODE_KEY = 'autoforge-view-mode'

// Bottom padding for main content when debug panel is collapsed (40px header + 8px margin)
const COLLAPSED_DEBUG_PANEL_CLEARANCE = 48

type InitializerStatus = 'idle' | 'starting' | 'error'

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
  const [showExpandProject, setShowExpandProject] = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null)
  const [setupComplete, setSetupComplete] = useState(true) // Start optimistic
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPanelHeight, setDebugPanelHeight] = useState(288) // Default height
  const [debugActiveTab, setDebugActiveTab] = useState<TabType>('agent')
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false)
  const [isSpecCreating, setIsSpecCreating] = useState(false)
  const [showResetModal, setShowResetModal] = useState(false)
  const [showSpecChat, setShowSpecChat] = useState(false)  // For "Create Spec" button in empty kanban
  const [specInitializerStatus, setSpecInitializerStatus] = useState<InitializerStatus>('idle')
  const [specInitializerError, setSpecInitializerError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    try {
      const stored = localStorage.getItem(VIEW_MODE_KEY)
      return (stored === 'graph' ? 'graph' : 'kanban') as ViewMode
    } catch {
      return 'kanban'
    }
  })

  const queryClient = useQueryClient()
  const { data: projects, isLoading: projectsLoading } = useProjects()
  const { data: features } = useFeatures(selectedProject)
  const { data: settings } = useSettings()
  useAgentStatus(selectedProject) // Keep polling for status updates
  const wsState = useProjectWebSocket(selectedProject)
  const { theme, setTheme, darkMode, toggleDarkMode, themes } = useTheme()

  // Get has_spec from the selected project
  const selectedProjectData = projects?.find(p => p.name === selectedProject)
  const hasSpec = selectedProjectData?.has_spec ?? true

  // Fetch graph data when in graph view
  const { data: graphData } = useQuery({
    queryKey: ['dependencyGraph', selectedProject],
    queryFn: () => getDependencyGraph(selectedProject!),
    enabled: !!selectedProject && viewMode === 'graph',
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  // Persist view mode to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(VIEW_MODE_KEY, viewMode)
    } catch {
      // localStorage not available
    }
  }, [viewMode])

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

  // Handle graph node click - memoized to prevent DependencyGraph re-renders
  const handleGraphNodeClick = useCallback((nodeId: number) => {
    const allFeatures = [
      ...(features?.pending ?? []),
      ...(features?.in_progress ?? []),
      ...(features?.done ?? [])
    ]
    const feature = allFeatures.find(f => f.id === nodeId)
    if (feature) setSelectedFeature(feature)
  }, [features])

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
        setDebugOpen(prev => !prev)
      }

      // T : Toggle terminal tab in debug panel
      if (e.key === 't' || e.key === 'T') {
        e.preventDefault()
        if (!debugOpen) {
          // If panel is closed, open it and switch to terminal tab
          setDebugOpen(true)
          setDebugActiveTab('terminal')
        } else if (debugActiveTab === 'terminal') {
          // If already on terminal tab, close the panel
          setDebugOpen(false)
        } else {
          // If open but on different tab, switch to terminal
          setDebugActiveTab('terminal')
        }
      }

      // N : Add new feature (when project selected)
      if ((e.key === 'n' || e.key === 'N') && selectedProject) {
        e.preventDefault()
        setShowAddFeature(true)
      }

      // E : Expand project with AI (when project selected, has spec and has features)
      if ((e.key === 'e' || e.key === 'E') && selectedProject && hasSpec && features &&
          (features.pending.length + features.in_progress.length + features.done.length) > 0) {
        e.preventDefault()
        setShowExpandProject(true)
      }

      // A : Toggle assistant panel (when project selected and not in spec creation)
      if ((e.key === 'a' || e.key === 'A') && selectedProject && !isSpecCreating) {
        e.preventDefault()
        setAssistantOpen(prev => !prev)
      }

      // , : Open settings
      if (e.key === ',') {
        e.preventDefault()
        setShowSettings(true)
      }

      // G : Toggle between Kanban and Graph view (when project selected)
      if ((e.key === 'g' || e.key === 'G') && selectedProject) {
        e.preventDefault()
        setViewMode(prev => prev === 'kanban' ? 'graph' : 'kanban')
      }

      // ? : Show keyboard shortcuts help
      if (e.key === '?') {
        e.preventDefault()
        setShowKeyboardHelp(true)
      }

      // R : Open reset modal (when project selected and agent not running)
      if ((e.key === 'r' || e.key === 'R') && selectedProject && wsState.agentStatus !== 'running') {
        e.preventDefault()
        setShowResetModal(true)
      }

      // Escape : Close modals
      if (e.key === 'Escape') {
        if (showKeyboardHelp) {
          setShowKeyboardHelp(false)
        } else if (showResetModal) {
          setShowResetModal(false)
        } else if (showExpandProject) {
          setShowExpandProject(false)
        } else if (showSettings) {
          setShowSettings(false)
        } else if (assistantOpen) {
          setAssistantOpen(false)
        } else if (showAddFeature) {
          setShowAddFeature(false)
        } else if (selectedFeature) {
          setSelectedFeature(null)
        } else if (debugOpen) {
          setDebugOpen(false)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedProject, showAddFeature, showExpandProject, selectedFeature, debugOpen, debugActiveTab, assistantOpen, features, showSettings, showKeyboardHelp, isSpecCreating, viewMode, showResetModal, wsState.agentStatus, hasSpec])

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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-card/80 backdrop-blur-md text-foreground border-b-2 border-border">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Logo and Title */}
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="AutoForge" className="h-9 w-9 rounded-full" />
              <h1 className="font-display text-2xl font-bold tracking-tight uppercase">
                AutoForge
              </h1>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-4">
              <ProjectSelector
                projects={projects ?? []}
                selectedProject={selectedProject}
                onSelectProject={handleSelectProject}
                isLoading={projectsLoading}
                onSpecCreatingChange={setIsSpecCreating}
              />

              {selectedProject && (
                <>
                  <AgentControl
                    projectName={selectedProject}
                    status={wsState.agentStatus}
                    defaultConcurrency={selectedProjectData?.default_concurrency}
                  />

                  <DevServerControl
                    projectName={selectedProject}
                    status={wsState.devServerStatus}
                    url={wsState.devServerUrl}
                  />

                  <Button
                    onClick={() => setShowSettings(true)}
                    variant="outline"
                    size="sm"
                    title="Settings (,)"
                    aria-label="Open Settings"
                  >
                    <Settings size={18} />
                  </Button>

                  <Button
                    onClick={() => setShowResetModal(true)}
                    variant="outline"
                    size="sm"
                    title="Reset Project (R)"
                    aria-label="Reset Project"
                    disabled={wsState.agentStatus === 'running'}
                  >
                    <RotateCcw size={18} />
                  </Button>

                  {/* Ollama Mode Indicator */}
                  {settings?.ollama_mode && (
                    <div
                      className="flex items-center gap-1.5 px-2 py-1 bg-card rounded border-2 border-border shadow-sm"
                      title="Using Ollama local models (configured via .env)"
                    >
                      <img src="/ollama.png" alt="Ollama" className="w-5 h-5" />
                      <span className="text-xs font-bold text-foreground">Ollama</span>
                    </div>
                  )}

                  {/* GLM Mode Badge */}
                  {settings?.glm_mode && (
                    <Badge
                      className="bg-purple-500 text-white hover:bg-purple-600"
                      title="Using GLM API (configured via .env)"
                    >
                      GLM
                    </Badge>
                  )}
                </>
              )}

              {/* Docs link */}
              <Button
                onClick={() => window.open('https://autoforge.cc', '_blank')}
                variant="outline"
                size="sm"
                title="Documentation"
                aria-label="Open Documentation"
              >
                <BookOpen size={18} />
              </Button>

              {/* Theme selector */}
              <ThemeSelector
                themes={themes}
                currentTheme={theme}
                onThemeChange={setTheme}
              />

              {/* Dark mode toggle - always visible */}
              <Button
                onClick={toggleDarkMode}
                variant="outline"
                size="sm"
                title="Toggle dark mode"
                aria-label="Toggle dark mode"
              >
                {darkMode ? <Sun size={18} /> : <Moon size={18} />}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main
        className="max-w-7xl mx-auto px-4 py-8"
        style={{ paddingBottom: debugOpen ? debugPanelHeight + 32 : COLLAPSED_DEBUG_PANEL_CLEARANCE }}
      >
        {!selectedProject ? (
          <div className="text-center mt-12">
            <h2 className="font-display text-2xl font-bold mb-2">
              Welcome to AutoForge
            </h2>
            <p className="text-muted-foreground mb-4">
              Select a project from the dropdown above or create a new one to get started.
            </p>
          </div>
        ) : !hasSpec ? (
          <ProjectSetupRequired
            projectName={selectedProject}
            projectPath={selectedProjectData?.path}
            onCreateWithClaude={() => setShowSpecChat(true)}
            onEditManually={() => {
              // Open debug panel for the user to see the project path
              setDebugOpen(true)
            }}
          />
        ) : (
          <div className="space-y-8">
            {/* Progress Dashboard */}
            <ProgressDashboard
              passing={progress.passing}
              total={progress.total}
              percentage={progress.percentage}
              isConnected={wsState.isConnected}
              logs={wsState.activeAgents.length === 0 ? wsState.logs : undefined}
              agentStatus={wsState.activeAgents.length === 0 ? wsState.agentStatus : undefined}
            />

            {/* Agent Mission Control - shows orchestrator status and active agents in parallel mode */}
            <AgentMissionControl
              agents={wsState.activeAgents}
              orchestratorStatus={wsState.orchestratorStatus}
              recentActivity={wsState.recentActivity}
              getAgentLogs={wsState.getAgentLogs}
            />


            {/* Initializing Features State - show when agent is running but no features yet */}
            {features &&
             features.pending.length === 0 &&
             features.in_progress.length === 0 &&
             features.done.length === 0 &&
             wsState.agentStatus === 'running' && (
              <Card className="p-8 text-center">
                <CardContent className="p-0">
                  <Loader2 size={32} className="animate-spin mx-auto mb-4 text-primary" />
                  <h3 className="font-display font-bold text-xl mb-2">
                    Initializing Features...
                  </h3>
                  <p className="text-muted-foreground">
                    The agent is reading your spec and creating features. This may take a moment.
                  </p>
                </CardContent>
              </Card>
            )}

            {/* View Toggle - only show when there are features */}
            {features && (features.pending.length + features.in_progress.length + features.done.length) > 0 && (
              <div className="flex justify-center">
                <ViewToggle viewMode={viewMode} onViewModeChange={setViewMode} />
              </div>
            )}

            {/* Kanban Board or Dependency Graph based on view mode */}
            {viewMode === 'kanban' ? (
              <KanbanBoard
                features={features}
                onFeatureClick={setSelectedFeature}
                onAddFeature={() => setShowAddFeature(true)}
                onExpandProject={() => setShowExpandProject(true)}
                activeAgents={wsState.activeAgents}
                onCreateSpec={() => setShowSpecChat(true)}
                hasSpec={hasSpec}
              />
            ) : (
              <Card className="overflow-hidden" style={{ height: '600px' }}>
                {graphData ? (
                  <DependencyGraph
                    graphData={graphData}
                    onNodeClick={handleGraphNodeClick}
                    activeAgents={wsState.activeAgents}
                  />
                ) : (
                  <div className="h-full flex items-center justify-center">
                    <Loader2 size={32} className="animate-spin text-primary" />
                  </div>
                )}
              </Card>
            )}
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

      {/* Expand Project Modal - AI-powered bulk feature creation */}
      {showExpandProject && selectedProject && hasSpec && (
        <ExpandProjectModal
          isOpen={showExpandProject}
          projectName={selectedProject}
          onClose={() => setShowExpandProject(false)}
          onFeaturesAdded={() => {
            // Invalidate features query to refresh the kanban board
            queryClient.invalidateQueries({ queryKey: ['features', selectedProject] })
          }}
        />
      )}

      {/* Spec Creation Chat - for creating spec from empty kanban */}
      {showSpecChat && selectedProject && (
        <div className="fixed inset-0 z-50 bg-background">
          <SpecCreationChat
            projectName={selectedProject}
            onComplete={async (_specPath, yoloMode) => {
              setSpecInitializerStatus('starting')
              try {
                await startAgent(selectedProject, {
                  yoloMode: yoloMode ?? false,
                  maxConcurrency: 3,
                })
                // Success — close chat and refresh
                setShowSpecChat(false)
                setSpecInitializerStatus('idle')
                queryClient.invalidateQueries({ queryKey: ['projects'] })
                queryClient.invalidateQueries({ queryKey: ['features', selectedProject] })
              } catch (err) {
                setSpecInitializerStatus('error')
                setSpecInitializerError(err instanceof Error ? err.message : 'Failed to start agent')
              }
            }}
            onCancel={() => { setShowSpecChat(false); setSpecInitializerStatus('idle') }}
            onExitToProject={() => { setShowSpecChat(false); setSpecInitializerStatus('idle') }}
            initializerStatus={specInitializerStatus}
            initializerError={specInitializerError}
            onRetryInitializer={() => {
              setSpecInitializerError(null)
              setSpecInitializerStatus('idle')
            }}
          />
        </div>
      )}

      {/* Debug Log Viewer - fixed to bottom */}
      {selectedProject && (
        <DebugLogViewer
          logs={wsState.logs}
          devLogs={wsState.devLogs}
          isOpen={debugOpen}
          onToggle={() => setDebugOpen(!debugOpen)}
          onClear={wsState.clearLogs}
          onClearDevLogs={wsState.clearDevLogs}
          onHeightChange={setDebugPanelHeight}
          projectName={selectedProject}
          activeTab={debugActiveTab}
          onTabChange={setDebugActiveTab}
        />
      )}

      {/* Assistant FAB and Panel - hide when expand modal or spec creation is open */}
      {selectedProject && !showExpandProject && !isSpecCreating && !showSpecChat && (
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

      {/* Settings Modal */}
      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />

      {/* Keyboard Shortcuts Help */}
      <KeyboardShortcutsHelp isOpen={showKeyboardHelp} onClose={() => setShowKeyboardHelp(false)} />

      {/* Reset Project Modal */}
      {showResetModal && selectedProject && (
        <ResetProjectModal
          isOpen={showResetModal}
          projectName={selectedProject}
          onClose={() => setShowResetModal(false)}
          onResetComplete={(wasFullReset) => {
            // If full reset, the spec was deleted - show spec creation chat
            if (wasFullReset) {
              setShowSpecChat(true)
            }
          }}
        />
      )}

      {/* Celebration Overlay - shows when a feature is completed by an agent */}
      {wsState.celebration && (
        <CelebrationOverlay
          agentName={wsState.celebration.agentName}
          featureName={wsState.celebration.featureName}
          onComplete={wsState.clearCelebration}
        />
      )}
    </div>
  )
}

export default App
