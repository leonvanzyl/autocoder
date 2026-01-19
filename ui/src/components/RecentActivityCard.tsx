/**
 * Small "Mission Control" preview shown on the project dashboard.
 */

import { useMemo } from 'react'
import { List, ExternalLink } from 'lucide-react'
import { useActivityEvents } from '../hooks/useActivityEvents'
import type { ActivityEvent } from '../lib/types'

function formatTime(ts: string): string {
  const raw = String(ts || '').trim()
  if (!raw) return ''
  const iso = raw.includes('T') ? raw : `${raw.replace(' ', 'T')}Z`
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  try {
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

function levelBadge(levelRaw: string): { text: string; className: string } {
  const level = String(levelRaw || 'INFO').toUpperCase()
  if (level === 'ERROR') return { text: 'ERR', className: 'bg-red-600 text-white' }
  if (level === 'WARN' || level === 'WARNING') return { text: 'WRN', className: 'bg-yellow-500 text-[var(--color-neo-text)]' }
  if (level === 'DEBUG') return { text: 'DBG', className: 'bg-[var(--color-neo-neutral-200)] text-[var(--color-neo-text)]' }
  return { text: 'INF', className: 'bg-[var(--color-neo-progress)] text-[var(--color-neo-text)]' }
}

export function RecentActivityCard({
  projectName,
  onOpen,
}: {
  projectName: string
  onOpen: () => void
}) {
  const { data, isLoading, error } = useActivityEvents(projectName, { limit: 10, refetchInterval: 4000 })

  const events = useMemo(() => {
    const items = (data ?? []) as ActivityEvent[]
    // show newest first
    return [...items].reverse().slice(0, 6)
  }, [data])

  return (
    <div className="neo-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div
            className="bg-[var(--color-neo-card)] border-2 border-[var(--color-neo-border)] p-1.5"
            style={{ boxShadow: 'var(--shadow-neo-sm)' }}
          >
            <List size={18} />
          </div>
          <div>
            <div className="font-display font-bold uppercase tracking-wide">Mission Control</div>
            <div className="text-xs text-[var(--color-neo-text-secondary)] font-mono">
              Recent activity across agents, Gatekeeper, QA, and regressions.
            </div>
          </div>
        </div>
        <button
          className="neo-btn neo-btn-sm bg-[var(--color-neo-bg)] flex items-center gap-2"
          onClick={onOpen}
          title="Open activity feed"
        >
          Open
          <ExternalLink size={14} />
        </button>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="text-sm text-[var(--color-neo-text-secondary)]">Loading activity…</div>
        ) : error ? (
          <div className="text-sm text-[var(--color-neo-danger)]">
            {error instanceof Error ? error.message : 'Failed to load activity'}
          </div>
        ) : events.length === 0 ? (
          <div className="text-sm text-[var(--color-neo-text-secondary)]">No activity yet.</div>
        ) : (
          <div className="space-y-2">
            {events.map((ev) => {
              const badge = levelBadge(ev.level)
              return (
                <div key={ev.id} className="flex items-start gap-2">
                  <span className="text-xs font-mono text-[var(--color-neo-text-muted)] shrink-0 pt-0.5">
                    {formatTime(ev.created_at)}
                  </span>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border border-black/20 ${badge.className}`}>
                    {badge.text}
                  </span>
                  <div className="text-sm text-[var(--color-neo-text)] leading-snug flex-1">
                    {ev.message}
                    {ev.feature_id ? (
                      <span className="ml-2 text-xs font-mono text-[var(--color-neo-text-muted)]">#{ev.feature_id}</span>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

