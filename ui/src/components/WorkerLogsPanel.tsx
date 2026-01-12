/**
 * Worker Logs Panel
 * =================
 *
 * Inspect and prune parallel worker log files stored in `.autocoder/logs`.
 * Designed to be embedded (e.g., inside the bottom Logs drawer).
 */

import { useMemo, useState } from 'react'
import { RefreshCw, Trash2, Scissors } from 'lucide-react'
import { useDeleteWorkerLog, usePruneWorkerLogs, useWorkerLogTail, useWorkerLogs } from '../hooks/useWorkerLogs'

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function WorkerLogsPanel({ projectName }: { projectName: string }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [tail, setTail] = useState(400)

  const [keepDays, setKeepDays] = useState(7)
  const [keepFiles, setKeepFiles] = useState(200)
  const [maxMb, setMaxMb] = useState(200)
  const [dryRun, setDryRun] = useState(true)

  const logsQuery = useWorkerLogs(projectName)
  const tailQuery = useWorkerLogTail(projectName, selected, tail)
  const prune = usePruneWorkerLogs(projectName)
  const del = useDeleteWorkerLog(projectName)

  const selectedText = useMemo(() => (tailQuery.data?.lines ?? []).join('\n'), [tailQuery.data])
  const files = logsQuery.data?.files ?? []

  return (
    <div className="h-full overflow-hidden grid grid-cols-1 lg:grid-cols-3 gap-3">
      {/* File list */}
      <div className="neo-card p-3 overflow-hidden flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="font-display font-bold uppercase text-xs">Files</div>
          <button
            className="neo-btn neo-btn-secondary text-xs py-1.5 px-2.5"
            onClick={() => logsQuery.refetch()}
            disabled={logsQuery.isFetching}
            title="Refresh"
          >
            <RefreshCw size={14} />
          </button>
        </div>

        {logsQuery.isLoading ? (
          <div className="text-xs text-[var(--color-neo-text-secondary)]">Loading…</div>
        ) : files.length === 0 ? (
          <div className="text-xs text-[var(--color-neo-text-secondary)]">
            No worker logs found (expected under <code>.autocoder/logs</code>).
          </div>
        ) : (
          <div className="space-y-2 overflow-y-auto pr-1">
            {files.map((f) => (
              <button
                key={f.name}
                className={`neo-card p-2 text-left w-full ${selected === f.name ? 'ring-4 ring-[var(--color-neo-accent)]' : ''}`}
                onClick={() => setSelected(f.name)}
              >
                <div className="font-mono text-[11px] break-all">{f.name}</div>
                <div className="text-[11px] text-[var(--color-neo-text-secondary)] flex justify-between mt-1 gap-2">
                  <span>{formatBytes(f.size_bytes)}</span>
                  <span className="whitespace-nowrap">{new Date(f.modified_at).toLocaleString()}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Log tail + prune */}
      <div className="neo-card p-3 overflow-hidden flex flex-col lg:col-span-2">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div className="font-display font-bold uppercase text-xs">{selected ? `Tail: ${selected}` : 'Tail'}</div>
          <div className="flex items-center gap-2">
            <label className="text-[11px] font-mono text-[var(--color-neo-text-secondary)]">Lines</label>
            <input
              type="number"
              min={1}
              max={5000}
              value={tail}
              onChange={(e) => setTail(Math.max(1, Math.min(5000, Number(e.target.value) || 400)))}
              className="neo-btn text-xs py-1.5 px-2 bg-white border-3 border-[var(--color-neo-border)] font-mono w-20"
            />
            <button
              className="neo-btn neo-btn-secondary text-xs py-1.5 px-2.5"
              onClick={() => tailQuery.refetch()}
              disabled={!selected || tailQuery.isFetching}
              title="Refresh tail"
            >
              <RefreshCw size={14} />
            </button>
            <button
              className="neo-btn neo-btn-danger text-xs py-1.5 px-2.5"
              onClick={async () => {
                if (!selected) return
                await del.mutateAsync(selected)
                setSelected(null)
              }}
              disabled={!selected || del.isPending}
              title="Delete selected log"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        {!selected ? (
          <div className="text-xs text-[var(--color-neo-text-secondary)]">Select a log file to view the last lines.</div>
        ) : tailQuery.isLoading ? (
          <div className="text-xs text-[var(--color-neo-text-secondary)]">Loading…</div>
        ) : (
          <pre className="neo-card p-2 bg-[var(--color-neo-bg)] overflow-auto text-[11px] font-mono whitespace-pre-wrap flex-1">
            {selectedText || '(empty)'}
          </pre>
        )}

        <div className="neo-card p-3 mt-3 bg-[var(--color-neo-bg)]">
          <div className="flex items-center justify-between mb-2">
            <div className="font-display font-bold uppercase text-xs">Prune</div>
            <button
              className="neo-btn neo-btn-primary text-xs py-1.5 px-2.5"
              onClick={async () => {
                await prune.mutateAsync({
                  keep_days: keepDays,
                  keep_files: keepFiles,
                  max_mb: maxMb,
                  dry_run: dryRun,
                })
                logsQuery.refetch()
              }}
              disabled={prune.isPending}
              title="Prune logs"
            >
              <Scissors size={14} />
              {dryRun ? 'Dry Run' : 'Prune'}
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div>
              <div className="text-[11px] font-mono text-[var(--color-neo-text-secondary)] mb-1">Keep days</div>
              <input
                type="number"
                min={0}
                max={3650}
                value={keepDays}
                onChange={(e) => setKeepDays(Math.max(0, Math.min(3650, Number(e.target.value) || 0)))}
                className="neo-btn text-xs py-1.5 px-2 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full"
              />
            </div>
            <div>
              <div className="text-[11px] font-mono text-[var(--color-neo-text-secondary)] mb-1">Keep files</div>
              <input
                type="number"
                min={0}
                max={100000}
                value={keepFiles}
                onChange={(e) => setKeepFiles(Math.max(0, Math.min(100000, Number(e.target.value) || 0)))}
                className="neo-btn text-xs py-1.5 px-2 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full"
              />
            </div>
            <div>
              <div className="text-[11px] font-mono text-[var(--color-neo-text-secondary)] mb-1">Max total (MB)</div>
              <input
                type="number"
                min={0}
                max={100000}
                value={maxMb}
                onChange={(e) => setMaxMb(Math.max(0, Math.min(100000, Number(e.target.value) || 0)))}
                className="neo-btn text-xs py-1.5 px-2 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full"
              />
            </div>
            <div className="flex items-end">
              <label className="neo-card p-2 w-full flex items-center justify-between cursor-pointer">
                <span className="font-display font-bold text-xs">Dry run</span>
                <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="w-4 h-4" />
              </label>
            </div>
          </div>

          {prune.data && (
            <div className="mt-2 text-[11px] font-mono text-[var(--color-neo-text-secondary)]">
              Deleted {prune.data.deleted_files} files ({formatBytes(prune.data.deleted_bytes)}), kept {prune.data.kept_files} files ({formatBytes(prune.data.kept_bytes)}).
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

