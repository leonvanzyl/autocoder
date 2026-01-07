import { Wifi, WifiOff } from 'lucide-react'

interface ProgressDashboardProps {
  passing: number
  total: number
  percentage: number
  isConnected: boolean
}

export function ProgressDashboard({
  passing,
  total,
  percentage,
  isConnected,
}: ProgressDashboardProps) {
  return (
    <div className="neo-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-xl font-bold uppercase">
          Progress
        </h2>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <Wifi size={16} className="text-[var(--color-neo-done)]" />
              <span className="text-sm text-[var(--color-neo-done)]">Live</span>
            </>
          ) : (
            <>
              <WifiOff size={16} className="text-[var(--color-neo-danger)]" />
              <span className="text-sm text-[var(--color-neo-danger)]">Offline</span>
            </>
          )}
        </div>
      </div>

      {/* Large Percentage */}
      <div className="text-center mb-6">
        <span className="font-display text-6xl font-bold">
          {percentage.toFixed(1)}
        </span>
        <span className="font-display text-3xl font-bold text-[var(--color-neo-text-secondary)]">
          %
        </span>
      </div>

      {/* Progress Bar */}
      <div className="neo-progress mb-4">
        <div
          className="neo-progress-fill"
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Stats */}
      <div className="flex justify-center gap-8 text-center">
        <div>
          <span className="font-mono text-3xl font-bold text-[var(--color-neo-done)]">
            {passing}
          </span>
          <span className="block text-sm text-[var(--color-neo-text-secondary)] uppercase">
            Passing
          </span>
        </div>
        <div className="text-4xl text-[var(--color-neo-text-secondary)]">/</div>
        <div>
          <span className="font-mono text-3xl font-bold">
            {total}
          </span>
          <span className="block text-sm text-[var(--color-neo-text-secondary)] uppercase">
            Total
          </span>
        </div>
      </div>
    </div>
  )
}
