import { useState, useEffect, useCallback } from 'react'
import { useProjects, useFeatures, useAgentStatus, useGitStatus } from './hooks/useProjects'
import { useProjectWebSocket } from './hooks/useWebSocket'
import { useFeatureSound } from './hooks/useFeatureSound'
import { useCelebration } from './hooks/useCelebration'

const STORAGE_KEY = 'autocoder-selected-project'
import { ProjectSelector } from './components/ProjectSelector'
import { KanbanBoard } from './components/KanbanBoard'
import { AgentControl } from './components/AgentControl'
import { SetupWizard } from './components/SetupWizard'
import { AddFeatureForm } from './components/AddFeatureForm'
import { FeatureModal } from './components/FeatureModal'
import { DebugLogViewer } from './components/DebugLogViewer'
import { AgentThought } from './components/AgentThought'
import { AssistantFAB } from './components/AssistantFAB'
import { AssistantPanel } from './components/AssistantPanel'
import { GitStatusBar } from './components/GitStatusBar'
import {
  Plus,
  Loader2,
  Cpu,
  FolderOpen,
  Zap,
  GitBranch,
  CheckCircle2,
  Clock,
  PlayCircle,
  ArrowRight,
  Sparkles,
} from 'lucide-react'
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
  const [setupComplete, setSetupComplete] = useState(true)
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPanelHeight, setDebugPanelHeight] = useState(288)
  const [assistantOpen, setAssistantOpen] = useState(false)

  const { data: projects, isLoading: projectsLoading } = useProjects()
  const { data: features } = useFeatures(selectedProject)
  const { data: agentStatusData } = useAgentStatus(selectedProject)
  const { data: gitStatusData, isLoading: gitStatusLoading } = useGitStatus(selectedProject)
  const wsState = useProjectWebSocket(selectedProject)

  useFeatureSound(features)
  useCelebration(features, selectedProject)

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

  useEffect(() => {
    if (selectedProject && projects && !projects.some(p => p.name === selectedProject)) {
      handleSelectProject(null)
    }
  }, [selectedProject, projects, handleSelectProject])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      if (e.key === 'd' || e.key === 'D') {
        e.preventDefault()
        setDebugOpen(prev => !prev)
      }

      if ((e.key === 'n' || e.key === 'N') && selectedProject) {
        e.preventDefault()
        setShowAddFeature(true)
      }

      if ((e.key === 'a' || e.key === 'A') && selectedProject) {
        e.preventDefault()
        setAssistantOpen(prev => !prev)
      }

      if (e.key === 'Escape') {
        if (assistantOpen) {
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
  }, [selectedProject, showAddFeature, selectedFeature, debugOpen, assistantOpen])

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
    <div className="min-h-screen bg-[#0f0f14]">
      {/* Modern Header */}
      <header className="sticky top-0 z-30 bg-[#16161d]/80 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                <Cpu size={22} className="text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-white tracking-tight">
                  AutoCoder
                </h1>
                {selectedProject && (
                  <p className="text-xs text-slate-400 font-mono">{selectedProject}</p>
                )}
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-3">
              <ProjectSelector
                projects={projects ?? []}
                selectedProject={selectedProject}
                onSelectProject={handleSelectProject}
                isLoading={projectsLoading}
              />

              {selectedProject && (
                <>
                  <button
                    onClick={() => setShowAddFeature(true)}
                    className="neo-btn neo-btn-primary text-sm"
                    title="Add Feature (N)"
                  >
                    <Plus size={16} />
                    <span className="hidden sm:inline">Add Feature</span>
                  </button>

                  <AgentControl
                    projectName={selectedProject}
                    status={wsState.agentStatus}
                    yoloMode={agentStatusData?.yolo_mode ?? false}
                  />
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main
        className="max-w-7xl mx-auto px-6 py-8"
        style={{ paddingBottom: debugOpen ? debugPanelHeight + 32 : undefined }}
      >
        {!selectedProject ? (
          /* Welcome Screen - No Project Selected */
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-purple-600/20 flex items-center justify-center mb-6 border border-white/10">
              <Sparkles size={36} className="text-indigo-400" />
            </div>
            <h2 className="text-3xl font-semibold text-white mb-3">
              Welcome to AutoCoder
            </h2>
            <p className="text-slate-400 max-w-md mb-8">
              Your AI-powered autonomous coding assistant. Select a project to get started or create a new one.
            </p>

            {/* Quick Stats */}
            {projects && projects.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-2xl mb-8">
                <div className="neo-card p-4 text-center">
                  <div className="text-2xl font-bold text-white">{projects.length}</div>
                  <div className="text-xs text-slate-400 uppercase tracking-wider">Projects</div>
                </div>
                <div className="neo-card p-4 text-center">
                  <div className="text-2xl font-bold text-emerald-400">Ready</div>
                  <div className="text-xs text-slate-400 uppercase tracking-wider">Status</div>
                </div>
                <div className="neo-card p-4 text-center">
                  <div className="text-2xl font-bold text-indigo-400">v2</div>
                  <div className="text-xs text-slate-400 uppercase tracking-wider">Schema</div>
                </div>
              </div>
            )}

            {/* Project Grid */}
            {projects && projects.length > 0 && (
              <div className="w-full max-w-4xl">
                <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4 text-left">
                  Your Projects
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {projects.map((project) => (
                    <button
                      key={project.name}
                      onClick={() => handleSelectProject(project.name)}
                      className="neo-card p-5 text-left group cursor-pointer hover:border-indigo-500/50"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center border border-white/10">
                          <FolderOpen size={18} className="text-indigo-400" />
                        </div>
                        <ArrowRight size={16} className="text-slate-500 group-hover:text-indigo-400 transition-colors" />
                      </div>
                      <h4 className="font-medium text-white mb-1 truncate">{project.name}</h4>
                      <p className="text-xs text-slate-500 truncate font-mono">{project.path}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Project Dashboard */
          <div className="space-y-6">
            {/* Stats Row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="neo-card p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                    <Clock size={18} className="text-blue-400" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-white">{features?.pending.length ?? 0}</div>
                    <div className="text-xs text-slate-400">Pending</div>
                  </div>
                </div>
              </div>
              <div className="neo-card p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                    <PlayCircle size={18} className="text-amber-400" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-white">{features?.in_progress.length ?? 0}</div>
                    <div className="text-xs text-slate-400">In Progress</div>
                  </div>
                </div>
              </div>
              <div className="neo-card p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                    <CheckCircle2 size={18} className="text-emerald-400" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-white">{features?.done.length ?? 0}</div>
                    <div className="text-xs text-slate-400">Complete</div>
                  </div>
                </div>
              </div>
              <div className="neo-card p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                    <GitBranch size={18} className="text-purple-400" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-white">{progress.percentage}%</div>
                    <div className="text-xs text-slate-400">Progress</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Git Status Bar */}
            <GitStatusBar gitStatus={gitStatusData} isLoading={gitStatusLoading} />

            {/* Progress Bar */}
            <div className="neo-card p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-white">Overall Progress</span>
                <span className="text-sm text-slate-400">{progress.passing} / {progress.total} tasks</span>
              </div>
              <div className="h-2 bg-[#1e1e28] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
                  style={{ width: `${progress.percentage}%` }}
                />
              </div>
            </div>

            {/* Agent Status */}
            {wsState.agentStatus === 'running' && (
              <div className="neo-card p-4 border-emerald-500/30">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse shadow-lg shadow-emerald-500/50" />
                  <span className="text-emerald-400 font-medium">Agent Running</span>
                  {agentStatusData?.yolo_mode && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-medium flex items-center gap-1">
                      <Zap size={12} />
                      YOLO Mode
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Agent Thought */}
            <AgentThought
              logs={wsState.logs}
              agentStatus={wsState.agentStatus}
            />

            {/* Initializing State */}
            {features &&
             features.pending.length === 0 &&
             features.in_progress.length === 0 &&
             features.done.length === 0 &&
             wsState.agentStatus === 'running' && (
              <div className="neo-card p-8 text-center">
                <Loader2 size={32} className="animate-spin mx-auto mb-4 text-indigo-400" />
                <h3 className="text-lg font-medium text-white mb-2">
                  Initializing Features...
                </h3>
                <p className="text-slate-400 text-sm">
                  The agent is reading your spec and creating features.
                </p>
              </div>
            )}

            {/* Kanban Board */}
            <div>
              <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
                Task Board
              </h3>
              <KanbanBoard
                features={features}
                onFeatureClick={setSelectedFeature}
              />
            </div>
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

      {/* Debug Log Viewer */}
      {selectedProject && (
        <DebugLogViewer
          logs={wsState.logs}
          isOpen={debugOpen}
          onToggle={() => setDebugOpen(!debugOpen)}
          onClear={wsState.clearLogs}
          onHeightChange={setDebugPanelHeight}
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
            agentStatus={wsState.agentStatus as 'running' | 'paused' | 'stopped' | undefined}
          />
        </>
      )}
    </div>
  )
}

export default App
