/**
 * Model Settings Panel
 * ====================
 *
 * Modal wrapper for model settings.
 */

import { X, Brain } from 'lucide-react'
import { ModelSettingsContent } from './ModelSettingsContent'

interface ModelSettingsPanelProps {
  onClose: () => void
}

export function ModelSettingsPanel({ onClose }: ModelSettingsPanelProps) {
  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div className="neo-modal w-full max-w-4xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <Brain className="text-[var(--color-neo-accent)]" size={32} />
            <h2 className="font-display text-2xl font-bold uppercase">Model Settings</h2>
          </div>
          <button onClick={onClose} className="neo-btn neo-btn-ghost p-2" aria-label="Close">
            <X size={24} />
          </button>
        </div>

        <div className="p-6">
          <ModelSettingsContent />
        </div>
      </div>
    </div>
  )
}
