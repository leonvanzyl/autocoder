import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { useEnqueueFeatures } from '../hooks/useProjects'

export function StagedBacklogPanel({
  projectName,
  stagedCount,
}: {
  projectName: string
  stagedCount: number
}) {
  const enqueue = useEnqueueFeatures(projectName)
  const [count, setCount] = useState(10)

  const safeCount = Math.max(1, Math.min(10000, Math.trunc(Number.isFinite(count) ? count : 1)))

  return (
    <div className="neo-card p-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="font-display font-bold uppercase">Staged Backlog</div>
          <div className="text-sm text-[var(--color-neo-text-secondary)]">
            {stagedCount} features are staged. Enqueue a batch to keep the run focused.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            max={10000}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="neo-input w-24"
          />
          <button
            className="neo-btn neo-btn-primary text-sm"
            disabled={enqueue.isPending}
            onClick={() => enqueue.mutate(safeCount)}
            title="Enable next staged features"
          >
            {enqueue.isPending ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
            Enqueue
          </button>
        </div>
      </div>
    </div>
  )
}
