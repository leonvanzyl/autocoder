import { FeatureCard } from './FeatureCard'
import { Plus, Sparkles, Wand2 } from 'lucide-react'
import type { Feature, ActiveAgent } from '../lib/types'

interface KanbanColumnProps {
  title: string
  count: number
  features: Feature[]
  allFeatures?: Feature[]  // For dependency status calculation
  activeAgents?: ActiveAgent[]  // Active agents for showing which agent is working on a feature
  color: 'pending' | 'progress' | 'done'
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  showExpandButton?: boolean
  onCreateSpec?: () => void  // Callback to start spec creation
  showCreateSpec?: boolean   // Show "Create Spec" button when project has no spec
}

const colorMap = {
  pending: 'kanban-header-pending',
  progress: 'kanban-header-progress',
  done: 'kanban-header-done',
}

export function KanbanColumn({
  title,
  count,
  features,
  allFeatures = [],
  activeAgents = [],
  color,
  onFeatureClick,
  onAddFeature,
  onExpandProject,
  showExpandButton,
  onCreateSpec,
  showCreateSpec,
}: KanbanColumnProps) {
  // Create a map of feature ID to active agent for quick lookup
  const agentByFeatureId = new Map(
    activeAgents.map(agent => [agent.featureId, agent])
  )
  return (
    <div
      className={`neo-card overflow-hidden kanban-column ${colorMap[color]}`}
    >
      {/* Header */}
      <div
        className="kanban-header px-4 py-3 border-b border-[var(--color-neo-border)]"
      >
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold flex items-center gap-2 text-[var(--color-neo-text)]">
            {title}
            <span className="neo-badge bg-[var(--color-neo-neutral-100)] text-[var(--color-neo-text-secondary)]">{count}</span>
          </h2>
          {(onAddFeature || onExpandProject) && (
            <div className="flex items-center gap-2">
              {onAddFeature && (
                <button
                  onClick={onAddFeature}
                  className="neo-btn neo-btn-primary text-sm py-1.5 px-2"
                  title="Add new feature (N)"
                >
                  <Plus size={16} />
                </button>
              )}
              {onExpandProject && showExpandButton && (
                <button
                  onClick={onExpandProject}
                  className="neo-btn bg-[var(--color-neo-progress)] text-[var(--color-neo-text-on-bright)] text-sm py-1.5 px-2"
                  title="Expand project with AI (E)"
                >
                  <Sparkles size={16} />
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Cards */}
      <div className="p-4 space-y-3 max-h-[600px] overflow-y-auto bg-[var(--color-neo-bg)]">
        {features.length === 0 ? (
          <div className="text-center py-8 text-[var(--color-neo-text-secondary)]">
            {showCreateSpec && onCreateSpec ? (
              <div className="space-y-4">
                <p>No spec created yet</p>
                <button
                  onClick={onCreateSpec}
                  className="neo-btn neo-btn-primary inline-flex items-center gap-2"
                >
                  <Wand2 size={18} />
                  Create Spec with AI
                </button>
              </div>
            ) : (
              'No features'
            )}
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
                allFeatures={allFeatures}
                activeAgent={agentByFeatureId.get(feature.id)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  )
}
