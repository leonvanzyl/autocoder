import { KanbanColumn } from './KanbanColumn'
import type { Feature, FeatureListResponse } from '../lib/types'

interface KanbanBoardProps {
  features: FeatureListResponse | undefined
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
}

export function KanbanBoard({ features, onFeatureClick, onAddFeature, onExpandProject }: KanbanBoardProps) {
  const hasFeatures = features && (features.pending.length + features.in_progress.length + features.done.length) > 0

  if (!features) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {['Pending', 'In Progress', 'Done'].map(title => (
          <div key={title} className="neo-card p-4">
            <div className="h-8 bg-[var(--color-neo-bg)] animate-pulse mb-4" />
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-24 bg-[var(--color-neo-bg)] animate-pulse" />
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <KanbanColumn
        title="Pending"
        count={features.pending.length}
        features={features.pending}
        color="pending"
        onFeatureClick={onFeatureClick}
        onAddFeature={onAddFeature}
        onExpandProject={onExpandProject}
        showExpandButton={hasFeatures}
      />
      <KanbanColumn
        title="In Progress"
        count={features.in_progress.length}
        features={features.in_progress}
        color="progress"
        onFeatureClick={onFeatureClick}
      />
      <KanbanColumn
        title="Done"
        count={features.done.length}
        features={features.done}
        color="done"
        onFeatureClick={onFeatureClick}
      />
    </div>
  )
}
