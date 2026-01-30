import { Rocket, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { AgentCard, AgentLogModal } from './AgentCard'
import { OrchestratorStatusCard } from './OrchestratorStatusCard'
import type { ActiveAgent, AgentLogEntry, OrchestratorStatus } from '../lib/types'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface AgentMissionControlProps {
  agents: ActiveAgent[]
  orchestratorStatus: OrchestratorStatus | null
  isExpanded?: boolean
  getAgentLogs?: (agentIndex: number) => AgentLogEntry[]
}

export function AgentMissionControl({
  agents,
  orchestratorStatus,
  isExpanded: defaultExpanded = true,
  getAgentLogs,
}: AgentMissionControlProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const [selectedAgentForLogs, setSelectedAgentForLogs] = useState<ActiveAgent | null>(null)

  // Don't render if no orchestrator status and no agents
  if (!orchestratorStatus && agents.length === 0) {
    return null
  }

  return (
    <Card className="mb-4 overflow-hidden py-0">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-primary hover:bg-primary/90 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Rocket size={18} className="text-primary-foreground" />
          <span className="font-semibold text-sm text-primary-foreground uppercase tracking-wide">
            Mission Control
          </span>
          <Badge variant="secondary" className="ml-2 text-xs">
            {agents.length > 0
              ? `${agents.length} ${agents.length === 1 ? 'agent' : 'agents'} active`
              : orchestratorStatus?.state === 'initializing'
                ? 'Initializing'
                : orchestratorStatus?.state === 'complete'
                  ? 'Complete'
                  : 'Orchestrating'
            }
          </Badge>
        </div>
        {isExpanded ? (
          <ChevronUp size={18} className="text-primary-foreground" />
        ) : (
          <ChevronDown size={18} className="text-primary-foreground" />
        )}
      </button>

      {/* Content */}
      <div
        className={`
          transition-all duration-300 ease-out overflow-hidden
          ${isExpanded ? 'max-h-[400px] opacity-100' : 'max-h-0 opacity-0'}
        `}
      >
        <CardContent className="p-3">
          {/* Orchestrator Status Card */}
          {orchestratorStatus && (
            <OrchestratorStatusCard status={orchestratorStatus} />
          )}

          {/* Agent Cards Row */}
          {agents.length > 0 && (
            <div className="flex gap-3 overflow-x-auto pb-2">
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
        </CardContent>
      </div>

      {/* Log Modal */}
      {selectedAgentForLogs && getAgentLogs && (
        <AgentLogModal
          agent={selectedAgentForLogs}
          logs={getAgentLogs(selectedAgentForLogs.agentIndex)}
          onClose={() => setSelectedAgentForLogs(null)}
        />
      )}
    </Card>
  )
}
