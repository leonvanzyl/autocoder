import { Rocket, ChevronDown, ChevronUp, Activity } from 'lucide-react'
import { useState } from 'react'
import { AgentCard, AgentLogModal } from './AgentCard'
import { ActivityFeed } from './ActivityFeed'
import { OrchestratorStatusCard } from './OrchestratorStatusCard'
import type { ActiveAgent, AgentLogEntry, OrchestratorStatus } from '../lib/types'

const ACTIVITY_COLLAPSED_KEY = 'autocoder-activity-collapsed'

interface AgentMissionControlProps {
  agents: ActiveAgent[]
  orchestratorStatus: OrchestratorStatus | null
  recentActivity: Array<{
    agentName: string
    thought: string
    timestamp: string
    featureId: number
  }>
  isExpanded?: boolean
  getAgentLogs?: (agentIndex: number) => AgentLogEntry[]
}

export function AgentMissionControl({
  agents,
  orchestratorStatus,
  recentActivity,
  isExpanded: defaultExpanded = true,
  getAgentLogs,
}: AgentMissionControlProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const [activityCollapsed, setActivityCollapsed] = useState(() => {
    try {
      return localStorage.getItem(ACTIVITY_COLLAPSED_KEY) === 'true'
    } catch {
      return false
    }
  })
  // State for log modal
  const [selectedAgentForLogs, setSelectedAgentForLogs] = useState<ActiveAgent | null>(null)

  const toggleActivityCollapsed = () => {
    const newValue = !activityCollapsed
    setActivityCollapsed(newValue)
    try {
      localStorage.setItem(ACTIVITY_COLLAPSED_KEY, String(newValue))
    } catch {
      // localStorage not available
    }
  }

  // Don't render if no orchestrator status and no agents
  if (!orchestratorStatus && agents.length === 0) {
    return null
  }

  return (
    <div className="neo-card mb-6 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[var(--color-neo-progress)] hover:brightness-105 transition-all"
      >
        <div className="flex items-center gap-2">
          <Rocket size={20} className="text-neo-text-on-bright" />
          <span className="font-display font-bold text-neo-text-on-bright uppercase tracking-wide">
            Mission Control
          </span>
          <span className="neo-badge neo-badge-sm bg-white text-neo-text ml-2">
            {agents.length > 0
              ? `${agents.length} ${agents.length === 1 ? 'agent' : 'agents'} active`
              : orchestratorStatus?.state === 'initializing'
                ? 'Initializing'
                : orchestratorStatus?.state === 'complete'
                  ? 'Complete'
                  : 'Orchestrating'
            }
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp size={20} className="text-neo-text-on-bright" />
        ) : (
          <ChevronDown size={20} className="text-neo-text-on-bright" />
        )}
      </button>

      {/* Content */}
      <div
        className={`
          transition-all duration-300 ease-out overflow-hidden
          ${isExpanded ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'}
        `}
      >
        <div className="p-4">
          {/* Orchestrator Status Card */}
          {orchestratorStatus && (
            <OrchestratorStatusCard status={orchestratorStatus} />
          )}

          {/* Agent Cards Row */}
          {agents.length > 0 && (
            <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-thin">
              {agents.map((agent) => (
                <AgentCard
                  key={`agent-${agent.agentIndex}`}
                  agent={agent}
                  onShowLogs={(agentIndex) => {
                    const agentToShow = agents.find(a => a.agentIndex === agentIndex)
                    if (agentToShow) {
                      setSelectedAgentForLogs(agentToShow)
                    }
                  }}
                />
              ))}
            </div>
          )}

          {/* Collapsible Activity Feed */}
          {recentActivity.length > 0 && (
            <div className="mt-4 pt-4 border-t-2 border-neo-border/30">
              <button
                onClick={toggleActivityCollapsed}
                className="flex items-center gap-2 mb-2 hover:opacity-80 transition-opacity"
              >
                <Activity size={14} className="text-neo-text-secondary" />
                <span className="text-xs font-bold text-neo-text-secondary uppercase tracking-wide">
                  Recent Activity
                </span>
                <span className="text-xs text-neo-muted">
                  ({recentActivity.length})
                </span>
                {activityCollapsed ? (
                  <ChevronDown size={14} className="text-neo-text-secondary" />
                ) : (
                  <ChevronUp size={14} className="text-neo-text-secondary" />
                )}
              </button>
              <div
                className={`
                  transition-all duration-200 ease-out overflow-hidden
                  ${activityCollapsed ? 'max-h-0 opacity-0' : 'max-h-[300px] opacity-100'}
                `}
              >
                <ActivityFeed activities={recentActivity} maxItems={5} showHeader={false} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Log Modal */}
      {selectedAgentForLogs && getAgentLogs && (
        <AgentLogModal
          agent={selectedAgentForLogs}
          logs={getAgentLogs(selectedAgentForLogs.agentIndex)}
          onClose={() => setSelectedAgentForLogs(null)}
        />
      )}
    </div>
  )
}
