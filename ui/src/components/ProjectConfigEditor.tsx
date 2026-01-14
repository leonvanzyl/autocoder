/**
 * Project Config Editor
 * =====================
 *
 * Edits the target project's `autocoder.yaml` (Gatekeeper verification commands + review config).
 */

import { useEffect, useMemo, useState } from 'react'
import { FileText, RefreshCw, Save } from 'lucide-react'
import { useAutocoderYaml, useUpdateAutocoderYaml } from '../hooks/useProjectConfig'

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
# Optional review gate (Codex/Gemini via local CLIs):
# review:
#   enabled: false
#   mode: advisory       # off|advisory|gate
#   type: multi_cli      # none|command|claude|multi_cli
#   agents: [codex, gemini]
#   consensus: majority  # majority|all|any
`

export function ProjectConfigEditor({ projectName }: { projectName: string }) {
  const q = useAutocoderYaml(projectName)
  const save = useUpdateAutocoderYaml(projectName)

  const [draft, setDraft] = useState('')
  const [dirty, setDirty] = useState(false)

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
                Inferred preset: {meta.inferred || '(none)'} • Resolved commands: {meta.cmds.length ? meta.cmds.join(', ') : '(none)'}
              </div>
              {!meta.exists && (
                <div className="mt-2 text-xs text-[var(--color-neo-text-secondary)]">
                  File does not exist yet. Use the template below to get started.
                </div>
              )}
            </div>
          )}

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

