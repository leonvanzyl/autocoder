import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import type { Feature } from '../lib/types'

interface FeatureCardProps {
  feature: Feature
  onClick: () => void
  isInProgress?: boolean
}

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

export function FeatureCard({ feature, onClick, isInProgress }: FeatureCardProps) {
  const categoryColor = getCategoryColor(feature.category)

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left neo-card p-4 cursor-pointer
        ${isInProgress ? 'animate-pulse-neo' : ''}
        ${feature.passes ? 'border-[var(--color-neo-done)]' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <span
          className="neo-badge"
          style={{ backgroundColor: categoryColor, color: 'white' }}
        >
          {feature.category}
        </span>
        <span className="font-mono text-sm text-[var(--color-neo-text-secondary)]">
          #{feature.priority}
        </span>
      </div>

      {/* Name */}
      <h3 className="font-display font-bold mb-1 line-clamp-2">
        {feature.name}
      </h3>

      {/* Description */}
      <p className="text-sm text-[var(--color-neo-text-secondary)] line-clamp-2 mb-3">
        {feature.description}
      </p>

      {/* Status */}
      <div className="flex items-center gap-2 text-sm">
        {isInProgress ? (
          <>
            <Loader2 size={16} className="animate-spin text-[var(--color-neo-progress)]" />
            <span className="text-[var(--color-neo-progress)] font-bold">Processing...</span>
          </>
        ) : feature.passes ? (
          <>
            <CheckCircle2 size={16} className="text-[var(--color-neo-done)]" />
            <span className="text-[var(--color-neo-done)] font-bold">Complete</span>
          </>
        ) : (
          <>
            <Circle size={16} className="text-[var(--color-neo-text-secondary)]" />
            <span className="text-[var(--color-neo-text-secondary)]">Pending</span>
          </>
        )}
      </div>
    </button>
  )
}
