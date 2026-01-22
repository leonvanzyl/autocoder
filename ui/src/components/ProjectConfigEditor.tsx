/**
 * Project Config Editor
 * =====================
 *
 * Edits the target project's `autocoder.yaml` (Gatekeeper verification commands + review config).
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, FileText, Info, RefreshCw, Save } from 'lucide-react'
import { useAutocoderYaml, useUpdateAutocoderYaml } from '../hooks/useProjectConfig'
import { useProjects } from '../hooks/useProjects'
import * as api from '../lib/api'
import { InlineNotice, type InlineNoticeType } from './InlineNotice'
import { HelpModal } from './HelpModal'

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
#   engines: [claude_review, codex_cli, gemini_cli]
#   consensus: majority  # majority|all|any
`

type HelpTopic = 'all' | 'overview' | 'import' | 'template' | 'commands' | 'placeholders' | 'review'

export function ProjectConfigEditor({ projectName }: { projectName: string }) {
  const q = useAutocoderYaml(projectName)
  const save = useUpdateAutocoderYaml(projectName)
  const projectsQ = useProjects()

  const [draft, setDraft] = useState('')
  const [dirty, setDirty] = useState(false)
  const [importFrom, setImportFrom] = useState('')
  const [importError, setImportError] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [helpTopic, setHelpTopic] = useState<HelpTopic>('all')
  const [justSaved, setJustSaved] = useState(false)
  const [notice, setNotice] = useState<{ type: InlineNoticeType; message: string } | null>(null)
  const noticeTimer = useRef<number | null>(null)
  const savedTimer = useRef<number | null>(null)

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

  useEffect(() => {
    return () => {
      if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
      if (savedTimer.current) window.clearTimeout(savedTimer.current)
    }
  }, [])

  const flash = (type: InlineNoticeType, message: string) => {
    setNotice({ type, message })
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(null), 2500)
  }

  const helpContent: Record<Exclude<HelpTopic, 'all'>, { title: string; body: string }> = {
    overview: {
      title: 'What is autocoder.yaml?',
      body:
        'This file lives in your target project and tells Gatekeeper what to run for setup/tests/lint/typecheck/acceptance. If Gatekeeper is rejecting merges, this is where you tune the commands.',
    },
    import: {
      title: 'Import config from another project',
      body:
        'Use this to copy a working autocoder.yaml from another project. It only overwrites the editor text until you click Save. Great for standardizing commands across projects.',
    },
    template: {
      title: 'Template starter',
      body:
        'Inserts a safe starting template. Replace commands for your stack (npm/pnpm/pytest/etc.). If the file doesn’t exist yet, the template is the fastest way to get Gatekeeper unblocked.',
    },
    commands: {
      title: 'Commands (what Gatekeeper runs)',
      body:
        'Commands are grouped under `commands:`. Gatekeeper can run setup/test/lint/typecheck/acceptance with timeouts. If your project has no tests, either add a test script or explicitly configure Gatekeeper (or enable YOLO).',
    },
    placeholders: {
      title: 'Placeholders: {PY} and {VENV_PY}',
      body:
        '{PY} is your system Python. {VENV_PY} is the project venv Python (e.g. .venv). Use these to keep commands cross-platform (Windows/macOS/Linux).',
    },
    review: {
      title: 'Review block (optional)',
      body:
        'The optional `review:` block configures pre-merge review (advisory or gate) using the Review engine chain. Use it for “second set of eyes” before merge; it’s not a replacement for tests.',
    },
  }

  const openHelp = (topic: HelpTopic) => {
    setHelpTopic(topic)
    setShowHelp(true)
  }

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
          <button
            className="neo-btn neo-btn-ghost p-2"
            onClick={() => openHelp('overview')}
            title="What is this file?"
            aria-label="Help: project config"
          >
            <Info size={18} />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button className="neo-btn neo-btn-secondary text-sm" onClick={() => openHelp('all')} title="Help">
            <Info size={16} />
            Help
          </button>
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
              try {
                await save.mutateAsync(draft)
                setDirty(false)
                flash('success', 'Project config saved.')
                setJustSaved(true)
                if (savedTimer.current) window.clearTimeout(savedTimer.current)
                savedTimer.current = window.setTimeout(() => setJustSaved(false), 2000)
              } catch (e: any) {
                flash('error', String(e?.message || e))
              }
            }}
            disabled={save.isPending || !dirty}
            title={!dirty ? 'No changes' : 'Save autocoder.yaml'}
          >
            {justSaved ? <CheckCircle2 size={18} /> : <Save size={18} />}
            {justSaved ? 'Saved' : 'Save'}
          </button>
        </div>
      </div>

      <HelpModal isOpen={showHelp} title="Project Config — help" onClose={() => setShowHelp(false)}>
        <div className="space-y-4 text-sm">
          {helpTopic !== 'all' && (
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">Tip: click ⓘ for section-specific help.</div>
              <button className="neo-btn neo-btn-secondary text-sm" onClick={() => setHelpTopic('all')}>
                Show all
              </button>
            </div>
          )}

          {helpTopic === 'all' ? (
            <div className="space-y-3">
              {(Object.keys(helpContent) as Array<Exclude<HelpTopic, 'all'>>).map((key) => (
                <div key={key} className="neo-card p-3 bg-[var(--color-neo-bg)]">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-display font-bold uppercase">{helpContent[key].title}</div>
                    <button className="neo-btn neo-btn-secondary text-sm" onClick={() => setHelpTopic(key)}>
                      Details
                    </button>
                  </div>
                  <div className="text-[var(--color-neo-text-secondary)] mt-1">{helpContent[key].body}</div>
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

      {notice && (
        <InlineNotice type={notice.type} message={notice.message} onClose={() => setNotice(null)} />
      )}

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
              <div className="flex items-start justify-between gap-3">
                <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] break-all">
                  Path: {meta.path}
                </div>
                <button className="neo-btn neo-btn-secondary neo-btn-sm" onClick={() => openHelp('commands')} title="About verification commands">
                  <Info size={14} />
                  Commands
                </button>
              </div>
              <div className="mt-1 text-xs font-mono text-[var(--color-neo-text-secondary)]">
                Inferred preset: {meta.inferred || '(none)'} | Resolved commands: {meta.cmds.length ? meta.cmds.join(', ') : '(none)'}
              </div>
              {!meta.exists && (
                <div className="mt-2 text-xs text-[var(--color-neo-text-secondary)]">
                  File does not exist yet. Use the template below to get started.
                </div>
              )}
            </div>
          )}

          <div className="mt-3 neo-card p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="text-sm font-display font-bold uppercase">Import</div>
              <button
                type="button"
                className="inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                onClick={() => openHelp('import')}
                title="Help: Import"
                aria-label="Help: Import"
              >
                <Info size={16} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
              </button>
            </div>
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
            <button className="neo-btn neo-btn-secondary text-sm" onClick={() => openHelp('template')} title="About the template">
              <Info size={16} />
              Template help
            </button>
            <div className="text-xs text-[var(--color-neo-text-secondary)] self-center">
              Placeholders: <span className="font-mono">{'{PY}'}</span> and <span className="font-mono">{'{VENV_PY}'}</span>.
              <button
                type="button"
                className="ml-2 inline-flex items-center justify-center p-1 rounded hover:bg-black/5"
                onClick={() => openHelp('placeholders')}
                title="Help: placeholders"
                aria-label="Help: placeholders"
              >
                <Info size={14} className="text-[var(--color-neo-text-secondary)]" aria-hidden="true" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
