/**
 * Agent Status Grid
 * =================
 *
 * Displays real-time status of parallel agents.
 * Neobrutalist design matching the app's style.
 */

import { useParallelAgentsStatus } from '../hooks/useParallelAgents'
import { Loader2, Bot } from 'lucide-react'

interface AgentStatusGridProps {
  projectPath: string
}

export function AgentStatusGrid({ projectPath }: AgentStatusGridProps) {
  const { data: status, isLoading } = useParallelAgentsStatus(projectPath)

  if (isLoading) {
    return (
      <div className="neo-card p-8">
        <div className="flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-[var(--color-neo-progress)]" />
        </div>
      </div>
    )
  }

  if (!status || !status.is_running || status.running_agents.length === 0) {
    return null
  }

  return (
    <div className="neo-card p-6">
      <div className="flex items-center gap-3 mb-4">
        <Bot className="text-[var(--color-neo-accent)]" size={28} />
        <h2 className="font-display text-xl font-bold uppercase">
          Agent Status
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
        {status.running_agents.map((agent) => (
          <AgentCard key={agent.agent_id} agent={agent} />
        ))}
      </div>

      {/* Summary */}
      <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-neo-progress)]">
              {status.running_agents.length}
            </div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">
              Running
            </div>
          </div>
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-neo-done)]">
              {status.completed_count}
            </div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">
              Completed
            </div>
          </div>
          <div>
            <div className="font-display font-bold text-2xl text-[var(--color-neo-danger)]">
              {status.failed_count}
            </div>
            <div className="text-xs uppercase text-[var(--color-neo-text-secondary)]">
              Failed
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface AgentCardProps {
  agent: {
    agent_id: string
    feature_id: number
    feature_name: string
    status: 'running' | 'completed' | 'failed'
    model_used: string
    progress: number
  }
}

function AgentCard({ agent }: AgentCardProps) {
  const statusConfig = {
    running: {
      bgColor: 'bg-[var(--color-neo-progress)]/10',
      borderColor: 'border-[var(--color-neo-progress)]',
      textColor: 'text-[var(--color-neo-progress)]',
      icon: '🔄',
    },
    completed: {
      bgColor: 'bg-[var(--color-neo-done)]/10',
      borderColor: 'border-[var(--color-neo-done)]',
      textColor: 'text-[var(--color-neo-done)]',
      icon: '✅',
    },
    failed: {
      bgColor: 'bg-[var(--color-neo-danger)]/10',
      borderColor: 'border-[var(--color-neo-danger)]',
      textColor: 'text-[var(--color-neo-danger)]',
      icon: '❌',
    },
  }

  const config = statusConfig[agent.status]

  return (
    <div className={`neo-card p-4 ${config.bgColor} ${config.borderColor}`}>
      {/* Agent Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="font-display font-bold text-sm uppercase">
            {agent.agent_id}
          </div>
          <div className="text-xs text-[var(--color-neo-text-secondary)] font-mono">
            Feature #{agent.feature_id}
          </div>
        </div>
        <div className="text-2xl">{config.icon}</div>
      </div>

      {/* Feature Name */}
      <div className="font-semibold text-sm mb-3 line-clamp-2">
        {agent.feature_name}
      </div>

      {/* Model Badge */}
      <div className="inline-block mb-3">
        <span className="neo-badge font-mono text-xs font-bold">
          {agent.model_used.toUpperCase()}
        </span>
      </div>

      {/* Progress Bar */}
      {agent.status === 'running' && (
        <div>
          <div className="w-full bg-[var(--color-neo-border)]/20 rounded-full h-2 mb-1">
            <div
              className="bg-[var(--color-neo-progress)] h-2 rounded-full transition-all"
              style={{ width: `${agent.progress}%` }}
            />
          </div>
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] text-right">
            {agent.progress}%
          </div>
        </div>
      )}

      {/* Status Label */}
      <div className="mt-2 text-xs font-display font-bold uppercase tracking-wide">
        {agent.status}
      </div>
    </div>
  )
}
