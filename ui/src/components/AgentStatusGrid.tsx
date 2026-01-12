/**
 * Agent Status Grid
 * =================
 *
 * Displays status of parallel agents (from `agent_system.db` heartbeats).
 */

import { useParallelAgentsStatus } from '../hooks/useParallelAgents'
import { Loader2, Bot } from 'lucide-react'

interface AgentStatusGridProps {
  projectName: string
}

export function AgentStatusGrid({ projectName }: AgentStatusGridProps) {
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
          <AgentCard key={agent.agent_id} agent={agent} />
        ))}
      </div>

      {/* Summary */}
      <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-neo-progress)]">
              {activeAgents.length}
            </div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">Active</div>
          </div>
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-neo-done)]">{completedCount}</div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">Completed</div>
          </div>
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-neo-danger)]">{crashedCount}</div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">Crashed</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AgentCard({
  agent,
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
}) {
  const config =
    agent.status === 'ACTIVE'
      ? {
          bgColor: 'bg-[var(--color-neo-progress)]/10',
          borderColor: 'border-[var(--color-neo-progress)]',
          textColor: 'text-[var(--color-neo-progress)]',
          badge: 'RUN',
        }
      : agent.status === 'COMPLETED'
        ? {
            bgColor: 'bg-[var(--color-neo-done)]/10',
            borderColor: 'border-[var(--color-neo-done)]',
            textColor: 'text-[var(--color-neo-done)]',
            badge: 'OK',
          }
        : {
            bgColor: 'bg-[var(--color-neo-danger)]/10',
            borderColor: 'border-[var(--color-neo-danger)]',
            textColor: 'text-[var(--color-neo-danger)]',
            badge: 'ERR',
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
        <span className={`neo-badge font-mono text-xs font-bold ${config.textColor}`}>{config.badge}</span>
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

      <div className="mt-2 text-xs font-display font-bold uppercase tracking-wide">
        <span className={config.textColor}>{agent.status}</span>
      </div>
    </div>
  )
}

