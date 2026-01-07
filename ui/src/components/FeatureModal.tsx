import { useState } from 'react'
import { X, CheckCircle2, Circle, SkipForward, Trash2, Loader2, AlertCircle } from 'lucide-react'
import { useSkipFeature, useDeleteFeature } from '../hooks/useProjects'
import type { Feature } from '../lib/types'

interface FeatureModalProps {
  feature: Feature
  projectName: string
  onClose: () => void
}

export function FeatureModal({ feature, projectName, onClose }: FeatureModalProps) {
  const [error, setError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const skipFeature = useSkipFeature(projectName)
  const deleteFeature = useDeleteFeature(projectName)

  const handleSkip = async () => {
    setError(null)
    try {
      await skipFeature.mutateAsync(feature.id)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to skip feature')
    }
  }

  const handleDelete = async () => {
    setError(null)
    try {
      await deleteFeature.mutateAsync(feature.id)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete feature')
    }
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-2xl p-0"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <div>
            <span className="neo-badge bg-[var(--color-neo-accent)] text-white mb-2">
              {feature.category}
            </span>
            <h2 className="font-display text-2xl font-bold">
              {feature.name}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="neo-btn neo-btn-ghost p-2"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-3 p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
              <AlertCircle size={20} />
              <span>{error}</span>
              <button
                onClick={() => setError(null)}
                className="ml-auto"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Status */}
          <div className="flex items-center gap-3 p-4 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]">
            {feature.passes ? (
              <>
                <CheckCircle2 size={24} className="text-[var(--color-neo-done)]" />
                <span className="font-display font-bold text-[var(--color-neo-done)]">
                  COMPLETE
                </span>
              </>
            ) : (
              <>
                <Circle size={24} className="text-[var(--color-neo-text-secondary)]" />
                <span className="font-display font-bold text-[var(--color-neo-text-secondary)]">
                  PENDING
                </span>
              </>
            )}
            <span className="ml-auto font-mono text-sm">
              Priority: #{feature.priority}
            </span>
          </div>

          {/* Description */}
          <div>
            <h3 className="font-display font-bold mb-2 uppercase text-sm">
              Description
            </h3>
            <p className="text-[var(--color-neo-text-secondary)]">
              {feature.description}
            </p>
          </div>

          {/* Steps */}
          {feature.steps.length > 0 && (
            <div>
              <h3 className="font-display font-bold mb-2 uppercase text-sm">
                Test Steps
              </h3>
              <ol className="list-decimal list-inside space-y-2">
                {feature.steps.map((step, index) => (
                  <li
                    key={index}
                    className="p-3 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]"
                  >
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {/* Actions */}
        {!feature.passes && (
          <div className="p-6 border-t-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
            {showDeleteConfirm ? (
              <div className="space-y-4">
                <p className="font-bold text-center">
                  Are you sure you want to delete this feature?
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleDelete}
                    disabled={deleteFeature.isPending}
                    className="neo-btn neo-btn-danger flex-1"
                  >
                    {deleteFeature.isPending ? (
                      <Loader2 size={18} className="animate-spin" />
                    ) : (
                      'Yes, Delete'
                    )}
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={deleteFeature.isPending}
                    className="neo-btn neo-btn-ghost flex-1"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex gap-3">
                <button
                  onClick={handleSkip}
                  disabled={skipFeature.isPending}
                  className="neo-btn neo-btn-warning flex-1"
                >
                  {skipFeature.isPending ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <>
                      <SkipForward size={18} />
                      Skip (Move to End)
                    </>
                  )}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  disabled={skipFeature.isPending}
                  className="neo-btn neo-btn-danger"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
