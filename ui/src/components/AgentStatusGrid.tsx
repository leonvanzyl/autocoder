/**
 * Agent Status Grid
 * =================
 *
 * Displays status of parallel agents (from `agent_system.db` heartbeats).
 */

import { useMemo } from 'react'
import { useParallelAgentsStatus } from '../hooks/useParallelAgents'
import { useWorkerLogTail } from '../hooks/useWorkerLogs'
import { Loader2, Bot, FileText } from 'lucide-react'

interface AgentStatusGridProps {
  projectName: string
  onViewLogs?: (agentId: string) => void
}

export function AgentStatusGrid({ projectName, onViewLogs }: AgentStatusGridProps) {
  const { data: status, isLoading } = useParallelAgentsStatus(projectName)

  if (isLoading) {
    return (
      <div className="neo-card p-8">
        <div className="flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-[var(--color-neo-progress)]" />
        </div>
      </div>
    )
  }

  const agents = status?.agents ?? []
  const activeAgents = agents.filter((a) => a.status === 'ACTIVE')

  if (!status || activeAgents.length === 0) {
    return null
  }

  const completedCount = agents.filter((a) => a.status === 'COMPLETED').length
  const crashedCount = agents.filter((a) => a.status === 'CRASHED').length

  return (
    <div className="neo-card p-6">
      <div className="flex items-center gap-3 mb-4">
        <Bot className="text-[var(--color-neo-accent)]" size={28} />
        <h2 className="font-display text-xl font-bold uppercase">Agent Status</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
        {activeAgents.map((agent) => (
          <AgentCard key={agent.agent_id} agent={agent} projectName={projectName} onViewLogs={onViewLogs} />
        ))}
      </div>

      {/* Summary */}
      <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-agent-running)]">
              {activeAgents.length}
            </div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">Running</div>
          </div>
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-agent-done)]">{completedCount}</div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">Done</div>
          </div>
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-agent-retry)]">{crashedCount}</div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">Retrying</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AgentCard({
  agent,
  projectName,
  onViewLogs,
}: {
  agent: {
    agent_id: string
    status: string
    pid: number | null
    feature_id: number | null
    feature_name: string | null
    api_port: number | null
    web_port: number | null
    last_ping: string | null
  }
  projectName: string
  onViewLogs?: (agentId: string) => void
}) {
  const logFilename = `${agent.agent_id}.log`
  const tailQuery = useWorkerLogTail(projectName, logFilename, 8)
  const activityLines = useMemo(() => {
    const lines = tailQuery.data?.lines ?? []
    const cleaned = lines.map((line) => line.trim()).filter(Boolean)
    return cleaned.slice(-3)
  }, [tailQuery.data])

  const config =
    agent.status === 'ACTIVE'
      ? {
          bgColor: 'bg-[var(--color-agent-running)]/10',
          borderColor: 'border-[var(--color-agent-running)]',
          textColor: 'text-[var(--color-agent-running)]',
          badge: 'RUN',
          label: 'Running',
          subtitle: 'On it.',
        }
      : agent.status === 'COMPLETED'
        ? {
            bgColor: 'bg-[var(--color-agent-done)]/10',
            borderColor: 'border-[var(--color-agent-done)]',
            textColor: 'text-[var(--color-agent-done)]',
            badge: 'OK',
            label: 'Done',
            subtitle: 'All good.',
          }
        : {
            bgColor: 'bg-[var(--color-agent-retry)]/10',
            borderColor: 'border-[var(--color-agent-retry)]',
            textColor: 'text-[var(--color-agent-retry)]',
            badge: 'RETRY',
            label: 'Trying plan B...',
            subtitle: 'Recovering.',
          }

  return (
    <div className={`neo-card p-4 ${config.bgColor} ${config.borderColor}`}>
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="font-display font-bold text-sm uppercase">{agent.agent_id}</div>
          <div className="text-xs text-[var(--color-neo-text-secondary)] font-mono">
            {agent.feature_id ? `Feature #${agent.feature_id}` : 'No feature assigned'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onViewLogs && (
            <button
              className="neo-btn neo-btn-secondary neo-btn-icon text-xs p-1.5"
              onClick={() => onViewLogs(agent.agent_id)}
              title="View agent logs"
              aria-label={`View logs for ${agent.agent_id}`}
            >
              <FileText size={14} />
            </button>
          )}
          <span className={`neo-badge font-mono text-xs font-bold ${config.textColor}`}>{config.badge}</span>
        </div>
      </div>

      <div className="font-semibold text-sm mb-3 line-clamp-2">{agent.feature_name || '(unknown feature)'}</div>

      <div className="space-y-1 text-xs font-mono text-[var(--color-neo-text-secondary)]">
        <div className="flex justify-between">
          <span>PID</span>
          <span className="font-bold">{agent.pid ?? '—'}</span>
        </div>
        <div className="flex justify-between">
          <span>API</span>
          <span className="font-bold">{agent.api_port ?? '—'}</span>
        </div>
        <div className="flex justify-between">
          <span>WEB</span>
          <span className="font-bold">{agent.web_port ?? '—'}</span>
        </div>
      </div>

      <div className="mt-3">
        <div className="text-xs font-display font-bold uppercase text-[var(--color-neo-text-secondary)] mb-1">
          Recent activity
        </div>
        {activityLines.length === 0 ? (
          <div className="text-[11px] text-[var(--color-neo-text-muted)]">
            {tailQuery.isFetching ? 'Loading…' : tailQuery.isError ? 'No activity yet.' : 'No activity yet.'}
          </div>
        ) : (
          <ul className="space-y-1 text-[11px] font-mono text-[var(--color-neo-text)]">
            {activityLines.map((line, idx) => (
              <li key={`${agent.agent_id}-${idx}`} className="flex gap-2">
                <span className="text-[var(--color-neo-text-muted)]">•</span>
                <span className="line-clamp-2">{line}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between text-xs font-display font-bold uppercase tracking-wide">
        <span className={config.textColor} title={agent.status}>{config.label}</span>
        <span className="text-[var(--color-neo-text-secondary)]">{config.subtitle}</span>
      </div>
    </div>
  )
}
