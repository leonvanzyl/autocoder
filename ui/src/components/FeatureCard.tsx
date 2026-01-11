import { CheckCircle2, Circle, Loader2, Lock, GitBranch } from 'lucide-react'
import type { Feature } from '../lib/types'

interface FeatureCardProps {
  feature: Feature
  onClick: () => void
  isInProgress?: boolean
  showDependencies?: boolean
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

export function FeatureCard({ feature, onClick, isInProgress, showDependencies = true }: FeatureCardProps) {
  const categoryColor = getCategoryColor(feature.category)
  const isBlocked = feature.is_blocked === true
  const dependencyCount = feature.depends_on?.length ?? 0
  const blocksCount = feature.blocks?.length ?? 0

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left neo-card p-4 cursor-pointer
        ${isInProgress ? 'animate-pulse-neo' : ''}
        ${feature.passes ? 'border-[var(--color-neo-done)]' : ''}
        ${isBlocked ? 'border-red-500 opacity-75' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="neo-badge"
            style={{ backgroundColor: categoryColor, color: 'white' }}
          >
            {feature.category}
          </span>
          {isBlocked && (
            <span className="neo-badge bg-red-500 text-white flex items-center gap-1">
              <Lock size={12} />
              Blocked
            </span>
          )}
        </div>
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

      {/* Blocked Reason */}
      {isBlocked && feature.blocked_reason && (
        <div className="text-xs text-red-500 mb-2 p-2 bg-red-50 border border-red-200 rounded">
          {feature.blocked_reason}
        </div>
      )}

      {/* Dependency Info */}
      {showDependencies && (dependencyCount > 0 || blocksCount > 0) && (
        <div className="flex items-center gap-3 text-xs text-[var(--color-neo-text-secondary)] mb-2">
          {dependencyCount > 0 && (
            <span className="flex items-center gap-1" title={`Depends on ${dependencyCount} task(s)`}>
              <GitBranch size={12} className="rotate-180" />
              {dependencyCount} dep{dependencyCount > 1 ? 's' : ''}
            </span>
          )}
          {blocksCount > 0 && (
            <span className="flex items-center gap-1" title={`Blocks ${blocksCount} task(s)`}>
              <GitBranch size={12} />
              blocks {blocksCount}
            </span>
          )}
        </div>
      )}

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
        ) : isBlocked ? (
          <>
            <Lock size={16} className="text-red-500" />
            <span className="text-red-500 font-bold">Blocked</span>
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
