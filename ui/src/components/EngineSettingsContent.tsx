/**
 * Engine Settings Content
 * =======================
 *
 * Per-project engine chains for workers, QA, review, and spec workflows.
 */

import { useEffect, useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, RefreshCcw, Save, Wrench } from 'lucide-react'
import { useEngineSettings, useUpdateEngineSettings } from '../hooks/useEngineSettings'
import { useSetupStatus } from '../hooks/useProjects'
import type { EngineId, EngineSettings, EngineStage } from '../lib/types'

type StageMeta = {
  id: EngineStage
  title: string
  description: string
  showIterations: boolean
}

const STAGES: StageMeta[] = [
  {
    id: 'implement',
    title: 'Implement',
    description: 'Primary worker chain used to implement features.',
    showIterations: true,
  },
  {
    id: 'qa_fix',
    title: 'QA Fix',
    description: 'Sub-agent chain used after Gatekeeper failures.',
    showIterations: true,
  },
  {
    id: 'review',
    title: 'Review',
    description: 'Reviewers that run in Gatekeeper before merge.',
    showIterations: false,
  },
  {
    id: 'spec_draft',
    title: 'Spec Draft',
    description: 'Draft engines for plan/spec generation.',
    showIterations: false,
  },
  {
    id: 'spec_synthesize',
    title: 'Spec Synthesize',
    description: 'Synthesis engine for spec/plan drafts.',
    showIterations: false,
  },
  {
    id: 'initializer',
    title: 'Initializer',
    description: 'Backlog generation engines.',
    showIterations: false,
  },
]

const ENGINE_LABELS: Record<EngineId, { label: string; hint: string }> = {
  codex_cli: { label: 'Codex CLI', hint: 'Requires codex on PATH' },
  gemini_cli: { label: 'Gemini CLI', hint: 'Requires gemini on PATH' },
  claude_patch: { label: 'Claude Patch', hint: 'Requires Claude CLI or credentials' },
  claude_review: { label: 'Claude Review', hint: 'Requires Claude CLI or credentials' },
  claude_spec: { label: 'Claude Spec', hint: 'Requires Claude CLI or credentials' },
}

const STAGE_ALLOWED: Record<EngineStage, EngineId[]> = {
  implement: ['codex_cli', 'gemini_cli', 'claude_patch'],
  qa_fix: ['codex_cli', 'gemini_cli', 'claude_patch'],
  review: ['claude_review', 'codex_cli', 'gemini_cli'],
  spec_draft: ['codex_cli', 'gemini_cli', 'claude_spec'],
  spec_synthesize: ['claude_spec'],
  initializer: ['codex_cli', 'gemini_cli', 'claude_spec'],
}

function clampInt(v: number, min: number, max: number): number {
  if (!Number.isFinite(v)) return min
  return Math.max(min, Math.min(max, Math.trunc(v)))
}

