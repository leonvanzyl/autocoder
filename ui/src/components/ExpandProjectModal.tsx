/**
 * Expand Project Modal
 *
 * Full-screen modal wrapper for the ExpandProjectChat component.
 * Allows users to add multiple features to an existing project via AI.
 */

import { ExpandProjectChat } from './ExpandProjectChat'

interface ExpandProjectModalProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onFeaturesAdded: () => void  // Called to refresh feature list
}

export function ExpandProjectModal({
  isOpen,
  projectName,
  onClose,
  onFeaturesAdded,
}: ExpandProjectModalProps) {
  if (!isOpen) return null

  const handleComplete = (featuresAdded: number) => {
    if (featuresAdded > 0) {
      onFeaturesAdded()
    }
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 bg-[var(--color-neo-bg)]">
      <ExpandProjectChat
        projectName={projectName}
        onComplete={handleComplete}
        onCancel={onClose}
      />
    </div>
  )
}
