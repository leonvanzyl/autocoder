/**
 * Expand Project Modal
 *
 * Full-screen wrapper for ExpandProjectChat.
 */

import { ExpandProjectChat } from './ExpandProjectChat'

interface ExpandProjectModalProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onFeaturesAdded?: () => void
}

export function ExpandProjectModal({
  isOpen,
  projectName,
  onClose,
  onFeaturesAdded,
}: ExpandProjectModalProps) {
  if (!isOpen) return null

  const handleComplete = (featuresAdded: number) => {
    if (featuresAdded > 0) onFeaturesAdded?.()
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

