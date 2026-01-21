import { useEffect, useState } from 'react'
import { RotateCcw, Trash2, AlertTriangle, Copy, X, FolderOpen, ShieldAlert } from 'lucide-react'
import { useDeleteProject, useProjectDeleteInfo, useResetProject } from '../hooks/useProjects'
import { ConfirmationDialog } from './ConfirmationDialog'

interface ProjectMaintenanceProps {
  projectName: string
}

export function ProjectMaintenance({ projectName }: ProjectMaintenanceProps) {
  const resetProject = useResetProject()
  const deleteProject = useDeleteProject()
  const [confirmReset, setConfirmReset] = useState(false)
  const [confirmFullReset, setConfirmFullReset] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteFiles, setDeleteFiles] = useState(false)
  const [confirmName, setConfirmName] = useState('')
  const [copied, setCopied] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const deleteInfo = useProjectDeleteInfo(projectName, confirmDelete)

  useEffect(() => {
    if (!confirmDelete) {
      setDeleteFiles(false)
      setConfirmName('')
      setCopied(false)
    }
  }, [confirmDelete])

  const handleReset = async (fullReset: boolean) => {
    setError(null)
    setMessage(null)
    try {
      await resetProject.mutateAsync({ name: projectName, fullReset })
      setMessage(fullReset ? 'Full reset complete.' : 'Project reset complete.')
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  const handleDelete = async () => {
    setError(null)
    setMessage(null)
    try {
      await deleteProject.mutateAsync({ name: projectName, deleteFiles })
      setMessage('Project deleted.')
      window.location.hash = ''
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  const requiresTypedConfirm = Boolean(
    deleteFiles ||
    deleteInfo.data?.git_dirty ||
    deleteInfo.data?.has_prompts ||
    deleteInfo.data?.has_spec ||
    (deleteInfo.data && !deleteInfo.data.runtime_only)
  )
  const typedOk = !requiresTypedConfirm || confirmName.trim() === projectName
  const isBlocked = Boolean(deleteInfo.data?.agent_running)

  const handleCopy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // no-op
    }
  }

  return (
    <div className="neo-card p-4 border-4 border-[var(--color-neo-danger)]">
      <div className="flex items-start gap-3">
        <div className="p-2 bg-[var(--color-neo-danger)] border-3 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
          <AlertTriangle size={18} className="text-white" />
        </div>
        <div>
          <div className="font-display font-bold uppercase">Danger zone</div>
          <div className="text-sm text-[var(--color-neo-text-secondary)]">
            Reset clears runtime state. Full reset also wipes prompts/specs. Delete removes the registry entry.
          </div>
        </div>
      </div>

      {message && (
        <div className="mt-3 neo-card p-3 border-3 border-[var(--color-neo-done)] text-sm">
          {message}
        </div>
      )}

      {error && (
        <div className="mt-3 neo-card p-3 border-3 border-[var(--color-neo-danger)] text-sm text-[var(--color-neo-danger)]">
          {error}
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="neo-card p-3">
          <div className="font-display font-bold uppercase text-sm mb-2">Reset runtime</div>
          <div className="text-xs text-[var(--color-neo-text-secondary)] mb-3">
            Clears <span className="font-mono">agent_system.db</span>, <span className="font-mono">.autocoder</span>, and
            worktrees. Keeps prompts/specs.
          </div>
          <button
            className="neo-btn neo-btn-secondary w-full text-sm"
            onClick={() => setConfirmReset(true)}
            disabled={resetProject.isPending}
          >
            <RotateCcw size={16} />
            Reset
          </button>
        </div>

        <div className="neo-card p-3">
          <div className="font-display font-bold uppercase text-sm mb-2">Full reset</div>
          <div className="text-xs text-[var(--color-neo-text-secondary)] mb-3">
            Wipes <span className="font-mono">prompts/</span> + spec status. You will need to recreate the spec.
          </div>
          <button
            className="neo-btn neo-btn-warning w-full text-sm"
            onClick={() => setConfirmFullReset(true)}
            disabled={resetProject.isPending}
          >
            <RotateCcw size={16} />
            Full reset
          </button>
        </div>

        <div className="neo-card p-3">
          <div className="font-display font-bold uppercase text-sm mb-2">Delete project</div>
          <div className="text-xs text-[var(--color-neo-text-secondary)] mb-3">
            Remove the registry entry, optionally delete files on disk.
          </div>
          <button
            className="neo-btn neo-btn-danger w-full text-sm"
            onClick={() => setConfirmDelete(true)}
            disabled={deleteProject.isPending}
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      </div>

      {confirmDelete && (
        <div className="neo-modal-backdrop">
          <div
            className="neo-modal w-full max-w-2xl p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-display font-bold uppercase">Delete project</div>
                <div className="text-sm text-[var(--color-neo-text-secondary)]">
                  This is permanent if you delete files on disk.
                </div>
              </div>
              <button className="neo-btn neo-btn-secondary" onClick={() => setConfirmDelete(false)}>
                <X size={16} />
                Close
              </button>
            </div>

            {deleteInfo.isLoading ? (
              <div className="mt-4 text-sm text-[var(--color-neo-text-secondary)]">Loading project info…</div>
            ) : deleteInfo.error ? (
              <div className="mt-4 space-y-3">
                <div className="neo-card p-3 border-3 border-[var(--color-neo-danger)] text-sm text-[var(--color-neo-danger)]">
                  {deleteInfo.error instanceof Error ? deleteInfo.error.message : 'Failed to load delete info'}
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">
                  Delete metadata is unavailable. Restart AutoCoder to load the latest API, or continue with a manual delete.
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={deleteFiles}
                    onChange={(e) => setDeleteFiles(e.target.checked)}
                  />
                  Also delete files on disk
                </label>
                <div>
                  <div className="text-xs text-[var(--color-neo-text-secondary)]">
                    Type <span className="font-mono">{projectName}</span> to confirm.
                  </div>
                  <input
                    className="neo-input w-full mt-2"
                    value={confirmName}
                    onChange={(e) => setConfirmName(e.target.value)}
                    placeholder={projectName}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button className="neo-btn neo-btn-secondary" onClick={() => setConfirmDelete(false)}>
                    Cancel
                  </button>
                  <button
                    className="neo-btn neo-btn-danger"
                    onClick={async () => {
                      await handleDelete()
                      setConfirmDelete(false)
                    }}
                    disabled={deleteProject.isPending || confirmName.trim() !== projectName}
                  >
                    <Trash2 size={16} />
                    Delete
                  </button>
                </div>
              </div>
            ) : deleteInfo.data ? (
              <div className="mt-4 space-y-3">
                <div className="neo-card p-3">
                  <div className="flex items-center gap-2 text-sm">
                    <FolderOpen size={16} />
                    <span className="font-mono break-all">{deleteInfo.data.path}</span>
                  </div>
                  {!deleteInfo.data.exists && (
                    <div className="mt-2 text-xs text-[var(--color-neo-danger)]">
                      Project path is missing. Deleting will remove the registry entry only.
                    </div>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                    <button
                      className="neo-btn neo-btn-secondary text-xs"
                      onClick={() => handleCopy(deleteInfo.data.path)}
                    >
                      <Copy size={14} />
                      {copied ? 'Copied' : 'Copy path'}
                    </button>
                    {deleteInfo.data.has_git && (
                      <span className={`neo-badge ${deleteInfo.data.git_dirty ? 'bg-[var(--color-neo-danger)] text-white' : 'bg-[var(--color-neo-progress)] text-[var(--color-neo-text-on-bright)]'}`}>
                        {deleteInfo.data.git_dirty ? 'Git dirty' : 'Git clean'}
                      </span>
                    )}
                    {deleteInfo.data.runtime_only && (
                      <span className="neo-badge bg-[var(--color-neo-done)] text-[var(--color-neo-text-on-bright)]">Runtime only</span>
                    )}
                  </div>
                </div>

                {!deleteInfo.data.runtime_only && (
                  <div className="neo-card p-3 border-3 border-[var(--color-neo-danger)]/40">
                    <div className="flex items-center gap-2 font-display font-bold text-sm">
                      <ShieldAlert size={16} />
                      Non-runtime files detected
                    </div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)] mt-1">
                      These folders/files are not runtime artifacts and may contain your work.
                    </div>
                    {deleteInfo.data.non_runtime_entries.length > 0 && (
                      <ul className="mt-2 text-xs font-mono space-y-1">
                        {deleteInfo.data.non_runtime_entries.map((entry) => (
                          <li key={entry}>{entry}</li>
                        ))}
                        {deleteInfo.data.non_runtime_truncated && (
                          <li>…and {Math.max(0, deleteInfo.data.non_runtime_count - deleteInfo.data.non_runtime_entries.length)} more</li>
                        )}
                      </ul>
                    )}
                  </div>
                )}

                {(deleteInfo.data.has_prompts || deleteInfo.data.has_spec) && (
                  <div className="neo-card p-3">
                    <div className="text-sm font-display font-bold uppercase">Spec assets</div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)] mt-1">
                      Prompts/specs exist for this project. Make sure you have a backup before deleting files.
                    </div>
                  </div>
                )}

                {isBlocked && (
                  <div className="neo-card p-3 border-3 border-[var(--color-neo-danger)] text-sm text-[var(--color-neo-danger)]">
                    Stop the agent before deleting this project.
                  </div>
                )}

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={deleteFiles}
                    disabled={!deleteInfo.data.exists}
                    onChange={(e) => setDeleteFiles(e.target.checked)}
                  />
                  Also delete files on disk
                </label>

                {requiresTypedConfirm && (
                  <div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">
                      Type <span className="font-mono">{projectName}</span> to confirm.
                    </div>
                    <input
                      className="neo-input w-full mt-2"
                      value={confirmName}
                      onChange={(e) => setConfirmName(e.target.value)}
                      placeholder={projectName}
                    />
                  </div>
                )}

                <div className="flex justify-end gap-2">
                  <button className="neo-btn neo-btn-secondary" onClick={() => setConfirmDelete(false)}>
                    Cancel
                  </button>
                  <button
                    className="neo-btn neo-btn-danger"
                    onClick={async () => {
                      await handleDelete()
                      setConfirmDelete(false)
                    }}
                    disabled={deleteProject.isPending || isBlocked || !typedOk}
                  >
                    <Trash2 size={16} />
                    Delete
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4 text-sm text-[var(--color-neo-text-secondary)]">
                No delete info available.
              </div>
            )}
          </div>
        </div>
      )}

      <ConfirmationDialog
        isOpen={confirmReset}
        title="Reset project runtime?"
        message={`This clears runtime state for "${projectName}" but keeps prompts/specs.`}
        confirmText="Reset"
        variant="warning"
        onCancel={() => setConfirmReset(false)}
        onConfirm={async () => {
          setConfirmReset(false)
          await handleReset(false)
        }}
      />

      <ConfirmationDialog
        isOpen={confirmFullReset}
        title="Full reset project?"
        message={`This wipes prompts/specs for "${projectName}". You will need to recreate the spec.`}
        confirmText="Full reset"
        onCancel={() => setConfirmFullReset(false)}
        onConfirm={async () => {
          setConfirmFullReset(false)
          await handleReset(true)
        }}
      />
    </div>
  )
}
