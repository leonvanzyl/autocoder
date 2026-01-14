/**
 * Advanced Settings Content
 * =========================
 *
 * Server-backed settings that affect subprocess env vars when starting agents/orchestrator from the UI.
 * Intended to be embedded in a page (not a modal).
 */

import { useEffect, useMemo, useState } from 'react'
import { Save, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { useAdvancedSettings, useUpdateAdvancedSettings } from '../hooks/useAdvancedSettings'
import type { AdvancedSettings } from '../lib/types'

function clampInt(v: number, min: number, max: number): number {
  if (!Number.isFinite(v)) return min
  return Math.max(min, Math.min(max, Math.trunc(v)))
}

const DEFAULTS: AdvancedSettings = {
  review_enabled: false,
  review_mode: 'off',
  review_type: 'none',
  review_command: '',
  review_timeout_s: 0,
  review_model: '',
  review_agents: '',
  review_consensus: '',
  codex_model: '',
  codex_reasoning_effort: '',
  gemini_model: '',
  locks_enabled: false,
  worker_verify: true,
  qa_fix_enabled: false,
  qa_model: '',
  qa_max_sessions: 0,
  controller_enabled: false,
  controller_model: '',
  controller_max_sessions: 0,
  logs_keep_days: 7,
  logs_keep_files: 200,
  logs_max_total_mb: 200,
  sdk_max_attempts: 3,
  sdk_initial_delay_s: 1,
  sdk_rate_limit_initial_delay_s: 30,
  sdk_max_delay_s: 60,
  sdk_exponential_base: 2,
  sdk_jitter: true,
  require_gatekeeper: true,
  allow_no_tests: false,
  api_port_range_start: 5000,
  api_port_range_end: 5100,
  web_port_range_start: 5173,
  web_port_range_end: 5273,
  skip_port_check: false,
}

export function AdvancedSettingsContent() {
  const { data, isLoading } = useAdvancedSettings()
  const update = useUpdateAdvancedSettings()

  const [draft, setDraft] = useState<AdvancedSettings>(DEFAULTS)
  const [tab, setTab] = useState<'automation' | 'gatekeeper' | 'logs' | 'retry' | 'ports'>('automation')

  useEffect(() => {
    if (data) setDraft(data)
  }, [data])

  const validationError = useMemo(() => {
    if (draft.api_port_range_end <= draft.api_port_range_start) return 'API port range end must be > start'
    if (draft.web_port_range_end <= draft.web_port_range_start) return 'WEB port range end must be > start'
    return null
  }, [draft])

  const saveDisabled = isLoading || update.isPending || !!validationError

  const onSave = async () => {
    if (validationError) return
    await update.mutateAsync(draft)
  }

  return (
    <div className="space-y-6">
      <div className="neo-card p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <SlidersHorizontal className="text-[var(--color-neo-accent)]" size={22} />
            <div>
              <div className="font-display font-bold uppercase">Advanced</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)]">
                Applied when the UI starts agents/orchestrator (env vars).
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              className="neo-btn neo-btn-secondary text-sm"
              onClick={() => setDraft(DEFAULTS)}
              disabled={update.isPending}
              title="Reset to defaults"
            >
              <RotateCcw size={18} />
              Reset
            </button>
            <button className="neo-btn neo-btn-primary text-sm" onClick={onSave} disabled={saveDisabled} title="Save">
              <Save size={18} />
              Save
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className={`neo-btn text-sm ${tab === 'automation' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('automation')}
          >
            Automation
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'gatekeeper' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('gatekeeper')}
          >
            Gatekeeper
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'logs' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('logs')}
          >
            Logs
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'retry' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('retry')}
          >
            Retry/Backoff
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'ports' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('ports')}
          >
            Ports
          </button>
        </div>
      </div>

      {validationError && (
        <div className="neo-card p-4 bg-[var(--color-neo-danger)]/10 border-[var(--color-neo-danger)]">
          <div className="font-display font-bold text-[var(--color-neo-danger)]">Fix before saving</div>
          <div className="text-sm">{validationError}</div>
        </div>
      )}

      {isLoading ? (
        <div className="neo-card p-6">Loading…</div>
      ) : (
        <>
          {tab === 'automation' && (
            <div className="space-y-4">
              <div className="neo-card p-4">
                <div className="font-display font-bold uppercase mb-3">Review</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Enable review</span>
                    <input
                      type="checkbox"
                      checked={draft.review_enabled}
                      onChange={(e) => setDraft({ ...draft, review_enabled: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </label>

                  <div className="neo-card p-3">
                    <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Mode</div>
                    <select
                      value={draft.review_mode}
                      onChange={(e) => setDraft({ ...draft, review_mode: e.target.value })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="off">off</option>
                      <option value="advisory">advisory</option>
                      <option value="gate">gate</option>
                    </select>
                  </div>

                  <div className="neo-card p-3">
                    <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Type</div>
                    <select
                      value={draft.review_type}
                      onChange={(e) => setDraft({ ...draft, review_type: e.target.value })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="none">none</option>
                      <option value="command">command</option>
                      <option value="claude">claude</option>
                      <option value="multi_cli">multi_cli</option>
                    </select>
                  </div>

                  <Field label="Timeout (s)" value={draft.review_timeout_s} onChange={(v) => setDraft({ ...draft, review_timeout_s: clampInt(v, 0, 3600) })} />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <TextField label="Review command" value={draft.review_command} onChange={(v) => setDraft({ ...draft, review_command: v })} placeholder="e.g. npm test && npm run lint" />
                  <TextField label="Review model" value={draft.review_model} onChange={(v) => setDraft({ ...draft, review_model: v })} placeholder="e.g. sonnet" />
                  <TextField label="Review agents (csv)" value={draft.review_agents} onChange={(v) => setDraft({ ...draft, review_agents: v })} placeholder="e.g. codex,gemini" />
                  <TextField label="Consensus" value={draft.review_consensus} onChange={(v) => setDraft({ ...draft, review_consensus: v })} placeholder="any|majority|all" />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
                  <TextField label="Codex model" value={draft.codex_model} onChange={(v) => setDraft({ ...draft, codex_model: v })} placeholder="e.g. gpt-5.2" />
                  <TextField label="Codex reasoning" value={draft.codex_reasoning_effort} onChange={(v) => setDraft({ ...draft, codex_reasoning_effort: v })} placeholder="low|medium|high" />
                  <TextField label="Gemini model" value={draft.gemini_model} onChange={(v) => setDraft({ ...draft, gemini_model: v })} placeholder="e.g. gemini-3-pro-preview" />
                </div>

                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Tip: set mode to <span className="font-mono">gate</span> to block merges when review fails.
                </div>
              </div>

              <div className="neo-card p-4">
                <div className="font-display font-bold uppercase mb-3">Locks + Verification</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Enable file locks</span>
                    <input type="checkbox" checked={draft.locks_enabled} onChange={(e) => setDraft({ ...draft, locks_enabled: e.target.checked })} className="w-5 h-5" />
                  </label>
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Worker verify (Gatekeeper)</span>
                    <input type="checkbox" checked={draft.worker_verify} onChange={(e) => setDraft({ ...draft, worker_verify: e.target.checked })} className="w-5 h-5" />
                  </label>
                </div>
              </div>

              <div className="neo-card p-4">
                <div className="font-display font-bold uppercase mb-3">QA + Controller</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">QA auto-fix</span>
                    <input type="checkbox" checked={draft.qa_fix_enabled} onChange={(e) => setDraft({ ...draft, qa_fix_enabled: e.target.checked })} className="w-5 h-5" />
                  </label>
                  <Field label="QA max sessions" value={draft.qa_max_sessions} onChange={(v) => setDraft({ ...draft, qa_max_sessions: clampInt(v, 0, 50) })} />
                  <TextField label="QA model" value={draft.qa_model} onChange={(v) => setDraft({ ...draft, qa_model: v })} placeholder="e.g. sonnet" />

                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Controller</span>
                    <input type="checkbox" checked={draft.controller_enabled} onChange={(e) => setDraft({ ...draft, controller_enabled: e.target.checked })} className="w-5 h-5" />
                  </label>
                  <Field label="Controller max sessions" value={draft.controller_max_sessions} onChange={(v) => setDraft({ ...draft, controller_max_sessions: clampInt(v, 0, 50) })} />
                  <TextField label="Controller model" value={draft.controller_model} onChange={(v) => setDraft({ ...draft, controller_model: v })} placeholder="e.g. haiku" />
                </div>
              </div>
            </div>
          )}

          {tab === 'gatekeeper' && (
            <div className="neo-card p-4">
              <div className="font-display font-bold uppercase mb-3">Gatekeeper</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Require Gatekeeper</span>
                  <input
                    type="checkbox"
                    checked={draft.require_gatekeeper}
                    onChange={(e) => setDraft({ ...draft, require_gatekeeper: e.target.checked })}
                    className="w-5 h-5"
                  />
                </label>
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Allow No Tests</span>
                  <input
                    type="checkbox"
                    checked={draft.allow_no_tests}
                    onChange={(e) => setDraft({ ...draft, allow_no_tests: e.target.checked })}
                    className="w-5 h-5"
                  />
                </label>
              </div>
            </div>
          )}

          {tab === 'logs' && (
            <div className="neo-card p-4">
              <div className="font-display font-bold uppercase mb-3">Log Retention</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Field label="Keep days" value={draft.logs_keep_days} onChange={(v) => setDraft({ ...draft, logs_keep_days: clampInt(v, 0, 3650) })} />
                <Field label="Keep files" value={draft.logs_keep_files} onChange={(v) => setDraft({ ...draft, logs_keep_files: clampInt(v, 0, 100000) })} />
                <Field label="Max total (MB)" value={draft.logs_max_total_mb} onChange={(v) => setDraft({ ...draft, logs_max_total_mb: clampInt(v, 0, 100000) })} />
              </div>
            </div>
          )}

          {tab === 'retry' && (
            <div className="neo-card p-4">
              <div className="font-display font-bold uppercase mb-3">SDK Retry/Backoff</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Field label="Max attempts" value={draft.sdk_max_attempts} onChange={(v) => setDraft({ ...draft, sdk_max_attempts: clampInt(v, 1, 20) })} />
                <Field label="Initial delay (s)" value={draft.sdk_initial_delay_s} onChange={(v) => setDraft({ ...draft, sdk_initial_delay_s: clampInt(v, 0, 600) })} />
                <Field label="Rate limit delay (s)" value={draft.sdk_rate_limit_initial_delay_s} onChange={(v) => setDraft({ ...draft, sdk_rate_limit_initial_delay_s: clampInt(v, 0, 3600) })} />
                <Field label="Max delay (s)" value={draft.sdk_max_delay_s} onChange={(v) => setDraft({ ...draft, sdk_max_delay_s: clampInt(v, 0, 3600) })} />
                <Field label="Exponential base" value={draft.sdk_exponential_base} onChange={(v) => setDraft({ ...draft, sdk_exponential_base: clampInt(v, 1, 10) })} />
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Jitter</span>
                  <input type="checkbox" checked={draft.sdk_jitter} onChange={(e) => setDraft({ ...draft, sdk_jitter: e.target.checked })} className="w-5 h-5" />
                </label>
              </div>
            </div>
          )}

          {tab === 'ports' && (
            <div className="neo-card p-4">
              <div className="font-display font-bold uppercase mb-3">Port Pools</div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <Field label="API start" value={draft.api_port_range_start} onChange={(v) => setDraft({ ...draft, api_port_range_start: clampInt(v, 1024, 65535) })} />
                <Field label="API end" value={draft.api_port_range_end} onChange={(v) => setDraft({ ...draft, api_port_range_end: clampInt(v, 1024, 65536) })} />
                <Field label="WEB start" value={draft.web_port_range_start} onChange={(v) => setDraft({ ...draft, web_port_range_start: clampInt(v, 1024, 65535) })} />
                <Field label="WEB end" value={draft.web_port_range_end} onChange={(v) => setDraft({ ...draft, web_port_range_end: clampInt(v, 1024, 65536) })} />
              </div>

              <div className="mt-3">
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Skip port availability check</span>
                  <input type="checkbox" checked={draft.skip_port_check} onChange={(e) => setDraft({ ...draft, skip_port_check: e.target.checked })} className="w-5 h-5" />
                </label>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Field({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full"
      />
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div>
      <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full"
      />
    </div>
  )
}

