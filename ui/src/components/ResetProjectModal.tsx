import { useState } from 'react'
import { X, AlertTriangle, Loader2, RotateCcw } from 'lucide-react'
import { useResetProject } from '../hooks/useProjects'

interface ResetProjectModalProps {
  projectName: string
  onClose: () => void
  onReset?: () => void
}

export function ResetProjectModal({ projectName, onClose, onReset }: ResetProjectModalProps) {
  const [error, setError] = useState<string | null>(null)
  const resetProject = useResetProject()

  const handleReset = async () => {
    setError(null)
    try {
      await resetProject.mutateAsync(projectName)
      onReset?.()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset project')
    }
  }

  return (
    <div className="neo-modal-backdrop" onClick={resetProject.isPending ? undefined : onClose}>
      <div
        className="neo-modal w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <h2 className="font-display text-2xl font-bold flex items-center gap-2">
            <AlertTriangle className="text-[var(--color-neo-warning)]" size={24} />
            Reset Project
          </h2>
          <button
            onClick={onClose}
            disabled={resetProject.isPending}
            className="neo-btn neo-btn-ghost p-2"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-3 p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
              <AlertTriangle size={20} />
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                className="ml-auto"
              >
                <X size={16} />
              </button>
            </div>
          )}

          <p className="text-[var(--color-neo-text)]">
            Are you sure you want to reset <strong>{projectName}</strong>?
          </p>

          <div className="p-4 bg-[var(--color-neo-pending)] border-3 border-[var(--color-neo-border)]">
            <p className="font-bold mb-2">This will delete:</p>
            <ul className="list-disc list-inside space-y-1 text-sm">
              <li>All features and their progress</li>
              <li>Assistant chat history</li>
              <li>Agent settings</li>
            </ul>
          </div>

          <div className="p-4 bg-[var(--color-neo-done)] border-3 border-[var(--color-neo-border)]">
            <p className="font-bold mb-2">This will preserve:</p>
            <ul className="list-disc list-inside space-y-1 text-sm">
              <li>App spec (prompts/app_spec.txt)</li>
              <li>Prompt templates</li>
              <li>Project registration</li>
            </ul>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t-3 border-[var(--color-neo-border)]">
            <button
              onClick={handleReset}
              disabled={resetProject.isPending}
              className="neo-btn bg-[var(--color-neo-danger)] text-white flex-1"
            >
              {resetProject.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  <RotateCcw size={18} />
                  Reset Project
                </>
              )}
            </button>
            <button
              onClick={onClose}
              disabled={resetProject.isPending}
              className="neo-btn neo-btn-ghost"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
