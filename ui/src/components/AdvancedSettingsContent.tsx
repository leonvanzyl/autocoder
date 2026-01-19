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
  worker_provider: 'claude',
  worker_patch_max_iterations: 2,
  worker_patch_agents: 'codex,gemini',
  qa_fix_enabled: false,
  qa_model: '',
  qa_max_sessions: 0,
  qa_subagent_enabled: false,
  qa_subagent_max_iterations: 2,
  qa_subagent_provider: 'claude',
  qa_subagent_agents: 'codex,gemini',
  controller_enabled: false,
  controller_model: '',
  controller_max_sessions: 0,
  planner_enabled: false,
  planner_model: '',
  planner_agents: 'codex,gemini',
  planner_synthesizer: 'claude',
  planner_timeout_s: 180,
  initializer_provider: 'claude',
  initializer_agents: 'codex,gemini',
  initializer_synthesizer: 'claude',
  initializer_timeout_s: 300,
  initializer_stage_threshold: 120,
  initializer_enqueue_count: 30,
  logs_keep_days: 7,
  logs_keep_files: 200,
  logs_max_total_mb: 200,
  logs_prune_artifacts: false,
  diagnostics_fixtures_dir: '',
  ui_host: '',
  ui_allow_remote: false,
  agent_color_running: '#00b4d8',
  agent_color_done: '#70e000',
  agent_color_retry: '#f59e0b',
  sdk_max_attempts: 3,
  sdk_initial_delay_s: 1,
  sdk_rate_limit_initial_delay_s: 30,
  sdk_max_delay_s: 60,
  sdk_exponential_base: 2,
  sdk_jitter: true,
  require_gatekeeper: true,
  allow_no_tests: false,
  stop_when_done: true,
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
  const [tab, setTab] = useState<'automation' | 'gatekeeper' | 'logs' | 'retry' | 'ports' | 'ui'>('automation')

  useEffect(() => {
    if (data) setDraft(data)
  }, [data])

  const validation = useMemo(() => {
    type FieldName = keyof AdvancedSettings
    const fieldErrors: Partial<Record<FieldName, string>> = {}
    const fieldWarnings: Partial<Record<FieldName, string>> = {}
    const errors: string[] = []
    const warnings: string[] = []

    const addError = (field: FieldName, message: string) => {
      errors.push(message)
      fieldErrors[field] = message
    }
    const addWarning = (field: FieldName, message: string) => {
      warnings.push(message)
      fieldWarnings[field] = message
    }

    const isHexColor = (value: string) => /^#[0-9a-fA-F]{6}$/.test(value.trim())

    if (draft.api_port_range_end <= draft.api_port_range_start) addError('api_port_range_end', 'API port range end must be > start')
    if (draft.web_port_range_end <= draft.web_port_range_start) addError('web_port_range_end', 'WEB port range end must be > start')

    if (draft.review_enabled) {
      if (draft.review_mode === 'off') addError('review_mode', 'Set review mode to advisory or gate')
      if (draft.review_type === 'none') addError('review_type', 'Select a review type')
      if (draft.review_type === 'command' && !draft.review_command.trim()) addError('review_command', 'Review command is required for command review')
      if (draft.review_type === 'multi_cli' && !draft.review_agents.trim()) addError('review_agents', 'Review agents are required for multi_cli review')
      if (draft.review_consensus.trim() && !['any', 'majority', 'all'].includes(draft.review_consensus.trim()))
        addError('review_consensus', 'Consensus must be any, majority, or all')
    } else {
      if (draft.review_mode !== 'off') addWarning('review_mode', 'Review is disabled; mode is ignored')
      if (draft.review_type !== 'none') addWarning('review_type', 'Review is disabled; type is ignored')
    }

    if (draft.codex_reasoning_effort.trim() && !['low', 'medium', 'high'].includes(draft.codex_reasoning_effort.trim()))
      addError('codex_reasoning_effort', 'Codex reasoning must be low, medium, or high')

    if (draft.worker_provider === 'multi_cli' && !draft.worker_patch_agents.trim())
      addError('worker_patch_agents', 'Patch provider order is required for multi_cli')

    if (draft.qa_subagent_enabled && draft.qa_subagent_provider === 'multi_cli' && !draft.qa_subagent_agents.trim())
      addError('qa_subagent_agents', 'QA provider order is required for multi_cli')

    if (draft.planner_enabled && !draft.planner_agents.trim()) addError('planner_agents', 'Planner agents are required when planner is enabled')

    if (draft.initializer_provider === 'multi_cli' && !draft.initializer_agents.trim())
      addError('initializer_agents', 'Initializer agents are required when provider is multi_cli')

    if (draft.initializer_stage_threshold > 0 && draft.initializer_enqueue_count === 0)
      addWarning('initializer_enqueue_count', 'Stage threshold is set but enqueue count is 0 (backlog will never start)')

    if (draft.allow_no_tests) addWarning('allow_no_tests', 'Allow No Tests can merge without verification (recommended only for YOLO)')
    if (draft.ui_allow_remote && !draft.ui_host.trim())
      addWarning('ui_host', 'Set UI bind host (e.g. 0.0.0.0) to allow LAN access')

    if (!isHexColor(draft.agent_color_running)) addError('agent_color_running', 'Running color must be a 6-digit hex (e.g. #00b4d8)')
    if (!isHexColor(draft.agent_color_done)) addError('agent_color_done', 'Done color must be a 6-digit hex (e.g. #70e000)')
    if (!isHexColor(draft.agent_color_retry)) addError('agent_color_retry', 'Retry color must be a 6-digit hex (e.g. #f59e0b)')

    return { errors, warnings, fieldErrors, fieldWarnings }
  }, [draft])

  const saveDisabled = isLoading || update.isPending || validation.errors.length > 0

  const onSave = async () => {
    if (validation.errors.length > 0) return
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
          <button
            className={`neo-btn text-sm ${tab === 'ui' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('ui')}
          >
            UI
          </button>
        </div>
      </div>

      {validation.errors.length > 0 && (
        <div className="neo-card p-4 bg-[var(--color-neo-danger)]/10 border-[var(--color-neo-danger)]">
          <div className="font-display font-bold text-[var(--color-neo-danger)]">Fix before saving</div>
          <ul className="text-sm list-disc pl-5 mt-1">
            {validation.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}
      {validation.errors.length === 0 && validation.warnings.length > 0 && (
        <div className="neo-card p-4 bg-yellow-500/10 border-yellow-600">
          <div className="font-display font-bold text-yellow-800">Warnings</div>
          <ul className="text-sm list-disc pl-5 mt-1">
            {validation.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
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
                      onChange={(e) => setDraft({ ...draft, review_mode: e.target.value as AdvancedSettings['review_mode'] })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="off">off</option>
                      <option value="advisory">advisory</option>
                      <option value="gate">gate</option>
                    </select>
                    {validation.fieldErrors.review_mode && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{validation.fieldErrors.review_mode}</div>}
                    {!validation.fieldErrors.review_mode && validation.fieldWarnings.review_mode && (
                      <div className="text-xs mt-1 text-yellow-800">{validation.fieldWarnings.review_mode}</div>
                    )}
                  </div>

                  <div className="neo-card p-3">
                    <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Type</div>
                    <select
                      value={draft.review_type}
                      onChange={(e) => setDraft({ ...draft, review_type: e.target.value as AdvancedSettings['review_type'] })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="none">none</option>
                      <option value="command">command</option>
                      <option value="claude">claude</option>
                      <option value="multi_cli">multi_cli</option>
                    </select>
                    {validation.fieldErrors.review_type && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{validation.fieldErrors.review_type}</div>}
                    {!validation.fieldErrors.review_type && validation.fieldWarnings.review_type && (
                      <div className="text-xs mt-1 text-yellow-800">{validation.fieldWarnings.review_type}</div>
                    )}
                  </div>

                  <Field label="Timeout (s)" value={draft.review_timeout_s} onChange={(v) => setDraft({ ...draft, review_timeout_s: clampInt(v, 0, 3600) })} />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <TextField
                    label="Review command"
                    value={draft.review_command}
                    onChange={(v) => setDraft({ ...draft, review_command: v })}
                    placeholder="e.g. npm test && npm run lint"
                    error={validation.fieldErrors.review_command}
                  />
                  <TextField label="Review model" value={draft.review_model} onChange={(v) => setDraft({ ...draft, review_model: v })} placeholder="e.g. sonnet" />
                  <TextField
                    label="Review agents (csv)"
                    value={draft.review_agents}
                    onChange={(v) => setDraft({ ...draft, review_agents: v })}
                    placeholder="e.g. codex,gemini"
                    error={validation.fieldErrors.review_agents}
                  />
                  <TextField
                    label="Consensus"
                    value={draft.review_consensus}
                    onChange={(v) => setDraft({ ...draft, review_consensus: v })}
                    placeholder="any|majority|all"
                    error={validation.fieldErrors.review_consensus}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
                  <TextField label="Codex model" value={draft.codex_model} onChange={(v) => setDraft({ ...draft, codex_model: v })} placeholder="e.g. gpt-5.2" />
                  <TextField
                    label="Codex reasoning"
                    value={draft.codex_reasoning_effort}
                    onChange={(v) => setDraft({ ...draft, codex_reasoning_effort: v })}
                    placeholder="low|medium|high"
                    error={validation.fieldErrors.codex_reasoning_effort}
                  />
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
                <div className="font-display font-bold uppercase mb-3">Run Behavior</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Stop when queue is empty</span>
                    <input
                      type="checkbox"
                      checked={draft.stop_when_done}
                      onChange={(e) => setDraft({ ...draft, stop_when_done: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </label>
                  <div className="text-xs text-[var(--color-neo-text-secondary)] self-center">
                    If disabled, agents stay alive and wait for new features.
                  </div>
                </div>
              </div>

              <div className="neo-card p-4">
                <div className="font-display font-bold uppercase mb-3">Feature Workers</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-2">Worker provider</div>
                    <select
                      value={draft.worker_provider}
                      onChange={(e) => setDraft({ ...draft, worker_provider: e.target.value as AdvancedSettings['worker_provider'] })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="claude">claude (Claude Agent SDK)</option>
                      <option value="codex_cli">codex_cli (patch worker)</option>
                      <option value="gemini_cli">gemini_cli (patch worker)</option>
                      <option value="multi_cli">multi_cli (patch worker)</option>
                    </select>
                    <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                      Patch workers implement features by generating unified diffs, then Gatekeeper verifies deterministically.
                    </div>
                  </div>

                  <Field
                    label="Patch iterations"
                    value={draft.worker_patch_max_iterations}
                    onChange={(v) => setDraft({ ...draft, worker_patch_max_iterations: clampInt(v, 1, 20) })}
                  />

                  <TextField
                    label="Patch provider order (csv)"
                    value={draft.worker_patch_agents}
                    onChange={(v) => setDraft({ ...draft, worker_patch_agents: v })}
                    placeholder="e.g. codex,gemini"
                    error={validation.fieldErrors.worker_patch_agents}
                  />
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  <span className="block">
                    Note: <span className="font-mono">multi_cli</span> uses the order above. Single providers ignore it.
                  </span>
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
                    <span className="font-display font-bold text-sm">QA sub-agent</span>
                    <input
                      type="checkbox"
                      checked={draft.qa_subagent_enabled}
                      onChange={(e) => setDraft({ ...draft, qa_subagent_enabled: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </label>
                  <Field
                    label="QA max iterations"
                    value={draft.qa_subagent_max_iterations}
                    onChange={(v) => setDraft({ ...draft, qa_subagent_max_iterations: clampInt(v, 1, 20) })}
                  />
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-2">QA provider</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <select
                          value={draft.qa_subagent_provider}
                          onChange={(e) => setDraft({ ...draft, qa_subagent_provider: e.target.value as AdvancedSettings['qa_subagent_provider'] })}
                          className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                        >
                          <option value="claude">claude</option>
                          <option value="codex_cli">codex_cli</option>
                          <option value="gemini_cli">gemini_cli</option>
                          <option value="multi_cli">multi_cli</option>
                        </select>
                      </div>
                      <TextField
                        label="Order (csv)"
                        value={draft.qa_subagent_agents}
                        onChange={(v) => setDraft({ ...draft, qa_subagent_agents: v })}
                        placeholder="e.g. codex,gemini"
                        error={validation.fieldErrors.qa_subagent_agents}
                      />
                    </div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                      Spawns a short-lived fixer after Gatekeeper rejects a feature (reuses the same branch; no new scope).
                      <span className="block mt-1">
                        Note: <span className="font-mono">codex_cli</span> uses <span className="font-mono">Codex model</span> above, and <span className="font-mono">gemini_cli</span> uses <span className="font-mono">Gemini model</span>.
                      </span>
                    </div>
                  </div>

                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Controller</span>
                    <input type="checkbox" checked={draft.controller_enabled} onChange={(e) => setDraft({ ...draft, controller_enabled: e.target.checked })} className="w-5 h-5" />
                  </label>
                  <Field label="Controller max sessions" value={draft.controller_max_sessions} onChange={(v) => setDraft({ ...draft, controller_max_sessions: clampInt(v, 0, 50) })} />
                  <TextField label="Controller model" value={draft.controller_model} onChange={(v) => setDraft({ ...draft, controller_model: v })} placeholder="e.g. haiku" />
                </div>
              </div>

              <div className="neo-card p-4">
                <div className="font-display font-bold uppercase mb-3">Planner</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Feature plan (multi-model)</span>
                    <input
                      type="checkbox"
                      checked={draft.planner_enabled}
                      onChange={(e) => setDraft({ ...draft, planner_enabled: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </label>
                  <Field
                    label="Timeout (s)"
                    value={draft.planner_timeout_s}
                    onChange={(v) => setDraft({ ...draft, planner_timeout_s: clampInt(v, 30, 3600) })}
                  />
                  <TextField
                    label="Agents (csv)"
                    value={draft.planner_agents}
                    onChange={(v) => setDraft({ ...draft, planner_agents: v })}
                    placeholder="e.g. codex,gemini"
                    error={validation.fieldErrors.planner_agents}
                  />
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-2">Synthesizer</div>
                    <select
                      value={draft.planner_synthesizer}
                      onChange={(e) => setDraft({ ...draft, planner_synthesizer: e.target.value as AdvancedSettings['planner_synthesizer'] })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="claude">claude</option>
                      <option value="none">none</option>
                      <option value="codex">codex</option>
                      <option value="gemini">gemini</option>
                    </select>
                  </div>
                  <TextField
                    label="Claude model (optional)"
                    value={draft.planner_model}
                    onChange={(v) => setDraft({ ...draft, planner_model: v })}
                    placeholder="e.g. sonnet"
                  />
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Generates a short implementation plan per feature and prepends it to the worker prompt. Uses Codex/Gemini CLIs
                  when available, with optional Claude synthesis.
                </div>
              </div>

              <div className="neo-card p-4">
                <div className="font-display font-bold uppercase mb-3">Initializer</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="neo-card p-3">
                    <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Provider</div>
                    <select
                      value={draft.initializer_provider}
                      onChange={(e) => setDraft({ ...draft, initializer_provider: e.target.value as AdvancedSettings['initializer_provider'] })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="claude">claude (Claude Agent SDK)</option>
                      <option value="codex_cli">codex_cli</option>
                      <option value="gemini_cli">gemini_cli</option>
                      <option value="multi_cli">multi_cli</option>
                    </select>
                  </div>
                  <TextField
                    label="Agents (csv)"
                    value={draft.initializer_agents}
                    onChange={(v) => setDraft({ ...draft, initializer_agents: v })}
                    placeholder="e.g. codex,gemini"
                    error={validation.fieldErrors.initializer_agents}
                  />
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-2">Synthesizer</div>
                    <select
                      value={draft.initializer_synthesizer}
                      onChange={(e) => setDraft({ ...draft, initializer_synthesizer: e.target.value as AdvancedSettings['initializer_synthesizer'] })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="claude">claude</option>
                      <option value="none">none</option>
                      <option value="codex">codex</option>
                      <option value="gemini">gemini</option>
                    </select>
                  </div>
                  <Field
                    label="Timeout (s)"
                    value={draft.initializer_timeout_s}
                    onChange={(v) => setDraft({ ...draft, initializer_timeout_s: clampInt(v, 30, 3600) })}
                  />
                  <Field
                    label="Stage threshold"
                    value={draft.initializer_stage_threshold}
                    onChange={(v) => setDraft({ ...draft, initializer_stage_threshold: clampInt(v, 0, 100000) })}
                  />
                  <Field
                    label="Enqueue count"
                    value={draft.initializer_enqueue_count}
                    onChange={(v) => setDraft({ ...draft, initializer_enqueue_count: clampInt(v, 0, 100000) })}
                  />
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Controls the initial feature backlog generation. Large backlogs get staged and only the top
                  <span className="font-mono"> enqueue_count</span> are enabled.
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
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Auto-prune Gatekeeper artifacts</span>
                  <input
                    type="checkbox"
                    checked={draft.logs_prune_artifacts}
                    onChange={(e) => setDraft({ ...draft, logs_prune_artifacts: e.target.checked })}
                    className="w-5 h-5"
                  />
                </label>
                <div className="text-xs text-[var(--color-neo-text-secondary)] self-center">
                  Prunes <span className="font-mono">.autocoder/**/gatekeeper/*.json</span> periodically during runs.
                </div>
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
                <Field
                  label="API end"
                  value={draft.api_port_range_end}
                  onChange={(v) => setDraft({ ...draft, api_port_range_end: clampInt(v, 1024, 65536) })}
                  error={validation.fieldErrors.api_port_range_end}
                />
                <Field label="WEB start" value={draft.web_port_range_start} onChange={(v) => setDraft({ ...draft, web_port_range_start: clampInt(v, 1024, 65535) })} />
                <Field
                  label="WEB end"
                  value={draft.web_port_range_end}
                  onChange={(v) => setDraft({ ...draft, web_port_range_end: clampInt(v, 1024, 65536) })}
                  error={validation.fieldErrors.web_port_range_end}
                />
              </div>

              <div className="mt-3">
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Skip port availability check</span>
                  <input type="checkbox" checked={draft.skip_port_check} onChange={(e) => setDraft({ ...draft, skip_port_check: e.target.checked })} className="w-5 h-5" />
                </label>
              </div>

              <div className="neo-card p-4 mt-4">
                <div className="font-display font-bold uppercase mb-3">UI Server</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <TextField
                    label="Bind host"
                    value={draft.ui_host}
                    onChange={(v) => setDraft({ ...draft, ui_host: v })}
                    placeholder="127.0.0.1 (default)"
                  />
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Allow LAN access</span>
                    <input
                      type="checkbox"
                      checked={draft.ui_allow_remote}
                      onChange={(e) => setDraft({ ...draft, ui_allow_remote: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </label>
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Requires a UI restart. Use <span className="font-mono">0.0.0.0</span> to bind all interfaces.
                </div>
              </div>
            </div>
          )}

          {tab === 'ui' && (
            <div className="neo-card p-4">
              <div className="font-display font-bold uppercase mb-3">Agent Status Colors</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <ColorField
                  label="Running"
                  value={draft.agent_color_running}
                  onChange={(v) => setDraft({ ...draft, agent_color_running: v })}
                  error={validation.fieldErrors.agent_color_running}
                />
                <ColorField
                  label="Done"
                  value={draft.agent_color_done}
                  onChange={(v) => setDraft({ ...draft, agent_color_done: v })}
                  error={validation.fieldErrors.agent_color_done}
                />
                <ColorField
                  label="Retrying"
                  value={draft.agent_color_retry}
                  onChange={(v) => setDraft({ ...draft, agent_color_retry: v })}
                  error={validation.fieldErrors.agent_color_retry}
                />
              </div>
              <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                These update the Agent Status cards and summary colors. Use hex values (e.g. <span className="font-mono">#00b4d8</span>).
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  error,
  warning,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  error?: string
  warning?: string
}) {
  const border =
    error ? 'border-[var(--color-neo-danger)]' : warning ? 'border-yellow-600' : 'border-[var(--color-neo-border)]'
  return (
    <div>
      <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className={`neo-btn text-sm py-2 px-3 bg-white border-3 ${border} font-mono w-full`}
      />
      {error && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{error}</div>}
      {!error && warning && <div className="text-xs mt-1 text-yellow-800">{warning}</div>}
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  error,
  warning,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  error?: string
  warning?: string
}) {
  const border =
    error ? 'border-[var(--color-neo-danger)]' : warning ? 'border-yellow-600' : 'border-[var(--color-neo-border)]'
  return (
    <div>
      <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={`neo-btn text-sm py-2 px-3 bg-white border-3 ${border} font-mono w-full`}
      />
      {error && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{error}</div>}
      {!error && warning && <div className="text-xs mt-1 text-yellow-800">{warning}</div>}
    </div>
  )
}

function ColorField({
  label,
  value,
  onChange,
  error,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  error?: string
}) {
  const border = error ? 'border-[var(--color-neo-danger)]' : 'border-[var(--color-neo-border)]'
  return (
    <div>
      <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`h-10 w-12 border-2 ${border} bg-white`}
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`neo-btn text-sm py-2 px-3 bg-white border-3 ${border} font-mono w-full`}
        />
      </div>
      {error && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{error}</div>}
    </div>
  )
}

