/**
 * Project Config Editor
 * =====================
 *
 * Edits the target project's `autocoder.yaml` (Gatekeeper verification commands + review config).
 */

import { useEffect, useMemo, useState } from 'react'
import { FileText, RefreshCw, Save } from 'lucide-react'
import { useAutocoderYaml, useUpdateAutocoderYaml } from '../hooks/useProjectConfig'
import { useProjects } from '../hooks/useProjects'
import * as api from '../lib/api'

const TEMPLATE = `# autocoder.yaml
# Controls Gatekeeper verification for this project.
#
# Minimal example (Python):
# preset: python
#
# commands:
#   setup:
#     command: "{PY} -m venv .venv && {VENV_PY} -m pip install -r requirements.txt"
#     timeout: 900
#   test:
#     command: "{VENV_PY} -m pytest -q"
#     timeout: 900
#
# Optional additional verification steps (under commands:):
#   acceptance:
#     command: "npm run acceptance"   # or "npx playwright test", etc.
#     timeout: 1800
#
# Optional review gate (Codex/Gemini via local CLIs):
# review:
#   enabled: false
#   mode: advisory       # off|advisory|gate
#   type: multi_cli      # none|command|claude|multi_cli
#   agents: [codex, gemini]
#   consensus: majority  # majority|all|any
#
# Optional per-project feature worker defaults:
# worker:
#   provider: claude            # claude|codex_cli|gemini_cli|multi_cli
#   patch_max_iterations: 2     # for patch workers
#   patch_agents: [codex, gemini]  # order for multi_cli
#
# Optional initializer defaults (multi-model backlog generation):
# initializer:
#   provider: claude           # claude|codex_cli|gemini_cli|multi_cli
#   agents: [codex, gemini]    # used when provider=multi_cli
#   synthesizer: claude        # none|claude|codex|gemini
#   timeout_s: 300
#   stage_threshold: 120       # stage backlog above this count
#   enqueue_count: 30          # keep this many enabled
`

