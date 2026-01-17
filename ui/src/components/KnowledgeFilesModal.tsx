import { useEffect, useMemo, useState } from 'react'
import { BookOpen, Plus, Save, Trash2, X, RefreshCcw, Copy } from 'lucide-react'
import { useKnowledgeFiles, useKnowledgeFile, useSaveKnowledgeFile, useDeleteKnowledgeFile } from '../hooks/useKnowledgeFiles'
import { ConfirmationDialog } from './ConfirmationDialog'

interface KnowledgeFilesModalProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

export function KnowledgeFilesModal({ projectName, isOpen, onClose }: KnowledgeFilesModalProps) {
  const listQ = useKnowledgeFiles(isOpen ? projectName : null)
  const save = useSaveKnowledgeFile(projectName)
  const remove = useDeleteKnowledgeFile(projectName)

  const [selected, setSelected] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  const [draftContent, setDraftContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConfirmDelete, setShowConfirmDelete] = useState(false)
  const [creatingNew, setCreatingNew] = useState(false)

  const fileQ = useKnowledgeFile(projectName, selected)

  const directory = listQ.data?.directory || 'knowledge'

  useEffect(() => {
    if (!listQ.data || selected || creatingNew) return
    const first = listQ.data.files?.[0]
    if (first?.name) {
      setSelected(first.name)
    }
  }, [listQ.data, selected])

  useEffect(() => {
    if (!fileQ.data || dirty) return
    setDraftName(fileQ.data.name)
    setDraftContent(fileQ.data.content || '')
  }, [fileQ.data, dirty])

  const activeName = selected ?? draftName
  const isNew = !selected

  const canSave = activeName.trim().length > 0 && !save.isPending
  const canDelete = !!selected && !remove.isPending

  const nameError = useMemo(() => {
    if (!activeName) return 'File name required'
    if (!/^[a-zA-Z0-9._-]+$/.test(activeName)) return 'Use letters, numbers, dash, dot or underscore'
    if (!activeName.toLowerCase().endsWith('.md')) return 'Must end with .md'
    return null
  }, [activeName])

  const handleNew = () => {
    setSelected(null)
    setDraftName('')
    setDraftContent('')
    setDirty(false)
    setError(null)
    setCreatingNew(true)
  }

  const handleSave = async () => {
    setError(null)
    if (nameError) {
      setError(nameError)
      return
    }
    try {
      const name = activeName.trim()
      await save.mutateAsync({ filename: name, content: draftContent })
      setSelected(name)
      setDirty(false)
      setCreatingNew(false)
      listQ.refetch()
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  const handleDelete = async () => {
    if (!selected) return
    setError(null)
    try {
      await remove.mutateAsync(selected)
      setSelected(null)
      setDraftName('')
      setDraftContent('')
      setDirty(false)
      setCreatingNew(false)
      listQ.refetch()
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  const handleCopyDir = async () => {
    try {
      await navigator.clipboard.writeText(directory)
    } catch {
      // ignore
    }
  }

  if (!isOpen) return null

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-5xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <BookOpen size={22} className="text-[var(--color-neo-accent)]" />
            <div>
              <div className="font-display font-bold uppercase">Knowledge Files</div>
              <div className="text-xs text-[var(--color-neo-text-secondary)]">
                Project-scoped notes injected into agent prompts.
              </div>
            </div>
          </div>
          <button onClick={onClose} className="neo-btn neo-btn-ghost p-2" title="Close">
            <X size={18} />
          </button>
        </div>

        <div className="p-4 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)] flex items-center gap-2">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">Dir</div>
          <div className="text-xs font-mono break-all flex-1">{directory}</div>
          <button className="neo-btn neo-btn-secondary text-xs" onClick={handleCopyDir}>
            <Copy size={14} />
            Copy
          </button>
        </div>

        <div className="flex-1 overflow-hidden grid grid-cols-1 md:grid-cols-[260px_1fr] gap-4 p-4">
          <div className="neo-card p-3 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <div className="font-display font-bold uppercase text-sm">Files</div>
              <button className="neo-btn neo-btn-secondary text-xs" onClick={handleNew}>
                <Plus size={14} />
                New
              </button>
            </div>

            {listQ.isLoading ? (
              <div className="text-xs text-[var(--color-neo-text-secondary)]">Loading…</div>
            ) : listQ.data?.files?.length ? (
              <div className="space-y-2">
                {listQ.data.files.map((file) => (
                  <button
                    key={file.name}
                    className={`neo-btn w-full text-left text-xs px-3 py-2 ${
                      file.name === selected ? 'neo-btn-primary' : 'neo-btn-secondary'
                    }`}
                    onClick={() => {
                      setSelected(file.name)
                      setDirty(false)
                      setError(null)
                      setCreatingNew(false)
                    }}
                  >
                    <div className="truncate font-mono">{file.name}</div>
                    <div className="text-[10px] opacity-70">{new Date(file.modified_at).toLocaleString()}</div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-xs text-[var(--color-neo-text-secondary)]">No knowledge files yet.</div>
            )}
          </div>

          <div className="neo-card p-3 flex flex-col min-h-0">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="text-xs font-display font-bold uppercase">Editor</div>
              <div className="flex items-center gap-2">
                <button
                  className="neo-btn neo-btn-secondary text-xs"
                  onClick={() => listQ.refetch()}
                  title="Refresh list"
                >
                  <RefreshCcw size={14} />
                  Refresh
                </button>
                <button
                  className="neo-btn neo-btn-primary text-xs"
                  disabled={!canSave}
                  onClick={handleSave}
                  title="Save"
                >
                  <Save size={14} />
                  Save
                </button>
                <button
                  className="neo-btn neo-btn-danger text-xs"
                  disabled={!canDelete}
                  onClick={() => setShowConfirmDelete(true)}
                  title="Delete"
                >
                  <Trash2 size={14} />
                  Delete
                </button>
              </div>
            </div>

            <div className="mb-3">
              <label className="text-xs font-mono text-[var(--color-neo-text-secondary)]">File name</label>
              <input
                className="neo-input mt-1"
                value={isNew ? draftName : selected || ''}
                onChange={(e) => {
                  if (!isNew) return
                  setDraftName(e.target.value)
                  setDirty(true)
                }}
                disabled={!isNew}
                placeholder="notes.md"
              />
              {isNew && nameError && (
                <div className="text-xs text-[var(--color-neo-danger)] mt-1">{nameError}</div>
              )}
            </div>

            <textarea
              className="neo-input flex-1 min-h-[240px] font-mono text-sm"
              value={draftContent}
              onChange={(e) => {
                setDraftContent(e.target.value)
                setDirty(true)
              }}
              placeholder="Add project-specific context, decisions, or constraints…"
            />

            <div className="mt-2 text-xs text-[var(--color-neo-text-secondary)]">
              Tip: keep these short and specific. Agents read them before planning.
            </div>

            {error && (
              <div className="mt-2 text-xs text-[var(--color-neo-danger)]">
                {error}
              </div>
            )}
          </div>
        </div>
      </div>

      <ConfirmationDialog
        isOpen={showConfirmDelete}
        title="Delete knowledge file?"
        message={`Delete "${selected}"? This cannot be undone.`}
        confirmText="Delete"
        cancelText="Cancel"
        onCancel={() => setShowConfirmDelete(false)}
        onConfirm={async () => {
          setShowConfirmDelete(false)
          await handleDelete()
        }}
        variant="danger"
      />
    </div>
  )
}
