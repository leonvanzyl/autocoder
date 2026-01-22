/**
 * Engine Settings Content
 * =======================
 *
 * Per-project engine chains for workers, QA, review, and spec workflows.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, CheckCircle2, Info, RefreshCcw, Save, Wrench } from 'lucide-react'
import { useEngineSettings, useUpdateEngineSettings } from '../hooks/useEngineSettings'
import { useSetupStatus } from '../hooks/useProjects'
import type { EngineId, EngineSettings, EngineStage } from '../lib/types'
import { InlineNotice, type InlineNoticeType } from './InlineNotice'
import { HelpModal } from './HelpModal'

type HelpTopic = 'all' | EngineStage

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
  const [showHelp, setShowHelp] = useState(false)
  const [helpTopic, setHelpTopic] = useState<HelpTopic>('all')
  const [justSaved, setJustSaved] = useState(false)
  const [notice, setNotice] = useState<{ type: InlineNoticeType; message: string } | null>(null)
  const noticeTimer = useRef<number | null>(null)
  const savedTimer = useRef<number | null>(null)

  useEffect(() => {
    if (data) setDraft(data)
  }, [data])

  useEffect(() => {
    return () => {
      if (noticeTimer.current) {
        window.clearTimeout(noticeTimer.current)
      }
      if (savedTimer.current) {
        window.clearTimeout(savedTimer.current)
      }
    }
  }, [])

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

  const flash = (type: InlineNoticeType, message: string) => {
    setNotice({ type, message })
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(null), 2500)
  }

  const onSave = async () => {
    if (!draft) return
    try {
      await update.mutateAsync({ projectName, settings: draft })
      flash('success', 'Engine settings saved.')
      setJustSaved(true)
      if (savedTimer.current) window.clearTimeout(savedTimer.current)
      savedTimer.current = window.setTimeout(() => setJustSaved(false), 2000)
    } catch (e: any) {
      flash('error', String(e?.message || e))
    }
  }

  const openHelp = (topic: HelpTopic) => {
    setHelpTopic(topic)
    setShowHelp(true)
  }

  const helpContent: Record<EngineStage, { title: string; body: string }> = {
    implement: {
      title: 'Implement (feature worker chain)',
      body:
        'This chain is used to implement features. Order matters: engines are tried in sequence until the feature is implemented and submitted to Gatekeeper. Keep Claude first by default; add Codex/Gemini as extra “eyes” if you want.',
    },
    qa_fix: {
      title: 'QA Fix (after Gatekeeper failure)',
      body:
        'If Gatekeeper rejects a feature (tests/lint/typecheck), AutoCoder can spawn a short-lived QA fixer that only targets the failure excerpt and resubmits. This chain controls which engines are tried for that fix loop.',
    },
    review: {
      title: 'Review (Gatekeeper reviewers)',
      body:
        'Optional review step that runs before merge. Use this for “another pass” (style, safety, correctness) without changing feature scope. If disabled, Gatekeeper goes straight to verification commands.',
    },
    spec_draft: {
      title: 'Spec Draft (planning)',
      body:
        'Draft engines used for planning/spec generation. These create draft artifacts that can then be synthesized into a single final spec/plan.',
    },
    spec_synthesize: {
      title: 'Spec Synthesize (final merge)',
      body:
        'The final “merge drafts into one” engine. Claude is the default because it tends to be best at consolidating multiple drafts into one coherent spec.',
    },
    initializer: {
      title: 'Initializer (backlog creation)',
      body:
        'Used to expand a project spec into a backlog of features (seed the database). This is typically Claude-based; add other engines only if you want extra draft diversity.',
    },
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
              onClick={() => openHelp('all')}
              title="Explain engine chains"
            >
              <Info size={16} />
              Help
            </button>
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
              {justSaved ? <CheckCircle2 size={18} /> : <Save size={18} />}
              {justSaved ? 'Saved' : 'Save'}
            </button>
          </div>
        </div>
      </div>

      {notice && (
        <InlineNotice type={notice.type} message={notice.message} onClose={() => setNotice(null)} />
      )}

      <HelpModal isOpen={showHelp} title="Engine Chains — how this works" onClose={() => setShowHelp(false)}>
        <div className="space-y-4 text-sm">
          {helpTopic !== 'all' && (
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
                Tip: click other ⓘ icons for section-specific help.
              </div>
              <button className="neo-btn neo-btn-secondary text-sm" onClick={() => setHelpTopic('all')}>
                Show all
              </button>
            </div>
          )}

          {helpTopic === 'all' ? (
            <div className="space-y-3">
              <div className="neo-card p-3 bg-[var(--color-neo-bg)]">
                <div className="font-display font-bold uppercase">Engine chains (quick mental model)</div>
                <div className="text-[var(--color-neo-text-secondary)] mt-1">
                  Each stage has an ordered list of engines. AutoCoder tries them in order. Keep the first engine as your
                  “default” and add others as optional fallbacks or second opinions.
                </div>
              </div>
              {(Object.keys(helpContent) as EngineStage[]).map((stage) => (
                <div key={stage} className="neo-card p-3 bg-[var(--color-neo-bg)]">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-display font-bold uppercase">{helpContent[stage].title}</div>
                    <button className="neo-btn neo-btn-secondary text-sm" onClick={() => setHelpTopic(stage)}>
                      Details
                    </button>
                  </div>
                  <div className="text-[var(--color-neo-text-secondary)] mt-1">{helpContent[stage].body}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
              <div className="font-display font-bold uppercase">{helpContent[helpTopic].title}</div>
              <div className="text-[var(--color-neo-text-secondary)] mt-2">{helpContent[helpTopic].body}</div>
            </div>
          )}
        </div>
      </HelpModal>

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
            const availableToAdd = allowed.filter((e) => availability[e]).filter((e) => !chain.engines.includes(e))
            return (
              <div key={stage.id} className="neo-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    <div>
                      <div className="font-display font-bold uppercase">{stage.title}</div>
                      <div className="text-xs text-[var(--color-neo-text-secondary)] mt-1">{stage.description}</div>
                    </div>
                    <button
                      className="neo-btn neo-btn-ghost p-1"
                      onClick={() => openHelp(stage.id)}
                      title={`About ${stage.title}`}
                      aria-label={`About ${stage.title}`}
                    >
                      <Info size={16} />
                    </button>
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
                      <div
                        key={`${stage.id}-${engine}`}
                        className={`neo-card p-2 flex items-center justify-between gap-2 ${isAvailable ? '' : 'opacity-70'}`}
                      >
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
                  {availableToAdd.length > 0 ? (
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
                        return (
                          <option key={`${stage.id}-add-${engine}`} value={engine}>
                            {meta.label}
                          </option>
                        )
                      })}
                    </select>
                  ) : (
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">
                      No additional engines detected for this stage.
                    </div>
                  )}
                  <div className="text-xs text-[var(--color-neo-text-secondary)]">
                    Order matters. First engine runs first.
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <HelpModal isOpen={showHelp} title="Engine Chains — how this works" onClose={() => setShowHelp(false)}>
        <div className="space-y-3 text-sm">
          <p>
            Engine chains define <span className="font-bold">who runs first</span> for each stage (feature workers, QA
            fixes, review, spec drafts, initializer).
          </p>
          <div className="neo-card p-3 bg-[var(--color-neo-bg)] space-y-2">
            <div className="font-display font-bold uppercase text-xs">Order matters</div>
            <p className="text-[var(--color-neo-text-secondary)]">
              Engines run top → bottom until a patch/review succeeds. Put the most reliable engine first.
            </p>
          </div>
          <div className="neo-card p-3 bg-[var(--color-neo-bg)] space-y-2">
            <div className="font-display font-bold uppercase text-xs">Claude-first defaults</div>
            <p className="text-[var(--color-neo-text-secondary)]">
              Defaults start with Claude. Add Codex/Gemini only if you want multi‑model passes and the CLIs are detected.
            </p>
          </div>
          <div className="text-xs text-[var(--color-neo-text-secondary)]">
            Missing CLIs are shown as “Not detected” and are skipped at runtime.
          </div>
        </div>
      </HelpModal>
    </div>
  )
}