export function ProjectConfigEditor({ projectName }: { projectName: string }) {
  const q = useAutocoderYaml(projectName)
  const save = useUpdateAutocoderYaml(projectName)
  const projectsQ = useProjects()

  const [draft, setDraft] = useState('')
  const [dirty, setDirty] = useState(false)
  const [importFrom, setImportFrom] = useState('')
  const [importError, setImportError] = useState<string | null>(null)

  useEffect(() => {
    if (!q.data) return
    if (dirty) return
    setDraft(q.data.content || '')
  }, [q.data, dirty])

  const meta = useMemo(() => {
    if (!q.data) return null
    return {
      path: q.data.path,
      inferred: q.data.inferred_preset || null,
      cmds: q.data.resolved_commands || [],
      workerProvider: q.data.resolved_worker_provider || null,
      workerIters: q.data.resolved_worker_patch_max_iterations ?? null,
      initializerProvider: q.data.resolved_initializer_provider || null,
      initializerAgents: q.data.resolved_initializer_agents || null,
      initializerSynthesizer: q.data.resolved_initializer_synthesizer || null,
      initializerTimeout: q.data.resolved_initializer_timeout_s ?? null,
      initializerStage: q.data.resolved_initializer_stage_threshold ?? null,
      initializerEnqueue: q.data.resolved_initializer_enqueue_count ?? null,
      exists: q.data.exists,
    }
  }, [q.data])

  return (
    <div className="neo-card p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <FileText className="text-[var(--color-neo-accent)]" size={22} />
          <div>
            <div className="font-display font-bold uppercase">Project Config</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Edits <span className="font-mono">autocoder.yaml</span> in the target project root.
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="neo-btn neo-btn-secondary text-sm"
            onClick={() => q.refetch()}
            disabled={q.isFetching}
            title="Reload from disk"
          >
            <RefreshCw size={18} />
            Reload
          </button>
          <button
            className="neo-btn neo-btn-primary text-sm"
            onClick={async () => {
              await save.mutateAsync(draft)
              setDirty(false)
            }}
            disabled={save.isPending || !dirty}
            title={!dirty ? 'No changes' : 'Save autocoder.yaml'}
          >
            <Save size={18} />
            Save
          </button>
        </div>
      </div>

      {q.isLoading ? (
        <div className="mt-4 text-sm text-[var(--color-neo-text-secondary)]">Loading…</div>
      ) : q.error ? (
        <div className="mt-4 neo-card p-3 border-3 border-[var(--color-neo-danger)]">
          <div className="text-sm font-bold text-[var(--color-neo-danger)]">Error</div>
          <div className="text-sm">{String((q.error as any)?.message || q.error)}</div>
        </div>
      ) : (
        <>
          {meta && (
            <div className="mt-4 neo-card p-3 bg-[var(--color-neo-bg)]">
              <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] break-all">
                Path: {meta.path}
              </div>
              <div className="mt-1 text-xs font-mono text-[var(--color-neo-text-secondary)]">
                Inferred preset: {meta.inferred || '(none)'} | Resolved commands: {meta.cmds.length ? meta.cmds.join(', ') : '(none)'}
              </div>
              <div className="mt-1 text-xs font-mono text-[var(--color-neo-text-secondary)]">
                Worker: {meta.workerProvider || '(default)'}
                {meta.workerIters ? ` (patch iters: ${meta.workerIters})` : ''}
              </div>
              <div className="mt-1 text-xs font-mono text-[var(--color-neo-text-secondary)]">
                Initializer: {meta.initializerProvider || '(default)'}
                {meta.initializerAgents && meta.initializerAgents.length > 0
                  ? ` [${meta.initializerAgents.join(', ')}]`
                  : ''}
                {meta.initializerSynthesizer ? ` (synth: ${meta.initializerSynthesizer})` : ''}
                {meta.initializerTimeout ? ` (timeout: ${meta.initializerTimeout}s)` : ''}
              </div>
              <div className="mt-1 text-xs font-mono text-[var(--color-neo-text-secondary)]">
                Staging: {meta.initializerStage ?? '(default)'} threshold, {meta.initializerEnqueue ?? '(default)'} enqueue
              </div>
              {!meta.exists && (
                <div className="mt-2 text-xs text-[var(--color-neo-text-secondary)]">
                  File does not exist yet. Use the template below to get started.
                </div>
              )}
            </div>
          )}

          <div className="mt-3 neo-card p-3">
            <div className="text-sm font-display font-bold uppercase mb-2">Import</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <select
                value={importFrom}
                onChange={(e) => {
                  setImportError(null)
                  setImportFrom(e.target.value)
                }}
                className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                disabled={projectsQ.isLoading || projectsQ.isFetching}
              >
                <option value="">Select a project…</option>
                {(projectsQ.data || [])
                  .map((p) => p.name)
                  .filter((n) => n && n !== projectName)
                  .sort()
                  .map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
              </select>
              <button
                className="neo-btn neo-btn-secondary text-sm"
                disabled={!importFrom}
                onClick={async () => {
                  setImportError(null)
                  try {
                    const other = await api.getAutocoderYaml(importFrom)
                    setDraft(other.content || TEMPLATE)
                    setDirty(true)
                  } catch (e: any) {
                    setImportError(String(e?.message || e))
                  }
                }}
                title="Overwrite editor content with another project's autocoder.yaml"
              >
                Load config
              </button>
              <div className="text-xs text-[var(--color-neo-text-secondary)] self-center">
                Overwrites the editor (doesn’t write to disk until Save).
              </div>
            </div>
            {importError && (
              <div className="mt-2 text-xs text-[var(--color-neo-danger)]">
                Import failed: {importError}
              </div>
            )}
          </div>

          <div className="mt-3">
            <textarea
              value={draft}
              onChange={(e) => {
                setDirty(true)
                setDraft(e.target.value)
              }}
              placeholder={TEMPLATE}
              className="neo-input min-h-[360px] resize-y font-mono text-sm"
            />
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className="neo-btn neo-btn-secondary text-sm"
              onClick={() => {
                setDirty(true)
                setDraft(TEMPLATE)
              }}
              title="Insert a starter template"
            >
              Use template
            </button>
            <div className="text-xs text-[var(--color-neo-text-secondary)] self-center">
              Placeholders: <span className="font-mono">{'{PY}'}</span> and <span className="font-mono">{'{VENV_PY}'}</span>.
            </div>
          </div>
        </>
      )}
    </div>
  )
}
