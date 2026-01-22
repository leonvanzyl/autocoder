/**
 * Diagnostics Content
 * ===================
 *
 * Runs deterministic end-to-end fixtures to validate core reliability pipelines.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, CheckCircle2, Copy, Play, RefreshCcw, Save, XCircle } from 'lucide-react'
import { useAdvancedSettings, useUpdateAdvancedSettings } from '../hooks/useAdvancedSettings'
import {
  useDiagnosticsFixturesDir,
  useDiagnosticsRuns,
  useDiagnosticsRunTail,
  useRunQAProviderE2E,
  useRunParallelMiniE2E,
} from '../hooks/useDiagnostics'
import { useHealthCheck, useProjects, useSetupStatus } from '../hooks/useProjects'
import { useCleanupQueue, useClearCleanupQueue, useProcessCleanupQueue } from '../hooks/useWorktrees'
import { useBackendVersion } from '../hooks/useVersion'
import type { EngineId } from '../lib/types'
import { UI_BUILD_ID } from '../lib/buildInfo'
import { InlineNotice, type InlineNoticeType } from './InlineNotice'

export function DiagnosticsContent() {
  const advanced = useAdvancedSettings()
  const updateAdvanced = useUpdateAdvancedSettings()
  const fixtures = useDiagnosticsFixturesDir()
  const runs = useDiagnosticsRuns(25)
  const run = useRunQAProviderE2E()
  const runMini = useRunParallelMiniE2E()
  const setup = useSetupStatus()
  const health = useHealthCheck()
  const projects = useProjects()
  const backendVersion = useBackendVersion()

  const [fixture, setFixture] = useState<'node' | 'python'>('node')
  const [qaEngines, setQaEngines] = useState<EngineId[]>(['claude_patch', 'codex_cli', 'gemini_cli'])
  const [timeoutS, setTimeoutS] = useState<number>(240)
  const [miniParallel, setMiniParallel] = useState<number>(3)
  const [miniPreset, setMiniPreset] = useState<string>('balanced')
  const [miniTimeoutS, setMiniTimeoutS] = useState<number>(1200)
  const [outDirDraft, setOutDirDraft] = useState<string>('')
  const [selectedRunName, setSelectedRunName] = useState<string | null>(null)
  const [tailMaxChars, setTailMaxChars] = useState<number>(8000)
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [cleanupMaxItems, setCleanupMaxItems] = useState<number>(5)
  const [notice, setNotice] = useState<{ type: InlineNoticeType; message: string } | null>(null)
  const noticeTimer = useRef<number | null>(null)

  const tail = useDiagnosticsRunTail(selectedRunName, tailMaxChars)
  const cleanup = useCleanupQueue(selectedProject)
  const processCleanup = useProcessCleanupQueue(selectedProject || '')
  const clearCleanup = useClearCleanupQueue(selectedProject || '')

  const effectiveOutDir = useMemo(() => fixtures.data?.effective_dir || '', [fixtures.data])
  const toggleEngine = (engine: EngineId) => {
    setQaEngines((prev) => (prev.includes(engine) ? prev.filter((e) => e !== engine) : [...prev, engine]))
  }

  const canSave = !!advanced.data && !updateAdvanced.isPending
  const flash = (type: InlineNoticeType, message: string) => {
    setNotice({ type, message })
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(null), 2500)
  }
  const onSaveOutDir = async () => {
    if (!advanced.data) return
    try {
      await updateAdvanced.mutateAsync({
        ...advanced.data,
        diagnostics_fixtures_dir: outDirDraft,
      })
      fixtures.refetch()
      flash('success', 'Diagnostics directory saved.')
    } catch (e: any) {
      flash('error', String(e?.message || e))
    }
  }

  const onUseDefault = async () => {
    setOutDirDraft('')
    if (!advanced.data) return
    try {
      await updateAdvanced.mutateAsync({
        ...advanced.data,
        diagnostics_fixtures_dir: '',
      })
      fixtures.refetch()
      flash('success', 'Diagnostics directory reset to default.')
    } catch (e: any) {
      flash('error', String(e?.message || e))
    }
  }

  // Keep the draft in sync with server settings (first load).
  useEffect(() => {
    if (!advanced.data) return
    if (outDirDraft !== '') return
    const v = (advanced.data.diagnostics_fixtures_dir || '').trim()
    if (v) setOutDirDraft(v)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [advanced.data])

  const lastQAResult = run.data
  const lastMiniResult = runMini.data
  const lastResult = lastMiniResult || lastQAResult

  // Pick a default project when available.
  useEffect(() => {
    if (selectedProject) return
    const first = projects.data?.[0]
    if (first?.name) setSelectedProject(first.name)
  }, [projects.data, selectedProject])

  useEffect(() => {
    return () => {
      if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    }
  }, [])


  // Auto-select the newest run when a run completes.
  useEffect(() => {
    const logPath = lastResult?.log_path
    if (!logPath) return
    const name = logPath.split(/[/\\\\]/).pop() || null
    if (name) setSelectedRunName(name)
    runs.refetch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastQAResult?.log_path, lastMiniResult?.log_path])

  // Auto-select the most recent run (first load).
  useEffect(() => {
    if (selectedRunName) return
    const first = runs.data?.[0]
    if (first?.name) setSelectedRunName(first.name)
  }, [runs.data, selectedRunName])

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // no-op
    }
  }

  const qaEngineOptions: Array<{ id: EngineId; label: string; available: boolean; hint: string }> = useMemo(() => {
    const hasCodex = Boolean(setup.data?.codex_cli)
    const hasGemini = Boolean(setup.data?.gemini_cli)
    const hasClaude = Boolean(setup.data?.claude_cli || setup.data?.credentials)
    return [
      { id: 'codex_cli', label: 'Codex CLI', available: hasCodex, hint: 'Requires codex on PATH' },
      { id: 'gemini_cli', label: 'Gemini CLI', available: hasGemini, hint: 'Requires gemini on PATH' },
      { id: 'claude_patch', label: 'Claude Patch', available: hasClaude, hint: 'Requires Claude CLI or credentials' },
    ]
  }, [setup.data])

  // Keep QA engine defaults sane: Claude first, and only engines that are actually available.
  useEffect(() => {
    if (!setup.data) return
    const available = new Set<EngineId>()
    if (setup.data.claude_cli || setup.data.credentials) available.add('claude_patch')
    if (setup.data.codex_cli) available.add('codex_cli')
    if (setup.data.gemini_cli) available.add('gemini_cli')

    setQaEngines((prev) => {
      const next = prev.filter((e) => available.has(e))
      const withClaude = next.includes('claude_patch') ? next : ['claude_patch', ...next]
      // Keep stable order
      const ordered: EngineId[] = []
      for (const e of ['claude_patch', 'codex_cli', 'gemini_cli'] as const) {
        if (withClaude.includes(e) && !ordered.includes(e)) ordered.push(e)
      }
      return ordered.length ? ordered : ['claude_patch']
    })
  }, [setup.data])

  return (
    <div className="space-y-6">
      <div className="neo-card p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <Activity className="text-[var(--color-neo-accent)]" size={22} />
            <div>
              <div className="font-display font-bold uppercase">Diagnostics</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)]">
                Deterministic fixtures to validate Gatekeeper + QA pipelines.
              </div>
            </div>
          </div>
          <button className="neo-btn neo-btn-secondary text-sm" onClick={() => fixtures.refetch()} title="Refresh">
            <RefreshCcw size={18} />
            Refresh
          </button>
        </div>
      </div>

      {notice && (
        <InlineNotice type={notice.type} message={notice.message} onClose={() => setNotice(null)} />
      )}

      <div className="neo-card p-4">
        <div className="font-display font-bold uppercase mb-3">System Status</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="neo-card p-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Server</div>
            <div className="flex items-center gap-2">
              {health.data?.status === 'healthy' ? (
                <>
                  <CheckCircle2 className="text-green-700" size={18} />
                  <div className="font-display text-sm">healthy</div>
                </>
              ) : health.isError ? (
                <>
                  <XCircle className="text-red-600" size={18} />
                  <div className="font-display text-sm">unreachable</div>
                </>
              ) : (
                <div className="text-sm text-[var(--color-neo-text-secondary)]">checking…</div>
              )}
            </div>
          </div>
          <div className="neo-card p-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Tools</div>
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              {[
                ['claude', !!setup.data?.claude_cli],
                ['credentials', !!setup.data?.credentials],
                ['node', !!setup.data?.node],
                ['npm', !!setup.data?.npm],
                ['codex', !!setup.data?.codex_cli],
                ['gemini', !!setup.data?.gemini_cli],
              ].map(([label, ok]) => (
                <div key={label as string} className="flex items-center gap-2">
                  {ok ? (
                    <CheckCircle2 className="text-green-700" size={16} />
                  ) : (
                    <XCircle className="text-red-600" size={16} />
                  )}
                  <span>{label as string}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="neo-card p-3 mt-3">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Build Info</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs font-mono">
            <div className="neo-card p-2">
              <div className="text-[var(--color-neo-text-muted)]">UI</div>
              <div className="break-all">{UI_BUILD_ID}</div>
            </div>
            <div className="neo-card p-2">
              <div className="text-[var(--color-neo-text-muted)]">Backend</div>
              <div className="break-all">
                {backendVersion.data?.git_sha || backendVersion.isLoading ? '…' : 'n/a'}
              </div>
            </div>
            <div className="neo-card p-2">
              <div className="text-[var(--color-neo-text-muted)]">Package</div>
              <div className="break-all">
                {backendVersion.data?.package_version || backendVersion.isLoading ? '…' : 'n/a'}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 mt-3">
            <div className="text-xs text-[var(--color-neo-text-secondary)]">
              If the UI looks broken, try a hard refresh (we disable caching for index.html, but browsers still get spicy sometimes).
            </div>
            <div className="flex items-center gap-2">
              <button
                className="neo-btn neo-btn-secondary text-sm"
                onClick={() => window.location.reload()}
                title="Hard refresh"
              >
                <RefreshCcw size={18} />
                Refresh
              </button>
              <button
                className="neo-btn neo-btn-secondary text-sm"
                onClick={() =>
                  copyToClipboard(
                    JSON.stringify(
                      {
                        ui_build: UI_BUILD_ID,
                        backend_git: backendVersion.data?.git_sha || null,
                        backend_package: backendVersion.data?.package_version || null,
                        tools: setup.data || null,
                      },
                      null,
                      2,
                    ),
                  )
                }
                title="Copy debug info"
              >
                <Copy size={18} />
                Copy
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="neo-card p-4">
        <div className="font-display font-bold uppercase mb-3">Fixtures Directory</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="neo-card p-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Configured</div>
            <input
              className="neo-input w-full"
              value={outDirDraft}
              onChange={(e) => setOutDirDraft(e.target.value)}
              placeholder={fixtures.data?.default_dir || 'default'}
            />
            <div className="flex gap-2 mt-3">
              <button className="neo-btn neo-btn-primary text-sm" disabled={!canSave} onClick={onSaveOutDir} title="Save">
                <Save size={18} />
                Save
              </button>
              <button className="neo-btn neo-btn-secondary text-sm" disabled={!canSave} onClick={onUseDefault} title="Use default">
                Use default
              </button>
            </div>
          </div>
          <div className="neo-card p-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Effective</div>
            <div className="font-mono text-sm break-all">{effectiveOutDir || '(loading...)'}</div>
            <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
              Default is a repo-local test directory when available.
            </div>
          </div>
        </div>
      </div>

      <div className="neo-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="font-display font-bold uppercase">Worktree Cleanup</div>
          <div className="flex items-center gap-2">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">Project</div>
            <select
              value={selectedProject || ''}
              onChange={(e) => setSelectedProject(e.target.value || null)}
              className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display"
            >
              {(projects.data || []).map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="neo-card p-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Cleanup queue</div>
            <div className="text-sm font-mono break-all text-[var(--color-neo-text-secondary)]">
              {cleanup.data?.queue_path || '(loading...)'}
            </div>
            <div className="mt-2 text-sm">
              Items: <span className="font-mono">{cleanup.data?.items?.length ?? 0}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">Process</div>
              <input
                className="neo-input w-[120px]"
                type="number"
                min={1}
                max={100}
                value={cleanupMaxItems}
                onChange={(e) => setCleanupMaxItems(Number(e.target.value))}
              />
              <button
                className="neo-btn neo-btn-secondary text-sm"
                disabled={!selectedProject || processCleanup.isPending}
                onClick={async () => {
                  await processCleanup.mutateAsync(cleanupMaxItems)
                  cleanup.refetch()
                }}
                title="Attempt deletion of queued worktrees"
              >
                <RefreshCcw size={18} />
                Run
              </button>
              <button
                className="neo-btn neo-btn-secondary text-sm"
                disabled={!selectedProject || clearCleanup.isPending}
                onClick={async () => {
                  await clearCleanup.mutateAsync()
                  cleanup.refetch()
                }}
                title="Clear the queue file (does not delete any directories)"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="neo-card p-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Items</div>
            <div className="space-y-2 max-h-[260px] overflow-auto">
              {(cleanup.data?.items || []).map((it, idx) => (
                <div key={`${it.path}-${idx}`} className="neo-card p-2 bg-white border-3 border-[var(--color-neo-border)]">
                  <div className="text-[11px] font-mono break-all">{it.path}</div>
                  <div className="text-[10px] font-mono text-[var(--color-neo-text-secondary)] mt-1">
                    attempts={it.attempts} next={it.next_try_at ? new Date(it.next_try_at * 1000).toLocaleString() : '-'}
                  </div>
                  {it.reason && (
                    <div className="text-[10px] text-[var(--color-neo-text-secondary)] mt-1">{it.reason}</div>
                  )}
                </div>
              ))}
              {cleanup.isLoading && <div className="text-xs text-[var(--color-neo-text-secondary)]">Loading…</div>}
              {!cleanup.isLoading && (cleanup.data?.items || []).length === 0 && (
                <div className="text-xs text-[var(--color-neo-text-secondary)]">Queue is empty.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="neo-card p-4">
        <div className="font-display font-bold uppercase mb-3">QA Engine E2E</div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Fixture</div>
            <select
              value={fixture}
              onChange={(e) => setFixture(e.target.value as any)}
              className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
            >
              <option value="node">node</option>
              <option value="python">python</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Engines</div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {qaEngineOptions.map((opt) => (
                <label key={opt.id} className="neo-card p-2 flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={qaEngines.includes(opt.id)}
                    onChange={() => toggleEngine(opt.id)}
                    disabled={!opt.available && !qaEngines.includes(opt.id)}
                    className="w-4 h-4"
                  />
                  <div>
                    <div className="text-xs font-display font-bold">{opt.label}</div>
                    <div className={`text-[10px] ${opt.available ? 'text-[var(--color-neo-text-secondary)]' : 'text-[var(--color-neo-danger)]'}`}>
                      {opt.available ? opt.hint : 'Not detected'}
                    </div>
                  </div>
                </label>
              ))}
            </div>
            <div className="text-[11px] text-[var(--color-neo-text-secondary)] mt-2">
              Select at least one engine. Missing CLIs are skipped during the run.
            </div>
          </div>
          <div>
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Timeout (s)</div>
            <input
              className="neo-input w-full"
              type="number"
              min={30}
              max={3600}
              value={timeoutS}
              onChange={(e) => setTimeoutS(Number(e.target.value))}
            />
          </div>
          <div className="flex items-end">
            <button
              className="neo-btn neo-btn-primary w-full text-sm"
              disabled={run.isPending || qaEngines.length === 0}
              onClick={() => run.mutate({ fixture, engines: qaEngines, timeout_s: timeoutS })}
              title="Run fixture"
            >
              <Play size={18} />
              Run
            </button>
          </div>
        </div>

        {lastQAResult && (
          <div className="neo-card p-3 mt-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="font-display font-bold text-sm uppercase">
                Result: {lastQAResult.success ? 'PASS' : 'FAIL'} (exit {lastQAResult.exit_code})
              </div>
              <div className="text-xs font-mono break-all text-[var(--color-neo-text-secondary)]">
                Log: {lastQAResult.log_path}
              </div>
            </div>
            <pre className="neo-code mt-3 max-h-[360px] overflow-auto whitespace-pre-wrap">
              {lastQAResult.output_tail}
            </pre>
          </div>
        )}
      </div>

      <div className="neo-card p-4">
        <div className="font-display font-bold uppercase mb-3">Parallel Mini E2E</div>
        <div className="text-xs text-[var(--color-neo-text-secondary)] mb-3">
          Runs a tiny repo end-to-end in parallel mode (workers + Gatekeeper merge). Can take a few minutes.
        </div>
        <div className="neo-card p-3 mb-3 bg-[var(--color-neo-bg)]">
          <div className="text-xs text-[var(--color-neo-text-secondary)]">
            Note: this fixture uses a deterministic dummy worker (
            <span className="font-mono">AUTOCODER_E2E_DUMMY_WORKER=1</span>) so it validates orchestration without
            requiring an LLM. Use it to test reliability/coordination, not model quality.
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Agents</div>
            <select
              value={miniParallel}
              onChange={(e) => setMiniParallel(Number(e.target.value))}
              className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={4}>4</option>
              <option value={5}>5</option>
            </select>
          </div>
          <div>
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Preset</div>
            <input
              className="neo-input w-full"
              value={miniPreset}
              onChange={(e) => setMiniPreset(e.target.value)}
              placeholder="balanced"
            />
          </div>
          <div>
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Timeout (s)</div>
            <input
              className="neo-input w-full"
              type="number"
              min={60}
              max={7200}
              value={miniTimeoutS}
              onChange={(e) => setMiniTimeoutS(Number(e.target.value))}
            />
          </div>
          <div className="flex items-end">
            <button
              className="neo-btn neo-btn-primary w-full text-sm"
              disabled={runMini.isPending}
              onClick={() => runMini.mutate({ parallel: miniParallel, preset: miniPreset, timeout_s: miniTimeoutS })}
              title="Run fixture"
            >
              <Play size={18} />
              Run
            </button>
          </div>
        </div>

        {lastMiniResult && (
          <div className="neo-card p-3 mt-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="font-display font-bold text-sm uppercase">
                Result: {lastMiniResult.success ? 'PASS' : 'FAIL'} (exit {lastMiniResult.exit_code})
              </div>
              <div className="text-xs font-mono break-all text-[var(--color-neo-text-secondary)]">
                Log: {lastMiniResult.log_path}
              </div>
            </div>
            <pre className="neo-code mt-3 max-h-[360px] overflow-auto whitespace-pre-wrap">
              {lastMiniResult.output_tail}
            </pre>
          </div>
        )}
      </div>

      <div className="neo-card p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="font-display font-bold uppercase">Run Logs</div>
          <button className="neo-btn neo-btn-secondary text-sm" onClick={() => runs.refetch()} title="Refresh list">
            <RefreshCcw size={18} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="neo-card p-3 md:col-span-1">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Recent runs</div>
            <div className="space-y-2 max-h-[340px] overflow-auto">
              {(runs.data || []).map((r) => (
                <button
                  key={r.name}
                  className={`neo-btn w-full text-left text-xs font-mono px-3 py-2 ${
                    selectedRunName === r.name ? 'neo-btn-primary' : 'neo-btn-secondary'
                  }`}
                  onClick={() => setSelectedRunName(r.name)}
                  title={r.path}
                >
                  <div className="truncate">{r.name}</div>
                  <div className="text-[10px] opacity-70 truncate">{new Date(r.modified_at).toLocaleString()}</div>
                </button>
              ))}
              {runs.isLoading && (
                <div className="text-xs text-[var(--color-neo-text-secondary)]">Loading…</div>
              )}
              {!runs.isLoading && (runs.data || []).length === 0 && (
                <div className="text-xs text-[var(--color-neo-text-secondary)]">
                  No diagnostics runs yet. Run a fixture to generate logs.
                </div>
              )}
            </div>
          </div>

          <div className="neo-card p-3 md:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">Selected</div>
              <div className="flex items-center gap-2">
                <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">Tail (chars)</div>
                <input
                  className="neo-input w-[120px]"
                  type="number"
                  min={200}
                  max={200000}
                  value={tailMaxChars}
                  onChange={(e) => setTailMaxChars(Number(e.target.value))}
                />
                <button
                  className="neo-btn neo-btn-secondary text-sm"
                  disabled={!selectedRunName}
                  onClick={() => tail.refetch()}
                  title="Refresh tail"
                >
                  <RefreshCcw size={18} />
                  Refresh
                </button>
              </div>
            </div>

            <div className="mt-2 text-sm font-mono break-all">{selectedRunName || '(none selected)'}</div>

            {tail.data?.path && (
              <div className="flex flex-wrap items-center justify-between gap-2 mt-2">
                <div className="text-xs font-mono break-all text-[var(--color-neo-text-secondary)]">
                  Path: {tail.data.path}
                </div>
                <button
                  className="neo-btn neo-btn-secondary text-sm"
                  onClick={() => copyToClipboard(tail.data!.path)}
                  title="Copy path"
                >
                  <Copy size={18} />
                  Copy
                </button>
              </div>
            )}

            {tail.isError && (
              <div className="neo-card p-3 mt-3 text-sm text-red-600">
                {(tail.error as any)?.message || 'Failed to load log tail'}
              </div>
            )}

            <pre className="neo-code mt-3 max-h-[420px] overflow-auto whitespace-pre-wrap">
              {tail.data?.tail || (selectedRunName ? '(loading...)' : '')}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
