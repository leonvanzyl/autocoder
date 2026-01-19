/**
 * Mission Control Activity Feed (DB-backed)
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { useActivityEvents, useClearActivityEvents } from '../hooks/useActivityEvents'
import type { ActivityEvent } from '../lib/types'

type ActivityFilter = 'all' | 'agents' | 'gatekeeper' | 'qa' | 'regression' | 'errors'

function _parseTimestamp(ts: string): Date | null {
  const raw = String(ts || '').trim()
  if (!raw) return null
  // SQLite CURRENT_TIMESTAMP: "YYYY-MM-DD HH:MM:SS" (UTC). Convert to ISO.
  const iso = raw.includes('T') ? raw : `${raw.replace(' ', 'T')}Z`
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

function _formatTime(ts: string): string {
  const d = _parseTimestamp(ts)
  if (!d) return ''
  try {
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

function _levelColor(levelRaw: string): string {
  const level = String(levelRaw || '').toUpperCase()
  if (level === 'ERROR') return 'text-red-300'
  if (level === 'WARN' || level === 'WARNING') return 'text-yellow-300'
  if (level === 'DEBUG') return 'text-gray-400'
  return 'text-blue-200'
}

function _eventGroup(ev: ActivityEvent): Exclude<ActivityFilter, 'all' | 'errors'> {
  const t = String(ev.event_type || '').toLowerCase()
  if (t.startsWith('qa.')) return 'qa'
  if (t.startsWith('gatekeeper.') || t.startsWith('preflight.')) return 'gatekeeper'
  if (t.startsWith('regression.')) return 'regression'
  return 'agents'
}

export function ActivityFeedPanel({ projectName, isActive }: { projectName: string; isActive?: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState<ActivityFilter>('all')

  const { data, isLoading, error } = useActivityEvents(projectName, {
    enabled: isActive ?? true,
    limit: 400,
    refetchInterval: 2500,
  })
  const clearMutation = useClearActivityEvents(projectName)

  const events = useMemo(() => {
    const items = (data ?? []) as ActivityEvent[]
    if (filter === 'all') return items

    if (filter === 'errors') {
      return items.filter((e) => ['ERROR', 'WARN', 'WARNING'].includes(String(e.level || '').toUpperCase()))
    }

    return items.filter((e) => _eventGroup(e) === filter)
  }, [data, filter])

  useEffect(() => {
    if (!autoScroll) return
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [events, autoScroll])

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 60
    setAutoScroll(isAtBottom)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-2 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-300">Mission Control</span>
          <select
            className="text-xs font-mono bg-[#222] border border-[#333] text-gray-200 rounded px-2 py-1"
            value={filter}
            onChange={(e) => setFilter(e.target.value as ActivityFilter)}
            aria-label="Filter activity"
          >
            <option value="all">All</option>
            <option value="agents">Agents</option>
            <option value="gatekeeper">Gatekeeper</option>
            <option value="qa">QA</option>
            <option value="regression">Regression</option>
            <option value="errors">Errors</option>
          </select>
          {!autoScroll && (
            <span className="px-2 py-0.5 text-xs font-mono bg-yellow-600 text-white rounded">
              Paused
            </span>
          )}
        </div>

        <button
          onClick={() => clearMutation.mutate()}
          disabled={clearMutation.isPending}
          className="p-1.5 hover:bg-[#333] rounded transition-colors disabled:opacity-50"
          title="Clear activity events"
        >
          <Trash2 size={14} className="text-gray-400" />
        </button>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-2 pb-2 font-mono text-sm"
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-gray-500">Loading activity…</div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-red-400">
            {error instanceof Error ? error.message : 'Failed to load activity'}
          </div>
        ) : events.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            No activity yet.
          </div>
        ) : (
          <div className="space-y-0.5">
            {events.map((ev) => (
              <div key={ev.id} className="flex gap-2 hover:bg-[#2a2a2a] px-1 py-0.5 rounded">
                <span className="text-gray-500 select-none shrink-0">{_formatTime(ev.created_at)}</span>
                <span className={`${_levelColor(ev.level)} shrink-0`}>{String(ev.level || 'INFO').toUpperCase()}</span>
                <span className="text-gray-300 whitespace-pre-wrap break-words flex-1">{ev.message}</span>
                {ev.feature_id ? (
                  <span className="text-xs text-gray-500 shrink-0">#{ev.feature_id}</span>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

