import { FeatureCard } from './FeatureCard'
import type { Feature } from '../lib/types'

interface KanbanColumnProps {
  title: string
  count: number
  features: Feature[]
  color: 'pending' | 'progress' | 'done'
  onFeatureClick: (feature: Feature) => void
}

const colorMap = {
  pending: 'var(--color-neo-pending)',
  progress: 'var(--color-neo-progress)',
  done: 'var(--color-neo-done)',
}

export function KanbanColumn({
  title,
  count,
  features,
  color,
  onFeatureClick,
}: KanbanColumnProps) {
  return (
    <div
      className="neo-card overflow-hidden"
      style={{ borderColor: colorMap[color] }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b-3 border-[var(--color-neo-border)]"
        style={{ backgroundColor: colorMap[color] }}
      >
        <h2 className="font-display text-lg font-bold uppercase flex items-center justify-between text-[var(--color-neo-text)]">
          {title}
          <span className="neo-badge bg-white text-[var(--color-neo-text)]">{count}</span>
        </h2>
      </div>

      {/* Cards */}
      <div className="p-4 space-y-3 max-h-[600px] overflow-y-auto bg-[var(--color-neo-bg)]">
        {features.length === 0 ? (
          <div className="text-center py-8 text-[var(--color-neo-text-secondary)]">
            No features
          </div>
        ) : (
          features.map((feature, index) => (
            <div
              key={feature.id}
              className="animate-slide-in"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <FeatureCard
                feature={feature}
                onClick={() => onFeatureClick(feature)}
                isInProgress={color === 'progress'}
              />
            </div>
          ))
        )}
      </div>
    </div>
  )
}
