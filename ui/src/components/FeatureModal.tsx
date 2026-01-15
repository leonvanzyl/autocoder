import { useMemo, useState } from 'react'
import { X, CheckCircle2, Circle, SkipForward, Trash2, Loader2, AlertCircle, Pencil } from 'lucide-react'
import { useSkipFeature, useDeleteFeature } from '../hooks/useProjects'
import type { Feature } from '../lib/types'
import { EditFeatureForm } from './EditFeatureForm'

interface FeatureModalProps {
  feature: Feature
  projectName: string
  onClose: () => void
}

export function FeatureModal({ feature, projectName, onClose }: FeatureModalProps) {
  const [error, setError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isEditing, setIsEditing] = useState(false)

  const status = useMemo(() => (feature.status ?? (feature.in_progress ? 'IN_PROGRESS' : feature.passes ? 'DONE' : 'PENDING')).toUpperCase(), [feature])
  const attempts = feature.attempts ?? 0
  const dependsOn = feature.depends_on ?? []
  const waitingOn = feature.waiting_on ?? []
  const ready = !!feature.ready

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

  if (isEditing) {
    return (
      <EditFeatureForm
        feature={feature}
        projectName={projectName}
        onClose={() => setIsEditing(false)}
        onSaved={() => {
          setIsEditing(false)
          onClose()
        }}
      />
    )
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
            {status === 'BLOCKED' ? (
              <>
                <AlertCircle size={24} className="text-[var(--color-neo-danger)]" />
                <span className="font-display font-bold text-[var(--color-neo-danger)]">
                  BLOCKED
                </span>
              </>
            ) : feature.in_progress ? (
              <>
                <Loader2 size={24} className="animate-spin text-[var(--color-neo-progress)]" />
                <span className="font-display font-bold text-[var(--color-neo-progress)]">
                  IN PROGRESS
                </span>
              </>
            ) : feature.passes ? (
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
              Priority: #{feature.priority}{attempts > 0 ? ` | Attempts: ${attempts}` : ''}
            </span>
          </div>

          {status === 'PENDING' && dependsOn.length > 0 && (
            <div className="neo-card p-3 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]">
              <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Dependency status</div>
              <div className="font-mono text-sm">
                {ready ? (
                  <span className="text-green-700">READY</span>
                ) : waitingOn.length > 0 ? (
                  <span className="text-[var(--color-neo-text-secondary)]">Waiting on: {waitingOn.join(', ')}</span>
                ) : (
                  <span className="text-[var(--color-neo-text-secondary)]">Not ready yet (retry backoff)</span>
                )}
              </div>
            </div>
          )}

          {dependsOn.length > 0 && (
            <div>
              <h3 className="font-display font-bold mb-2 uppercase text-sm">
                Depends On
              </h3>
              <div className="neo-card p-3 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)] font-mono text-sm">
                {dependsOn.join(', ')}
              </div>
            </div>
          )}

          {/* Description */}
          <div>
            <h3 className="font-display font-bold mb-2 uppercase text-sm">
              Description
            </h3>
            <p className="text-[var(--color-neo-text-secondary)]">
              {feature.description}
            </p>
          </div>

          {feature.last_error && String(feature.last_error).trim().length > 0 && (
            <div>
              <h3 className="font-display font-bold mb-2 uppercase text-sm">
                Last Error
              </h3>
              <pre className="neo-card p-3 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)] text-[11px] font-mono whitespace-pre-wrap overflow-auto max-h-48">
                {feature.last_error}
              </pre>
            </div>
          )}

          {feature.last_artifact_path && String(feature.last_artifact_path).trim().length > 0 && (
            <div>
              <h3 className="font-display font-bold mb-2 uppercase text-sm">
                Artifact
              </h3>
              <div className="neo-card p-3 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)] font-mono text-sm break-all">
                {feature.last_artifact_path}
              </div>
            </div>
          )}

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
                  onClick={() => setIsEditing(true)}
                  disabled={skipFeature.isPending || status === 'DONE'}
                  className="neo-btn neo-btn-secondary"
                  title="Edit feature details"
                >
                  <Pencil size={18} />
                </button>
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