export function EngineSettingsContent({ projectName }: { projectName: string }) {
  const { data, isLoading, error, refetch } = useEngineSettings(projectName)
  const update = useUpdateEngineSettings()
  const { data: setup } = useSetupStatus()

  const [draft, setDraft] = useState<EngineSettings | null>(null)

  useEffect(() => {
    if (data) setDraft(data)
  }, [data])

  const availability = useMemo(() => {
    const hasCodex = Boolean(setup?.codex_cli)
    const hasGemini = Boolean(setup?.gemini_cli)
    const hasClaude = Boolean(setup?.claude_cli || setup?.credentials)
    return {
      codex_cli: hasCodex,
      gemini_cli: hasGemini,
      claude_patch: hasClaude,
      claude_review: hasClaude,
      claude_spec: hasClaude,
    }
  }, [setup])

  const validation = useMemo(() => {
    if (!draft) return { errors: [] as string[] }
    const errors: string[] = []
    for (const stage of STAGES) {
      const chain = draft.chains[stage.id]
      if (chain?.enabled && (!chain.engines || chain.engines.length === 0)) {
        errors.push(`${stage.title}: select at least one engine`)
      }
    }
    return { errors }
  }, [draft])

  const updateChain = (stage: EngineStage, updater: (chain: EngineSettings['chains'][EngineStage]) => EngineSettings['chains'][EngineStage]) => {
    if (!draft) return
    const next = { ...draft, chains: { ...draft.chains } }
    next.chains[stage] = updater({ ...next.chains[stage], engines: [...next.chains[stage].engines] })
    setDraft(next)
  }

  const moveEngine = (stage: EngineStage, index: number, direction: -1 | 1) => {
    updateChain(stage, (chain) => {
      const next = [...chain.engines]
      const target = index + direction
      if (target < 0 || target >= next.length) return chain
      const temp = next[index]
      next[index] = next[target]
      next[target] = temp
      return { ...chain, engines: next }
    })
  }

  const removeEngine = (stage: EngineStage, engine: EngineId) => {
    updateChain(stage, (chain) => ({ ...chain, engines: chain.engines.filter((e) => e !== engine) }))
  }

  const addEngine = (stage: EngineStage, engine: EngineId) => {
    updateChain(stage, (chain) => ({ ...chain, engines: chain.engines.includes(engine) ? chain.engines : [...chain.engines, engine] }))
  }

  const onSave = async () => {
    if (!draft) return
    await update.mutateAsync({ projectName, settings: draft })
  }

  return (
    <div className="space-y-6">
      <div className="neo-card p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <Wrench className="text-[var(--color-neo-accent)]" size={22} />
            <div>
              <div className="font-display font-bold uppercase">Engines</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)]">
                Per-project engine chains stored in <span className="font-mono">agent_system.db</span>.
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="neo-btn neo-btn-secondary text-sm"
              onClick={() => refetch()}
              disabled={isLoading}
              title="Reload"
            >
              <RefreshCcw size={18} />
              Reload
            </button>
            <button
              className="neo-btn neo-btn-primary text-sm"
              onClick={onSave}
              disabled={!draft || update.isPending || validation.errors.length > 0}
              title="Save engine settings"
            >
              <Save size={18} />
              Save
            </button>
          </div>
        </div>
      </div>

      {validation.errors.length > 0 && (
        <div className="neo-card p-4 bg-[var(--color-neo-danger)]/10 border-[var(--color-neo-danger)]">
          <div className="font-display font-bold text-[var(--color-neo-danger)]">Fix before saving</div>
          <ul className="text-sm list-disc pl-5 mt-1">
            {validation.errors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {isLoading && <div className="neo-card p-6">Loading…</div>}
      {!isLoading && error && (
        <div className="neo-card p-4 border-[var(--color-neo-danger)]">
          <div className="font-display font-bold text-[var(--color-neo-danger)]">Failed to load engine settings</div>
          <div className="text-sm mt-1">{String((error as any)?.message || error)}</div>
        </div>
      )}

      {!isLoading && draft && (
        <div className="space-y-4">
          {STAGES.map((stage) => {
            const chain = draft.chains[stage.id]
            const allowed = STAGE_ALLOWED[stage.id]
            const availableToAdd = allowed.filter((e) => !chain.engines.includes(e))
            return (
              <div key={stage.id} className="neo-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-display font-bold uppercase">{stage.title}</div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)] mt-1">{stage.description}</div>
                  </div>
                  <label className="neo-card p-2 flex items-center gap-2 cursor-pointer">
                    <span className="text-xs font-display font-bold">Enabled</span>
                    <input
                      type="checkbox"
                      checked={chain.enabled}
                      onChange={(e) => updateChain(stage.id, (c) => ({ ...c, enabled: e.target.checked }))}
                      className="w-4 h-4"
                    />
                  </label>
                </div>

                {stage.showIterations && (
                  <div className="mt-3">
                    <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Max iterations</div>
                    <input
                      className="neo-input w-[160px]"
                      type="number"
                      min={1}
                      max={20}
                      value={chain.max_iterations}
                      onChange={(e) =>
                        updateChain(stage.id, (c) => ({ ...c, max_iterations: clampInt(Number(e.target.value), 1, 20) }))
                      }
                    />
                  </div>
                )}

                <div className="mt-3 space-y-2">
                  {chain.engines.length === 0 && (
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">No engines selected.</div>
                  )}
                  {chain.engines.map((engine, idx) => {
                    const meta = ENGINE_LABELS[engine]
                    const isAvailable = availability[engine]
                    return (
                      <div key={`${stage.id}-${engine}`} className="neo-card p-2 flex items-center justify-between gap-2">
                        <div>
                          <div className="font-display text-sm font-bold">{meta.label}</div>
                          <div className={`text-[10px] ${isAvailable ? 'text-[var(--color-neo-text-secondary)]' : 'text-[var(--color-neo-danger)]'}`}>
                            {isAvailable ? meta.hint : 'Not detected'}
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            className="neo-btn neo-btn-secondary neo-btn-sm"
                            onClick={() => moveEngine(stage.id, idx, -1)}
                            disabled={idx === 0}
                            title="Move up"
                          >
                            <ArrowUp size={14} />
                          </button>
                          <button
                            className="neo-btn neo-btn-secondary neo-btn-sm"
                            onClick={() => moveEngine(stage.id, idx, 1)}
                            disabled={idx === chain.engines.length - 1}
                            title="Move down"
                          >
                            <ArrowDown size={14} />
                          </button>
                          <button
                            className="neo-btn neo-btn-secondary neo-btn-sm"
                            onClick={() => removeEngine(stage.id, engine)}
                            title="Remove engine"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <select
                    className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display"
                    value=""
                    onChange={(e) => {
                      const value = e.target.value as EngineId
                      if (value) addEngine(stage.id, value)
                    }}
                  >
                    <option value="">Add engine…</option>
                    {availableToAdd.map((engine) => {
                      const meta = ENGINE_LABELS[engine]
                      const available = availability[engine]
                      return (
                        <option key={`${stage.id}-add-${engine}`} value={engine} disabled={!available}>
                          {meta.label} {available ? '' : '(missing)'}
                        </option>
                      )
                    })}
                  </select>
                  <div className="text-xs text-[var(--color-neo-text-secondary)]">
                    Order matters. First engine runs first.
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
