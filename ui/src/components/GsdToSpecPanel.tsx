import { useEffect, useMemo, useState } from 'react'
import { Loader2, Sparkles, RefreshCw } from 'lucide-react'
import { useSetupStatus } from '../hooks/useProjects'
import { useGsdStatus, useGsdToSpec } from '../hooks/useGsd'

export function GsdToSpecPanel({ projectName }: { projectName: string }) {
  const statusQuery = useGsdStatus(projectName)
  const run = useGsdToSpec(projectName)
  const { data: setup } = useSetupStatus()

  const [useCodex, setUseCodex] = useState(true)
  const [useGemini, setUseGemini] = useState(true)
  const [synthesizer, setSynthesizer] = useState<'' | 'none' | 'claude' | 'codex' | 'gemini'>('claude')
  const [timeoutS, setTimeoutS] = useState(600)

  useEffect(() => {
    if (!setup) return
    if (!setup.codex_cli) setUseCodex(false)
    if (!setup.gemini_cli) setUseGemini(false)
    if (!setup.codex_cli && synthesizer === 'codex') setSynthesizer('claude')
    if (!setup.gemini_cli && synthesizer === 'gemini') setSynthesizer('claude')
  }, [setup, synthesizer])

  const agentsList = useMemo(() => {
    const a: Array<'codex' | 'gemini'> = []
    if (useCodex) a.push('codex')
    if (useGemini) a.push('gemini')
    return a
  }, [useCodex, useGemini])

  const canRun =
    Boolean(statusQuery.data && statusQuery.data.exists && statusQuery.data.missing.length === 0) &&
    (agentsList.length > 0 || synthesizer === 'claude')

  return (
    <div className="neo-card p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Sparkles className="text-[var(--color-neo-accent)]" size={22} />
          <div>
            <div className="font-display font-bold uppercase">GSD → app_spec.txt</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Convert <code>.planning/codebase/*.md</code> into <code>prompts/app_spec.txt</code>.
            </div>
          </div>
        </div>

        <button
          className="neo-btn neo-btn-secondary text-sm"
          onClick={() => statusQuery.refetch()}
          disabled={statusQuery.isFetching}
          title="Refresh"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      <div className="mt-4 neo-card p-3">
        {statusQuery.isLoading ? (
          <div className="text-sm text-[var(--color-neo-text-secondary)]">Checking for GSD mapping…</div>
        ) : statusQuery.data ? (
          <div className="space-y-2">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
              Codebase dir: {statusQuery.data.codebase_dir}
            </div>
            {statusQuery.data.missing.length > 0 ? (
              <div className="text-sm">
                <div className="font-bold text-[var(--color-neo-danger)]">Missing required files</div>
                <div className="text-xs font-mono mt-1">{statusQuery.data.missing.join(', ')}</div>
              </div>
            ) : (
              <div className="text-sm">
                <div className="font-bold text-[var(--color-neo-progress)]">Ready</div>
                <div className="text-xs font-mono mt-1">
                  Found: {statusQuery.data.present.length ? statusQuery.data.present.join(', ') : '(none)'}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-[var(--color-neo-danger)]">Failed to check GSD status.</div>
        )}
      </div>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="neo-card p-3">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Synthesizer</div>
          <select
            value={synthesizer}
            onChange={(e) => setSynthesizer(e.target.value as any)}
            className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
          >
            <option value="claude">claude (default)</option>
            <option value="none">none</option>
            <option value="codex" disabled={setup ? !setup.codex_cli : false}>
              codex
            </option>
            <option value="gemini" disabled={setup ? !setup.gemini_cli : false}>
              gemini
            </option>
          </select>
        </div>

        <div className="neo-card p-3">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Timeout (s)</div>
          <input
            type="number"
            min={30}
            max={36000}
            value={timeoutS}
            onChange={(e) => setTimeoutS(Number(e.target.value))}
            className="neo-input"
          />
        </div>

        <div className="neo-card p-3">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Agents</div>
          <div className="flex flex-wrap gap-3 items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={useCodex}
                onChange={(e) => setUseCodex(e.target.checked)}
                disabled={setup ? !setup.codex_cli : false}
              />
              <span className="font-display font-bold text-sm">Codex</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={useGemini}
                onChange={(e) => setUseGemini(e.target.checked)}
                disabled={setup ? !setup.gemini_cli : false}
              />
              <span className="font-display font-bold text-sm">Gemini</span>
            </label>
            <span className="text-xs text-[var(--color-neo-text-secondary)] font-mono">
              {agentsList.length ? agentsList.join(', ') : '(none)'}
            </span>
          </div>
        </div>
      </div>

      {run.error && (
        <div className="mt-3 neo-card p-3 border-3 border-[var(--color-neo-danger)]">
          <div className="text-sm text-[var(--color-neo-danger)] font-bold">Error</div>
          <div className="text-sm">{run.error instanceof Error ? run.error.message : 'Generation failed'}</div>
        </div>
      )}

      {run.data && (
        <div className="mt-3 neo-card p-3">
          <div className="text-sm font-bold">Generated</div>
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mt-1">Output: {run.data.output_path}</div>
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">Drafts: {run.data.drafts_dir}</div>
        </div>
      )}

      <div className="mt-4 flex items-center justify-end gap-2">
        <button
          className="neo-btn neo-btn-primary text-sm"
          onClick={() =>
            run.mutate({
              agents: agentsList,
              synthesizer,
              timeout_s: timeoutS,
            })
          }
          disabled={!canRun || run.isPending}
          title={
            !canRun
              ? 'Missing required files or no engines selected'
              : 'Generate prompts/app_spec.txt from GSD mapping'
          }
        >
          {run.isPending ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
          Generate app_spec.txt
        </button>
      </div>
    </div>
  )
}

