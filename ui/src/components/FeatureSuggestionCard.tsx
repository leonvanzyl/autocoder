/**
 * Feature Suggestion Card Component
 *
 * Displays a feature suggestion from the chat-to-features interface.
 * Shows feature details with accept/reject actions.
 */

import { Check, X, Lightbulb, Loader2 } from 'lucide-react'

// Generate consistent color for category
function getCategoryColor(category: string): string {
  const colors = [
    '#ff006e', // pink
    '#00b4d8', // cyan
    '#70e000', // green
    '#ffd60a', // yellow
    '#ff5400', // orange
    '#8338ec', // purple
    '#3a86ff', // blue
  ]

  let hash = 0
  for (let i = 0; i < category.length; i++) {
    hash = category.charCodeAt(i) + ((hash << 5) - hash)
  }

  return colors[Math.abs(hash) % colors.length]
}

export interface FeatureSuggestion {
  index: number
  name: string
  category: string
  description: string
  steps: string[]
  reasoning: string
}

interface FeatureSuggestionCardProps {
  suggestion: FeatureSuggestion
  onAccept: () => void
  onReject: () => void
  isCreating?: boolean
}

export function FeatureSuggestionCard({
  suggestion,
  onAccept,
  onReject,
  isCreating = false,
}: FeatureSuggestionCardProps) {
  const categoryColor = getCategoryColor(suggestion.category)

  return (
    <div
      className="
        neo-card
        bg-gradient-to-br from-[#fff8dc] to-[#ffe4b5]
        border-[var(--color-neo-border)]
        p-4
        relative
      "
    >
      {/* Header with suggestion badge and category */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="neo-badge bg-[var(--color-neo-pending)] text-[var(--color-neo-text)] text-xs">
            SUGGESTION
          </span>
          <span
            className="neo-badge text-xs"
            style={{ backgroundColor: categoryColor, color: 'white' }}
          >
            {suggestion.category}
          </span>
        </div>
      </div>

      {/* Feature Name */}
      <h3 className="font-display font-bold text-lg mb-2 text-[var(--color-neo-text)]">
        {suggestion.name}
      </h3>

      {/* Description */}
      <p className="text-sm text-[var(--color-neo-text)] mb-3 leading-relaxed">
        {suggestion.description}
      </p>

      {/* Steps */}
      {suggestion.steps.length > 0 && (
        <div className="mb-3">
          <h4 className="font-display font-bold text-sm mb-2 text-[var(--color-neo-text)]">
            Verification Steps:
          </h4>
          <ol className="space-y-1.5 text-sm text-[var(--color-neo-text)]">
            {suggestion.steps.map((step, index) => (
              <li key={index} className="flex gap-2">
                <span className="font-mono font-bold text-[var(--color-neo-text-secondary)] flex-shrink-0">
                  {index + 1}.
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Reasoning */}
      {suggestion.reasoning && (
        <div className="mb-4 p-3 bg-white/50 border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
          <div className="flex items-start gap-2">
            <Lightbulb
              size={16}
              className="text-[var(--color-neo-pending)] flex-shrink-0 mt-0.5"
            />
            <div>
              <h4 className="font-display font-bold text-xs mb-1 text-[var(--color-neo-text)]">
                REASONING
              </h4>
              <p className="text-xs text-[var(--color-neo-text-secondary)] leading-relaxed italic">
                {suggestion.reasoning}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onAccept}
          disabled={isCreating}
          className="
            flex-1
            neo-btn neo-btn-success
            py-2 px-4
            text-xs
            disabled:opacity-50 disabled:cursor-not-allowed
          "
          title="Accept and create feature"
        >
          {isCreating ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span>Creating...</span>
            </>
          ) : (
            <>
              <Check size={14} />
              <span>Create Feature</span>
            </>
          )}
        </button>
        <button
          onClick={onReject}
          disabled={isCreating}
          className="
            neo-btn
            bg-[var(--color-neo-bg)]
            text-[var(--color-neo-text)]
            py-2 px-4
            text-xs
            disabled:opacity-50 disabled:cursor-not-allowed
          "
          title="Dismiss suggestion"
        >
          <X size={14} />
          <span>Dismiss</span>
        </button>
      </div>
    </div>
  )
}
