import { useState } from 'react'
import { ChevronDown, ChevronUp, Code, FlaskConical, Clock, Lock, Sparkles } from 'lucide-react'
import { OrchestratorAvatar } from './OrchestratorAvatar'
import type { OrchestratorStatus, OrchestratorState } from '../lib/types'

interface OrchestratorStatusCardProps {
  status: OrchestratorStatus
}

// Get a friendly state description
function getStateText(state: OrchestratorState): string {
  switch (state) {
    case 'idle':
      return 'Standing by...'
    case 'initializing':
      return 'Setting up features...'
    case 'scheduling':
      return 'Planning next moves...'
    case 'spawning':
      return 'Deploying agents...'
    case 'monitoring':
      return 'Watching progress...'
    case 'complete':
      return 'Mission accomplished!'
    default:
      return 'Orchestrating...'
  }
}

// Get state color
function getStateColor(state: OrchestratorState): string {
  switch (state) {
    case 'complete':
      return 'text-neo-done'
    case 'spawning':
      return 'text-[#7C3AED]'  // Violet
    case 'scheduling':
    case 'monitoring':
      return 'text-neo-progress'
    case 'initializing':
      return 'text-neo-pending'
    default:
      return 'text-neo-text-secondary'
  }
}

// Format timestamp to relative time
function formatRelativeTime(timestamp: string): string {
  const now = new Date()
  const then = new Date(timestamp)
  const diffMs = now.getTime() - then.getTime()
  const diffSecs = Math.floor(diffMs / 1000)

  if (diffSecs < 5) return 'just now'
  if (diffSecs < 60) return `${diffSecs}s ago`
  const diffMins = Math.floor(diffSecs / 60)
  if (diffMins < 60) return `${diffMins}m ago`
  return `${Math.floor(diffMins / 60)}h ago`
}

export function OrchestratorStatusCard({ status }: OrchestratorStatusCardProps) {
  const [showEvents, setShowEvents] = useState(false)

  return (
    <div className="neo-card p-4 bg-gradient-to-r from-[#EDE9FE] to-[#F3E8FF] border-[#7C3AED]/30 mb-4">
      <div className="flex items-start gap-4">
        {/* Avatar */}
        <OrchestratorAvatar state={status.state} size="md" />

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2 mb-1">
            <span className="font-display font-bold text-lg text-[#7C3AED]">
              Maestro
            </span>
            <span className={`text-sm font-medium ${getStateColor(status.state)}`}>
              {getStateText(status.state)}
            </span>
          </div>

          {/* Current message */}
          <p className="text-sm text-neo-text mb-3 line-clamp-2">
            {status.message}
          </p>

          {/* Status badges row */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Coding agents badge */}
            <div className="inline-flex items-center gap-1.5 px-2 py-1 bg-blue-100 text-blue-700 rounded border border-blue-300 text-xs font-bold">
              <Code size={12} />
              <span>Coding: {status.codingAgents}</span>
            </div>

            {/* Testing agents badge */}
            <div className="inline-flex items-center gap-1.5 px-2 py-1 bg-purple-100 text-purple-700 rounded border border-purple-300 text-xs font-bold">
              <FlaskConical size={12} />
              <span>Testing: {status.testingAgents}</span>
            </div>

            {/* Ready queue badge */}
            <div className="inline-flex items-center gap-1.5 px-2 py-1 bg-green-100 text-green-700 rounded border border-green-300 text-xs font-bold">
              <Clock size={12} />
              <span>Ready: {status.readyCount}</span>
            </div>

            {/* Blocked badge (only show if > 0) */}
            {status.blockedCount > 0 && (
              <div className="inline-flex items-center gap-1.5 px-2 py-1 bg-amber-100 text-amber-700 rounded border border-amber-300 text-xs font-bold">
                <Lock size={12} />
                <span>Blocked: {status.blockedCount}</span>
              </div>
            )}
          </div>
        </div>

        {/* Recent events toggle */}
        {status.recentEvents.length > 0 && (
          <button
            onClick={() => setShowEvents(!showEvents)}
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-[#7C3AED] hover:bg-[#7C3AED]/10 rounded transition-colors"
          >
            <Sparkles size={12} />
            <span>Activity</span>
            {showEvents ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>

      {/* Collapsible recent events */}
      {showEvents && status.recentEvents.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[#7C3AED]/20">
          <div className="space-y-1.5">
            {status.recentEvents.map((event, idx) => (
              <div
                key={`${event.timestamp}-${idx}`}
                className="flex items-start gap-2 text-xs"
              >
                <span className="text-[#A78BFA] shrink-0 font-mono">
                  {formatRelativeTime(event.timestamp)}
                </span>
                <span className="text-neo-text">
                  {event.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
