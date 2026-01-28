import { useState } from 'react'
import { X, AlertTriangle, Loader2, RotateCcw, Trash2 } from 'lucide-react'
import { useResetProject } from '../hooks/useProjects'

interface ResetProjectModalProps {
  projectName: string
  onClose: () => void
  onReset?: () => void
}

export function ResetProjectModal({ projectName, onClose, onReset }: ResetProjectModalProps) {
  const [error, setError] = useState<string | null>(null)
  const [fullReset, setFullReset] = useState(false)
  const resetProject = useResetProject()

  const handleReset = async () => {
    setError(null)
    try {
      await resetProject.mutateAsync({ name: projectName, fullReset })
      onReset?.()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset project')
    }
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-lg"
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
            Reset <strong>{projectName}</strong> to start fresh.
          </p>

          {/* Reset Type Toggle */}
          <div className="space-y-3">
            <button
              type="button"
              onClick={() => setFullReset(false)}
              className={`w-full p-4 text-left border-3 border-[var(--color-neo-border)] transition-colors ${
                !fullReset
                  ? 'bg-[var(--color-neo-progress)] shadow-neo'
                  : 'bg-white hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-3">
                <RotateCcw size={20} />
                <div>
                  <p className="font-bold">Quick Reset</p>
                  <p className="text-sm text-[var(--color-neo-text-secondary)]">
                    Keep your app spec and prompts, just clear features and history
                  </p>
                </div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setFullReset(true)}
              className={`w-full p-4 text-left border-3 border-[var(--color-neo-border)] transition-colors ${
                fullReset
                  ? 'bg-[var(--color-neo-danger)] text-white shadow-neo'
                  : 'bg-white hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-3">
                <Trash2 size={20} />
                <div>
                  <p className="font-bold">Full Reset</p>
                  <p className={`text-sm ${fullReset ? 'text-white/80' : 'text-[var(--color-neo-text-secondary)]'}`}>
                    Delete everything including prompts - start completely fresh
                  </p>
                </div>
              </div>
            </button>
          </div>

          {/* What will be deleted */}
          <div className="p-4 bg-[var(--color-neo-pending)] border-3 border-[var(--color-neo-border)]">
            <p className="font-bold mb-2">This will delete:</p>
            <ul className="list-disc list-inside space-y-1 text-sm">
              <li>All features and their progress</li>
              <li>Assistant chat history</li>
              <li>Agent settings</li>
              {fullReset && (
                <li className="font-bold">Prompts directory (app_spec.txt, templates)</li>
              )}
            </ul>
          </div>

          {/* What will be preserved */}
          <div className="p-4 bg-[var(--color-neo-done)] border-3 border-[var(--color-neo-border)]">
            <p className="font-bold mb-2">This will preserve:</p>
            <ul className="list-disc list-inside space-y-1 text-sm">
              {!fullReset && (
                <>
                  <li>App spec (prompts/app_spec.txt)</li>
                  <li>Prompt templates</li>
                </>
              )}
              <li>Project registration</li>
              {fullReset && (
                <li className="text-[var(--color-neo-text-secondary)] italic">
                  (You'll see the setup wizard to create a new spec)
                </li>
              )}
            </ul>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t-3 border-[var(--color-neo-border)]">
            <button
              onClick={handleReset}
              disabled={resetProject.isPending}
              className={`neo-btn flex-1 ${
                fullReset
                  ? 'bg-[var(--color-neo-danger)] text-white'
                  : 'bg-[var(--color-neo-progress)] text-[var(--color-neo-text)]'
              }`}
            >
              {resetProject.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  {fullReset ? <Trash2 size={18} /> : <RotateCcw size={18} />}
                  {fullReset ? 'Full Reset' : 'Quick Reset'}
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
