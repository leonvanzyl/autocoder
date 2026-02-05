import { KanbanColumn } from './KanbanColumn'
import type { Feature, FeatureListResponse, ActiveAgent } from '../lib/types'
import { Card, CardContent } from '@/components/ui/card'

interface KanbanBoardProps {
  features: FeatureListResponse | undefined
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  activeAgents?: ActiveAgent[]
  onCreateSpec?: () => void
  hasSpec?: boolean
}

export function KanbanBoard({ features, onFeatureClick, onAddFeature, onExpandProject, activeAgents = [], onCreateSpec, hasSpec = true }: KanbanBoardProps) {
  const hasFeatures = features && (features.pending.length + features.in_progress.length + features.done.length) > 0

  // Combine all features for dependency status calculation
  const allFeatures = features
    ? [...features.pending, ...features.in_progress, ...features.done]
    : []

  if (!features) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {['Pending', 'In Progress', 'Done'].map(title => (
          <Card key={title} className="py-4">
            <CardContent className="p-4">
              <div className="h-8 bg-muted animate-pulse rounded mb-4" />
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-24 bg-muted animate-pulse rounded" />
                ))}
              </div>
            </CardContent>
          </Card>
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
        allFeatures={allFeatures}
        activeAgents={activeAgents}
        color="pending"
        onFeatureClick={onFeatureClick}
        onAddFeature={onAddFeature}
        onExpandProject={onExpandProject}
        showExpandButton={hasFeatures && hasSpec}
        onCreateSpec={onCreateSpec}
        showCreateSpec={!hasSpec && !hasFeatures}
      />
      <KanbanColumn
        title="In Progress"
        count={features.in_progress.length}
        features={features.in_progress}
        allFeatures={allFeatures}
        activeAgents={activeAgents}
        color="progress"
        onFeatureClick={onFeatureClick}
      />
      <KanbanColumn
        title="Done"
        count={features.done.length}
        features={features.done}
        allFeatures={allFeatures}
        activeAgents={activeAgents}
        color="done"
        onFeatureClick={onFeatureClick}
      />
    </div>
  )
}
