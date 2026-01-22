/**
 * Advanced Settings Content
 * =========================
 *
 * Server-backed settings that affect subprocess env vars when starting agents/orchestrator from the UI.
 * Intended to be embedded in a page (not a modal).
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, Info, RotateCcw, Save, SlidersHorizontal } from 'lucide-react'
import { useAdvancedSettings, useUpdateAdvancedSettings } from '../hooks/useAdvancedSettings'
import { useSetupStatus } from '../hooks/useProjects'
import type { AdvancedSettings } from '../lib/types'
import { ConfirmationDialog } from './ConfirmationDialog'
import { InlineNotice, type InlineNoticeType } from './InlineNotice'
import { HelpModal } from './HelpModal'

function clampInt(v: number, min: number, max: number): number {
  if (!Number.isFinite(v)) return min
  return Math.max(min, Math.min(max, Math.trunc(v)))
}

const DEFAULTS: AdvancedSettings = {
  review_enabled: false,
  review_mode: 'off',
  review_timeout_s: 0,
  review_model: '',
  review_consensus: '',
  codex_model: '',
  codex_reasoning_effort: '',
  gemini_model: '',
  locks_enabled: true,
  worker_verify: true,
  qa_fix_enabled: false,
  qa_model: '',
  qa_max_sessions: 0,
  qa_subagent_enabled: true,
  qa_subagent_max_iterations: 2,
  controller_enabled: false,
  controller_model: '',
  controller_max_sessions: 0,
  regression_pool_enabled: false,
  regression_pool_max_agents: 1,
  regression_pool_model: '',
  regression_pool_min_interval_s: 600,
  regression_pool_max_iterations: 1,
  planner_enabled: false,
  planner_model: '',
  planner_synthesizer: 'claude',
  planner_timeout_s: 180,
  initializer_synthesizer: 'claude',
  initializer_timeout_s: 300,
  initializer_stage_threshold: 120,
  initializer_enqueue_count: 30,
  logs_keep_days: 7,
  logs_keep_files: 200,
  logs_max_total_mb: 200,
  logs_prune_artifacts: false,
  activity_keep_days: 14,
  activity_keep_rows: 5000,
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

type HelpTopic =
  | 'overview'
  | 'review'
  | 'locks'
  | 'gatekeeper'
  | 'cli_defaults'
  | 'logs'
  | 'retry'
  | 'ports'
  | 'ui'
  | 'qa_controller'
  | 'regression_pool'
  | 'planner'
  | 'initializer'

const HELP_CONTENT: Record<HelpTopic, { title: string; body: JSX.Element }> = {
  overview: {
    title: 'Advanced Settings — How this actually works',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          These settings are <span className="font-bold">global</span> (this machine) and only affect runs started from
          the Web UI. When you hit <span className="font-mono">Save</span>, the server persists them and applies them as
          env vars when spawning agents/orchestrator.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Good mental model</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <span className="font-bold">Project config</span> lives in the target repo (<span className="font-mono">autocoder.yaml</span>).
            </li>
            <li>
              <span className="font-bold">Advanced settings</span> live on your machine (<span className="font-mono">~/.autocoder/settings.db</span>).
            </li>
            <li>
              <span className="font-bold">Nothing changes</span> until you click Save.
            </li>
          </ul>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          If you’re new: keep <span className="font-bold">Gatekeeper</span>, <span className="font-bold">Worker verify</span>, and{' '}
          <span className="font-bold">File locks</span> enabled. Those three prevent 90% of “why is this cursed?” moments.
        </p>
      </div>
    ),
  },
  review: {
    title: 'Review (optional) — what it does',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          Review runs inside <span className="font-bold">Gatekeeper</span> after tests pass, right before merging. It
          reviews the <span className="font-bold">staged diff</span> in the temporary worktree.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Modes</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <span className="font-bold">Advisory</span>: records findings in the Gatekeeper artifact, but does not block the merge.
            </li>
            <li>
              <span className="font-bold">Gate</span>: blocks the merge if review is not approved (unless the reviewer explicitly skips).
            </li>
          </ul>
        </div>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Engines</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              Choose the engine chain in the <span className="font-bold">Engines</span> tab (Claude review + Codex/Gemini CLIs).
            </li>
            <li>
              Missing CLIs are skipped automatically. Claude review skips when credentials are missing.
            </li>
          </ul>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          Review is not a substitute for tests. Think of it as “linting + sanity check + second set of eyes.”
        </p>
      </div>
    ),
  },
  locks: {
    title: 'File locks + Worker verify (recommended)',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          These are your “don’t melt the repo” safety rails when you run multiple agents/sub‑agents.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">File locks</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Enforces a per‑file write lock for the agent’s file‑write tools. First writer auto‑acquires the lock; other agents must pick different files.
          </p>
        </div>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Worker verify</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Forces workers to submit for Gatekeeper verification instead of self‑attesting “passing”. Gatekeeper runs deterministic commands and merges safely.
          </p>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          Separate thing: AutoCoder also uses a per‑project run lock (<span className="font-mono">.agent.lock</span>) so two orchestrators don’t run in the same project.
        </p>
      </div>
    ),
  },
  gatekeeper: {
    title: 'Gatekeeper — deterministic merge gate (and when to ignore it)',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          Gatekeeper is the only thing allowed to merge to main. It verifies in a clean temporary worktree, then fast‑forwards main to the verified merge commit.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Require Gatekeeper</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Recommended. Disabling it removes the deterministic merge gate and can merge broken code (especially in parallel).
          </p>
        </div>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Allow No Tests</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Lets Gatekeeper proceed when no deterministic test command exists. This is basically “YOLO mode for merges” — use only when you accept that risk.
          </p>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          Tip: if a project doesn’t have a <span className="font-mono">test</span> script, configure commands in <span className="font-mono">autocoder.yaml</span> instead of disabling Gatekeeper.
        </p>
      </div>
    ),
  },
  cli_defaults: {
    title: 'Codex/Gemini defaults — models + reasoning',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          These are the default knobs used by <span className="font-bold">Codex CLI</span> and <span className="font-bold">Gemini CLI</span> steps across AutoCoder (review, planner drafts, patch workers, etc.).
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Best practice</div>
          <ul className="list-disc pl-5 space-y-1 text-[var(--color-neo-text-secondary)]">
            <li>
              Leave model fields blank to use the CLI’s own defaults (AutoCoder also reads Codex defaults from <span className="font-mono">~/.codex/config.toml</span> when available).
            </li>
            <li>
              Only override when you need a specific model for cost/latency/quality.
            </li>
            <li>
              Reasoning effort is Codex-specific and accepts: <span className="font-mono">low|medium|high|xlow|xmedium|xhigh</span>.
            </li>
          </ul>
        </div>
      </div>
    ),
  },
  logs: {
    title: 'Logs + Activity — retention & auto-prune',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          AutoCoder writes runtime logs under each project’s <span className="font-mono">.autocoder/</span>. These knobs
          keep disk usage from creeping up over time.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">What gets pruned</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <span className="font-bold">Logs</span>: old files + total size cap.
            </li>
            <li>
              <span className="font-bold">Gatekeeper artifacts</span>: optional cleanup of historical{' '}
              <span className="font-mono">gatekeeper/*.json</span> files (useful on long runs).
            </li>
            <li>
              <span className="font-bold">Mission Control feed</span>: DB rows stored in{' '}
              <span className="font-mono">agent_system.db</span> (keeps UI snappy).
            </li>
          </ul>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          Tip: if you’re debugging a flaky project, temporarily disable auto-prune so artifacts stick around longer.
        </p>
      </div>
    ),
  },
  retry: {
    title: 'SDK Retry/Backoff — keep agents resilient',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          These settings control how AutoCoder retries transient failures (rate limits, network hiccups, flaky CLI calls)
          inside agent/sub-agent loops.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">How it behaves</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <span className="font-bold">Max attempts</span>: total tries before the run is marked failed.
            </li>
            <li>
              <span className="font-bold">Initial delay</span> + <span className="font-bold">exponential base</span>: backoff curve.
            </li>
            <li>
              <span className="font-bold">Rate limit delay</span>: a “bigger first wait” for 429s.
            </li>
            <li>
              <span className="font-bold">Jitter</span>: randomizes delays to avoid synchronized retries (recommended).
            </li>
          </ul>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          If you see tight retry loops, increase Max delay or enable jitter.
        </p>
      </div>
    ),
  },
  ports: {
    title: 'Ports — parallel agent isolation',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          Parallel agents often start dev servers (API + web). AutoCoder allocates unique port pairs per agent to avoid{' '}
          <span className="font-mono">EADDRINUSE</span> crashes.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Port pools</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <span className="font-bold">API pool</span>: backend/dev API ports.
            </li>
            <li>
              <span className="font-bold">WEB pool</span>: frontend/dev web ports.
            </li>
            <li>
              <span className="font-bold">Skip availability check</span>: only if your environment blocks port probing (not recommended).
            </li>
          </ul>
        </div>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">UI server</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Bind host controls where the UI listens. Keep it on <span className="font-mono">127.0.0.1</span> by default.
            Enable LAN only if you understand the risk and you’re on a trusted network.
          </p>
        </div>
      </div>
    ),
  },
  ui: {
    title: 'UI — Agent status colors',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          Cosmetic only. These colors are used by the Agent Status cards (running/done/retrying) so you can match your taste
          or improve contrast on your monitor.
        </p>
        <p className="text-[var(--color-neo-text-secondary)]">
          Use 6‑digit hex colors like <span className="font-mono">#00b4d8</span>.
        </p>
      </div>
    ),
  },
  qa_controller: {
    title: 'QA + Controller — fixing failures without human babysitting',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          These are optional helpers that kick in after a Gatekeeper rejection (or right before Gatekeeper runs).
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">QA auto‑fix</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Reuses the same worker session to focus on fixing the last failure (tests/lint/typecheck), capped by max sessions.
          </p>
        </div>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">QA sub‑agent</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Spawns a short‑lived fixer in the same feature branch. It only fixes the failure excerpt and resubmits — no new scope creep.
          </p>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          Recommended default: enable <span className="font-bold">QA sub‑agent</span> (low noise; runs only on failures). Keep Controller off unless you want stricter preflight.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Controller preflight</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Runs deterministic verification commands in the agent worktree before Gatekeeper merge verification. Fail‑fast, less churn.
          </p>
        </div>
      </div>
    ),
  },
  regression_pool: {
    title: 'Regression pool — keep “passing” features passing',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          When there are no claimable features, AutoCoder can spawn short‑lived regression testers (Claude + Playwright) to re‑verify previously passing features.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">What happens if it finds a bug?</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            It creates a new issue‑like <span className="font-mono">REGRESSION</span> feature linked to the original feature, so the normal queue can fix it.
          </p>
        </div>
        <p className="text-[var(--color-neo-text-secondary)]">
          This is opt‑in because it can cost tokens and can be noisy on unstable projects. Start with 1 tester and a longer min interval.
        </p>
      </div>
    ),
  },
  planner: {
    title: 'Planner — multi‑model plan artifacts (optional)',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          Planner generates a short plan per feature and prepends it to the worker prompt. Draft engines are configured in
          <span className="font-bold"> Settings → Engines</span>; an optional synthesizer can merge ideas.
        </p>
        <p className="text-[var(--color-neo-text-secondary)]">
          Use it when features are complex, specs are messy, or you want more predictable step‑by‑step execution.
        </p>
      </div>
    ),
  },
  initializer: {
    title: 'Initializer — generating the feature backlog',
    body: (
      <div className="space-y-4 text-sm">
        <p>
          Initializer turns your spec into a backlog. Draft engines are configured in
          <span className="font-bold"> Settings → Engines</span>, with an optional synthesizer here.
        </p>
        <div className="neo-card p-4 bg-[var(--color-neo-bg)] space-y-2">
          <div className="font-display font-bold uppercase text-xs">Staging</div>
          <p className="text-[var(--color-neo-text-secondary)]">
            Large backlogs can be staged to keep active queues manageable. The stage threshold controls when AutoCoder starts staging instead of enabling everything at once.
          </p>
        </div>
      </div>
    ),
  },
}

export function AdvancedSettingsContent() {
  const { data, isLoading } = useAdvancedSettings()
  const update = useUpdateAdvancedSettings()
  const { data: setupStatus } = useSetupStatus()

  const [draft, setDraft] = useState<AdvancedSettings>(DEFAULTS)
  const [tab, setTab] = useState<'automation' | 'gatekeeper' | 'logs' | 'retry' | 'ports' | 'ui'>('automation')
  const [helpTopic, setHelpTopic] = useState<HelpTopic | null>(null)
  const [justSaved, setJustSaved] = useState(false)
  const [notice, setNotice] = useState<{ type: InlineNoticeType; message: string } | null>(null)
  const noticeTimer = useRef<number | null>(null)
  const savedTimer = useRef<number | null>(null)
  const [confirmToggle, setConfirmToggle] = useState<{
    field: keyof AdvancedSettings
    next: boolean
    title: string
    message: string
    confirmText: string
    variant?: 'danger' | 'warning'
  } | null>(null)

  useEffect(() => {
    if (data) setDraft(data)
  }, [data])

  useEffect(() => {
    return () => {
      if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
      if (savedTimer.current) window.clearTimeout(savedTimer.current)
    }
  }, [])

  const requestDangerToggle = (
    field: keyof AdvancedSettings,
    next: boolean,
    cfg: { title: string; message: string; confirmText: string; variant?: 'danger' | 'warning' },
  ) => {
    const shouldConfirm =
      (field === 'allow_no_tests' && next === true) ||
      (field !== 'allow_no_tests' && next === false)

    if (!shouldConfirm) {
      setDraft({ ...draft, [field]: next } as AdvancedSettings)
      return
    }

    setConfirmToggle({ field, next, ...cfg })
  }

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
      if (draft.review_consensus.trim() && !['any', 'majority', 'all'].includes(draft.review_consensus.trim()))
        addError('review_consensus', 'Consensus must be any, majority, or all')
    } else {
      if (draft.review_mode !== 'off') addWarning('review_mode', 'Review is disabled; mode is ignored')
    }

    if (
      draft.codex_reasoning_effort.trim() &&
      !['low', 'medium', 'high', 'xlow', 'xmedium', 'xhigh'].includes(draft.codex_reasoning_effort.trim())
    )
      addError('codex_reasoning_effort', 'Codex reasoning must be low|medium|high|xlow|xmedium|xhigh (or blank)')

    if (draft.regression_pool_enabled && draft.regression_pool_max_agents <= 0)
      addError('regression_pool_max_agents', 'Regression pool max agents must be > 0 when enabled')

    if (draft.initializer_stage_threshold > 0 && draft.initializer_enqueue_count === 0)
      addWarning('initializer_enqueue_count', 'Stage threshold is set but enqueue count is 0 (backlog will never start)')

    if (draft.allow_no_tests) addWarning('allow_no_tests', 'Allow No Tests can merge without verification (recommended only for YOLO)')
    if (!draft.require_gatekeeper) addWarning('require_gatekeeper', 'Gatekeeper is disabled; merges may happen without deterministic verification')
    if (!draft.worker_verify) addWarning('worker_verify', 'Worker verify is disabled; workers can self-attest without Gatekeeper')
    if (!draft.locks_enabled) addWarning('locks_enabled', 'File locks are disabled; multiple runs can overlap in the same project')
    if (draft.ui_allow_remote && !draft.ui_host.trim())
      addWarning('ui_host', 'Set UI bind host (e.g. 0.0.0.0) to allow LAN access')

    if (!isHexColor(draft.agent_color_running)) addError('agent_color_running', 'Running color must be a 6-digit hex (e.g. #00b4d8)')
    if (!isHexColor(draft.agent_color_done)) addError('agent_color_done', 'Done color must be a 6-digit hex (e.g. #70e000)')
    if (!isHexColor(draft.agent_color_retry)) addError('agent_color_retry', 'Retry color must be a 6-digit hex (e.g. #f59e0b)')

    return { errors, warnings, fieldErrors, fieldWarnings }
  }, [draft])

  const labelReviewMode = (v: string) => (v === 'off' ? 'Off' : v === 'advisory' ? 'Advisory' : v === 'gate' ? 'Gate' : v)

  const showSetupWarning = Boolean(setupStatus && (!setupStatus.codex_cli || !setupStatus.gemini_cli))

  const saveDisabled = isLoading || update.isPending || validation.errors.length > 0

  const flash = (type: InlineNoticeType, message: string) => {
    setNotice({ type, message })
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(null), 2500)
  }

  const onSave = async () => {
    if (validation.errors.length > 0) return
    try {
      await update.mutateAsync(draft)
      flash('success', 'Advanced settings saved.')
      setJustSaved(true)
      if (savedTimer.current) window.clearTimeout(savedTimer.current)
      savedTimer.current = window.setTimeout(() => setJustSaved(false), 2000)
    } catch (e: any) {
      flash('error', String(e?.message || e))
    }
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
              onClick={() => setHelpTopic('overview')}
              title="What do these settings do?"
            >
              <Info size={18} />
              Help
            </button>
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
              {justSaved ? <CheckCircle2 size={18} /> : <Save size={18} />}
              {justSaved ? 'Saved' : 'Save'}
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

      {notice && (
        <InlineNotice type={notice.type} message={notice.message} onClose={() => setNotice(null)} />
      )}

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
              {showSetupWarning && (
                <div className="neo-card p-4 bg-yellow-500/10 border-yellow-600">
                  <div className="font-display font-bold text-yellow-900">Some CLIs are missing</div>
                  <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                    Codex/Gemini-powered features will be disabled or skipped until the CLI is installed and on your PATH.
                  </div>
                </div>
              )}
              <div className="neo-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className="font-display font-bold uppercase">Review</div>
                  <button
                    type="button"
                    className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                    onClick={() => setHelpTopic('review')}
                    title="What is Review?"
                    aria-label="Help: Review"
                  >
                    <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                  </button>
                </div>
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
                      <option value="off">{labelReviewMode('off')}</option>
                      <option value="advisory">{labelReviewMode('advisory')}</option>
                      <option value="gate">{labelReviewMode('gate')}</option>
                    </select>
                    {validation.fieldErrors.review_mode && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{validation.fieldErrors.review_mode}</div>}
                    {!validation.fieldErrors.review_mode && validation.fieldWarnings.review_mode && (
                      <div className="text-xs mt-1 text-yellow-800">{validation.fieldWarnings.review_mode}</div>
                    )}
                    <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                      {draft.review_mode === 'off'
                        ? 'Off: don’t run the reviewer.'
                        : draft.review_mode === 'advisory'
                          ? 'Advisory: run reviewer + store findings, but don’t block merge.'
                          : 'Gate: block merge if reviewer rejects.'}
                    </div>
                  </div>

                  <Field label="Timeout (s)" value={draft.review_timeout_s} onChange={(v) => setDraft({ ...draft, review_timeout_s: clampInt(v, 0, 3600) })} />
                  <SelectField
                    label="Claude review model (optional)"
                    value={(draft.review_model || '').trim().toLowerCase()}
                    onChange={(v) => setDraft({ ...draft, review_model: v })}
                    options={[
                      { value: '', label: 'Auto (sonnet)' },
                      { value: 'haiku', label: 'haiku' },
                      { value: 'sonnet', label: 'sonnet' },
                      { value: 'opus', label: 'opus' },
                    ]}
                  />
                  <SelectField
                    label="Consensus (when multiple reviewers run)"
                    value={(draft.review_consensus || '').trim().toLowerCase()}
                    onChange={(v) => setDraft({ ...draft, review_consensus: v })}
                    options={[
                      { value: '', label: 'Auto (majority)' },
                      { value: 'majority', label: 'majority' },
                      { value: 'any', label: 'any' },
                      { value: 'all', label: 'all' },
                    ]}
                    error={validation.fieldErrors.review_consensus}
                  />
                </div>

                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Review engines are configured in <span className="font-display font-semibold">Settings → Engines</span>.
                  Tip: set mode to <span className="font-mono">gate</span> to block merges when review fails.
                </div>
              </div>

              <div className="neo-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className="font-display font-bold uppercase">Codex / Gemini Defaults</div>
                  <button
                    type="button"
                    className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                    onClick={() => setHelpTopic('cli_defaults')}
                    title="What are these defaults?"
                    aria-label="Help: Codex/Gemini defaults"
                  >
                    <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <TextField
                    label="Codex CLI model (optional)"
                    value={draft.codex_model}
                    onChange={(v) => setDraft({ ...draft, codex_model: v })}
                    placeholder="Leave blank to use Codex defaults"
                    warning={validation.fieldWarnings.codex_model}
                    disabled={setupStatus ? !setupStatus.codex_cli : false}
                  />
                  <SelectField
                    label="Codex reasoning (optional)"
                    value={(draft.codex_reasoning_effort || '').trim().toLowerCase()}
                    onChange={(v) => setDraft({ ...draft, codex_reasoning_effort: v })}
                    options={[
                      { value: '', label: 'Auto (use Codex defaults)' },
                      { value: 'low', label: 'low' },
                      { value: 'medium', label: 'medium' },
                      { value: 'high', label: 'high' },
                      { value: 'xlow', label: 'xlow' },
                      { value: 'xmedium', label: 'xmedium' },
                      { value: 'xhigh', label: 'xhigh' },
                    ]}
                    error={validation.fieldErrors.codex_reasoning_effort}
                    disabled={setupStatus ? !setupStatus.codex_cli : false}
                  />
                  <TextField
                    label="Gemini CLI model (optional)"
                    value={draft.gemini_model}
                    onChange={(v) => setDraft({ ...draft, gemini_model: v })}
                    placeholder="Leave blank to use Gemini defaults"
                    warning={validation.fieldWarnings.gemini_model}
                    disabled={setupStatus ? !setupStatus.gemini_cli : false}
                  />
                </div>

                {setupStatus?.codex_cli &&
                  (!draft.codex_model.trim() || !draft.codex_reasoning_effort.trim()) &&
                  (setupStatus.codex_model_default || setupStatus.codex_reasoning_default) && (
                    <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                      Detected Codex defaults:{' '}
                      {setupStatus.codex_model_default ? (
                        <span className="font-mono">model={setupStatus.codex_model_default}</span>
                      ) : null}
                      {setupStatus.codex_reasoning_default ? (
                        <span className="font-mono ml-2">reasoning={setupStatus.codex_reasoning_default}</span>
                      ) : null}
                    </div>
                  )}
              </div>

              <div className="neo-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className="font-display font-bold uppercase">Locks + Verification</div>
                  <button
                    type="button"
                    className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                    onClick={() => setHelpTopic('locks')}
                    title="What are locks and worker verify?"
                    aria-label="Help: Locks + verification"
                  >
                    <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Enable file locks</span>
                    <input
                      type="checkbox"
                      checked={draft.locks_enabled}
                      onChange={(e) =>
                        requestDangerToggle('locks_enabled', e.target.checked, {
                          title: 'Disable file locks?',
                          message:
                            'File locks prevent two agents/sub-agents from writing the same files at the same time. Disabling can cause merge conflicts and “last writer wins” bugs.',
                          confirmText: 'Disable locks',
                          variant: 'warning',
                        })
                      }
                      className="w-5 h-5"
                    />
                  </label>
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Worker verify (Gatekeeper)</span>
                    <input
                      type="checkbox"
                      checked={draft.worker_verify}
                      onChange={(e) =>
                        requestDangerToggle('worker_verify', e.target.checked, {
                          title: 'Disable worker verify?',
                          message:
                            'With worker verify off, workers can self‑attest passing without Gatekeeper’s deterministic verification/merge. Great for debugging, risky for real runs.',
                          confirmText: 'Disable verify',
                          variant: 'warning',
                        })
                      }
                      className="w-5 h-5"
                    />
                  </label>
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  If you’re running parallel agents, keep both enabled unless you’re debugging something very specific.
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
                <div className="font-display font-bold uppercase mb-2">Engine Chains</div>
                <div className="text-sm text-[var(--color-neo-text-secondary)]">
                  Feature workers, QA fixers, review, and spec/initializer engines are configured in the
                  <span className="font-display font-semibold"> Engines</span> tab (project‑scoped).
                  Advanced Settings only controls the global safety toggles.
                </div>
              </div>

              <details
                className="neo-card p-4"
                open={draft.qa_fix_enabled || draft.qa_subagent_enabled || draft.controller_enabled}
              >
                <summary className="font-display font-bold uppercase cursor-pointer select-none">QA + Controller</summary>
                <div className="flex justify-end mt-2">
                  <button
                    type="button"
                    className="neo-btn neo-btn-secondary neo-btn-sm"
                    onClick={() => setHelpTopic('qa_controller')}
                    title="Explain QA + Controller"
                  >
                    <Info size={14} />
                    What’s this?
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">QA auto-fix</span>
                    <input type="checkbox" checked={draft.qa_fix_enabled} onChange={(e) => setDraft({ ...draft, qa_fix_enabled: e.target.checked })} className="w-5 h-5" />
                  </label>
                  <Field label="QA max sessions" value={draft.qa_max_sessions} onChange={(v) => setDraft({ ...draft, qa_max_sessions: clampInt(v, 0, 50) })} />
                  <SelectField
                    label="QA model (optional)"
                    value={(draft.qa_model || '').trim().toLowerCase()}
                    onChange={(v) => setDraft({ ...draft, qa_model: v })}
                    options={[
                      { value: '', label: 'Auto' },
                      { value: 'haiku', label: 'haiku' },
                      { value: 'sonnet', label: 'sonnet' },
                      { value: 'opus', label: 'opus' },
                    ]}
                  />

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
                    <div className="font-display font-bold text-sm mb-2">QA engines</div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">
                      QA sub-agent engines are configured in <span className="font-display font-semibold">Settings → Engines</span>.
                      This section only controls when the QA fixer runs and how long it can try.
                    </div>
                  </div>

                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Controller</span>
                    <input type="checkbox" checked={draft.controller_enabled} onChange={(e) => setDraft({ ...draft, controller_enabled: e.target.checked })} className="w-5 h-5" />
                  </label>
                  <Field label="Controller max sessions" value={draft.controller_max_sessions} onChange={(v) => setDraft({ ...draft, controller_max_sessions: clampInt(v, 0, 50) })} />
                  <SelectField
                    label="Controller model (optional)"
                    value={(draft.controller_model || '').trim().toLowerCase()}
                    onChange={(v) => setDraft({ ...draft, controller_model: v })}
                    options={[
                      { value: '', label: 'Auto' },
                      { value: 'haiku', label: 'haiku' },
                      { value: 'sonnet', label: 'sonnet' },
                      { value: 'opus', label: 'opus' },
                    ]}
                  />
                </div>
              </details>

              <details className="neo-card p-4" open={draft.regression_pool_enabled}>
                <summary className="font-display font-bold uppercase cursor-pointer select-none">Regression Pool</summary>
                <div className="flex justify-end mt-2">
                  <button
                    type="button"
                    className="neo-btn neo-btn-secondary neo-btn-sm"
                    onClick={() => setHelpTopic('regression_pool')}
                    title="Explain regression pool"
                  >
                    <Info size={14} />
                    What’s this?
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Enable regression testers</span>
                    <input
                      type="checkbox"
                      checked={draft.regression_pool_enabled}
                      onChange={(e) => setDraft({ ...draft, regression_pool_enabled: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </label>
                  <Field
                    label="Max testers"
                    value={draft.regression_pool_max_agents}
                    onChange={(v) => setDraft({ ...draft, regression_pool_max_agents: clampInt(v, 0, 10) })}
                    error={validation.fieldErrors.regression_pool_max_agents}
                  />
                  <Field
                    label="Min interval (s)"
                    value={draft.regression_pool_min_interval_s}
                    onChange={(v) => setDraft({ ...draft, regression_pool_min_interval_s: clampInt(v, 30, 86400) })}
                  />
                  <Field
                    label="Max iters"
                    value={draft.regression_pool_max_iterations}
                    onChange={(v) => setDraft({ ...draft, regression_pool_max_iterations: clampInt(v, 1, 5) })}
                  />
                  <SelectField
                    label="Model (optional)"
                    value={(draft.regression_pool_model || '').trim().toLowerCase()}
                    onChange={(v) => setDraft({ ...draft, regression_pool_model: v })}
                    options={[
                      { value: '', label: 'Auto (sonnet)' },
                      { value: 'haiku', label: 'haiku' },
                      { value: 'sonnet', label: 'sonnet' },
                      { value: 'opus', label: 'opus' },
                    ]}
                  />
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Spawns short-lived Claude+Playwright testers when there are no claimable pending features. On failure,
                  it creates a new <span className="font-mono">REGRESSION</span> feature linked to the original passing feature.
                </div>
              </details>

              <details className="neo-card p-4" open={draft.planner_enabled}>
                <summary className="font-display font-bold uppercase cursor-pointer select-none">Planner</summary>
                <div className="flex justify-end mt-2">
                  <button
                    type="button"
                    className="neo-btn neo-btn-secondary neo-btn-sm"
                    onClick={() => setHelpTopic('planner')}
                    title="Explain planner"
                  >
                    <Info size={14} />
                    What’s this?
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                    <span className="font-display font-bold text-sm">Feature plan (multi-engine)</span>
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
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-1">Draft engines</div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">
                      Draft engines are set in <span className="font-display font-semibold">Settings → Engines</span>
                      (<span className="font-mono">spec_draft</span> chain).
                    </div>
                  </div>
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-2">Synthesizer</div>
                    <select
                      value={draft.planner_synthesizer}
                      onChange={(e) => setDraft({ ...draft, planner_synthesizer: e.target.value as AdvancedSettings['planner_synthesizer'] })}
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="claude">claude</option>
                      <option value="none">none</option>
                      <option value="codex" disabled={setupStatus ? !setupStatus.codex_cli : false}>
                        codex
                      </option>
                      <option value="gemini" disabled={setupStatus ? !setupStatus.gemini_cli : false}>
                        gemini
                      </option>
                    </select>
                  </div>
                  <SelectField
                    label="Claude model (optional)"
                    value={(draft.planner_model || '').trim().toLowerCase()}
                    onChange={(v) => setDraft({ ...draft, planner_model: v })}
                    options={[
                      { value: '', label: 'Auto (sonnet)' },
                      { value: 'haiku', label: 'haiku' },
                      { value: 'sonnet', label: 'sonnet' },
                      { value: 'opus', label: 'opus' },
                    ]}
                  />
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Generates a short implementation plan per feature and prepends it to the worker prompt. Uses the draft engines
                  configured in Settings → Engines, with optional synthesis.
                </div>
              </details>

              <details className="neo-card p-4" open={draft.initializer_synthesizer !== 'claude'}>
                <summary className="font-display font-bold uppercase cursor-pointer select-none">Initializer</summary>
                <div className="flex justify-end mt-2">
                  <button
                    type="button"
                    className="neo-btn neo-btn-secondary neo-btn-sm"
                    onClick={() => setHelpTopic('initializer')}
                    title="Explain initializer"
                  >
                    <Info size={14} />
                    What’s this?
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-1">Initializer engines</div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">
                      Draft engines live in <span className="font-display font-semibold">Settings → Engines</span>
                      (<span className="font-mono">initializer</span> chain).
                    </div>
                  </div>
                  <div className="neo-card p-3">
                    <div className="font-display font-bold text-sm mb-2">Synthesizer</div>
                    <select
                      value={draft.initializer_synthesizer}
                      onChange={(e) =>
                        setDraft({ ...draft, initializer_synthesizer: e.target.value as AdvancedSettings['initializer_synthesizer'] })
                      }
                      className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                    >
                      <option value="claude">claude</option>
                      <option value="none">none</option>
                      <option value="codex" disabled={setupStatus ? !setupStatus.codex_cli : false}>
                        codex
                      </option>
                      <option value="gemini" disabled={setupStatus ? !setupStatus.gemini_cli : false}>
                        gemini
                      </option>
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
              </details>
            </div>
          )}

          {tab === 'gatekeeper' && (
            <div className="neo-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="font-display font-bold uppercase">Gatekeeper</div>
                <button
                  type="button"
                  className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                  onClick={() => setHelpTopic('gatekeeper')}
                  title="What is Gatekeeper?"
                  aria-label="Help: Gatekeeper"
                >
                  <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Require Gatekeeper</span>
                  <input
                    type="checkbox"
                    checked={draft.require_gatekeeper}
                    onChange={(e) =>
                      requestDangerToggle('require_gatekeeper', e.target.checked, {
                        title: 'Disable Gatekeeper?',
                        message:
                          'Gatekeeper is the deterministic merge gate. Disabling it means features may merge without running verification commands in a clean temp worktree.',
                        confirmText: 'Disable Gatekeeper',
                        variant: 'danger',
                      })
                    }
                    className="w-5 h-5"
                  />
                </label>
                <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
                  <span className="font-display font-bold text-sm">Allow No Tests</span>
                  <input
                    type="checkbox"
                    checked={draft.allow_no_tests}
                    onChange={(e) =>
                      requestDangerToggle('allow_no_tests', e.target.checked, {
                        title: 'Allow merges without tests?',
                        message:
                          'This allows Gatekeeper to proceed even when no deterministic test command exists. It’s basically YOLO for merges.',
                        confirmText: 'Allow no-tests',
                        variant: 'warning',
                      })
                    }
                    className="w-5 h-5"
                  />
                </label>
              </div>
              <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                <div>
                  <span className="font-display font-semibold">Require Gatekeeper</span>: recommended. Disabling it removes the deterministic merge gate.
                </div>
                <div className="mt-1">
                  <span className="font-display font-semibold">Allow No Tests</span>: only use if you explicitly want merges to proceed when no test command exists (YOLO vibes).
                </div>
              </div>
            </div>
          )}

          {tab === 'logs' && (
            <div className="neo-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="font-display font-bold uppercase">Log Retention</div>
                <button
                  type="button"
                  className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                  onClick={() => setHelpTopic('logs')}
                  title="Help: Logs"
                  aria-label="Help: Logs"
                >
                  <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                </button>
              </div>
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

              <div className="mt-4 border-t-2 border-[var(--color-neo-border)] pt-3">
                <div className="font-display font-bold text-sm mb-2">Mission Control feed</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field
                    label="Keep days"
                    value={draft.activity_keep_days}
                    onChange={(v) => setDraft({ ...draft, activity_keep_days: clampInt(v, 0, 3650) })}
                  />
                  <Field
                    label="Max events"
                    value={draft.activity_keep_rows}
                    onChange={(v) => setDraft({ ...draft, activity_keep_rows: clampInt(v, 0, 200000) })}
                  />
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
                  Stored in <span className="font-mono">agent_system.db</span>. Pruned periodically during runs.
                </div>
              </div>
            </div>
          )}

          {tab === 'retry' && (
            <div className="neo-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="font-display font-bold uppercase">SDK Retry/Backoff</div>
                <button
                  type="button"
                  className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                  onClick={() => setHelpTopic('retry')}
                  title="Help: Retry/Backoff"
                  aria-label="Help: Retry/Backoff"
                >
                  <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                </button>
              </div>
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
              <div className="flex items-center gap-2 mb-3">
                <div className="font-display font-bold uppercase">Port Pools</div>
                <button
                  type="button"
                  className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                  onClick={() => setHelpTopic('ports')}
                  title="Help: Ports"
                  aria-label="Help: Ports"
                >
                  <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                </button>
              </div>
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
              <div className="flex items-center gap-2 mb-3">
                <div className="font-display font-bold uppercase">Agent Status Colors</div>
                <button
                  type="button"
                  className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                  onClick={() => setHelpTopic('ui')}
                  title="Help: UI"
                  aria-label="Help: UI"
                >
                  <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
                </button>
              </div>
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

      <HelpModal
        isOpen={helpTopic !== null}
        title={helpTopic ? HELP_CONTENT[helpTopic].title : ''}
        onClose={() => setHelpTopic(null)}
      >
        {helpTopic ? HELP_CONTENT[helpTopic].body : null}
      </HelpModal>

      <ConfirmationDialog
        isOpen={confirmToggle !== null}
        title={confirmToggle?.title ?? ''}
        message={confirmToggle?.message ?? ''}
        confirmText={confirmToggle?.confirmText ?? 'Confirm'}
        cancelText="Cancel"
        variant={confirmToggle?.variant ?? 'warning'}
        onConfirm={() => {
          if (!confirmToggle) return
          setDraft({ ...draft, [confirmToggle.field]: confirmToggle.next } as AdvancedSettings)
          setConfirmToggle(null)
        }}
        onCancel={() => setConfirmToggle(null)}
      />
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  error,
  warning,
  disabled,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  error?: string
  warning?: string
  disabled?: boolean
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
        disabled={disabled}
        className={`neo-btn text-sm py-2 px-3 bg-white border-3 ${border} font-mono w-full ${
          disabled ? 'opacity-60 cursor-not-allowed' : ''
        }`}
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
  disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  error?: string
  warning?: string
  disabled?: boolean
}) {
  const border =
    error ? 'border-[var(--color-neo-danger)]' : warning ? 'border-yellow-600' : 'border-[var(--color-neo-border)]'
  return (
    <div>
      {label ? <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div> : null}
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`neo-btn text-sm py-2 px-3 bg-white border-3 ${border} font-mono w-full ${
          disabled ? 'opacity-60 cursor-not-allowed' : ''
        }`}
      />
      {error && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{error}</div>}
      {!error && warning && <div className="text-xs mt-1 text-yellow-800">{warning}</div>}
    </div>
  )
}

function SelectField({
  label,
  value,
  onChange,
  options,
  error,
  warning,
  disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: Array<{ value: string; label: string }>
  error?: string
  warning?: string
  disabled?: boolean
}) {
  const border =
    error ? 'border-[var(--color-neo-danger)]' : warning ? 'border-yellow-600' : 'border-[var(--color-neo-border)]'
  return (
    <div>
      <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`neo-btn text-sm py-2 px-3 bg-white border-3 ${border} font-mono w-full ${
          disabled ? 'opacity-60 cursor-not-allowed' : ''
        }`}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
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

