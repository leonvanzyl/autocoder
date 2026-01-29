import { useState, useEffect } from 'react'
import {
  Activity,
  DollarSign,
  Zap,
  TrendingUp,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { UsageSummary, DailyUsage, CostEstimate } from '../lib/types'
import * as api from '../lib/api'

interface UsageDashboardProps {
  projectName: string | null
  className?: string
}

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: typeof Activity
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
}

function StatCard({ title, value, subtitle, icon: Icon, trend, trendValue }: StatCardProps) {
  return (
    <div className="bg-card border-2 border-border rounded-lg p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subtitle && (
            <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
          )}
        </div>
        <div className="p-2 bg-primary/10 rounded-lg">
          <Icon size={20} className="text-primary" />
        </div>
      </div>
      {trend && trendValue && (
        <div className={`flex items-center gap-1 mt-2 text-xs ${
          trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-muted-foreground'
        }`}>
          {trend === 'up' ? <TrendingUp size={12} /> : trend === 'down' ? <ChevronDown size={12} /> : null}
          {trendValue}
        </div>
      )}
    </div>
  )
}

function formatCost(cost: number): string {
  if (cost < 0.01) return '<$0.01'
  if (cost < 1) return `$${cost.toFixed(2)}`
  return `$${cost.toFixed(2)}`
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`
  return String(tokens)
}

export function UsageDashboard({ projectName, className = '' }: UsageDashboardProps) {
  const [summary, setSummary] = useState<UsageSummary | null>(null)
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null)
  const [dailyUsage, setDailyUsage] = useState<DailyUsage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [days, setDays] = useState(30)

  const fetchData = async () => {
    if (!projectName) return

    setIsLoading(true)
    setError(null)

    try {
      const [summaryData, costData, dailyData] = await Promise.all([
        api.getUsageSummary(projectName, days),
        api.getCostEstimate(projectName, days),
        api.getDailyUsage(projectName, days),
      ])
      setSummary(summaryData)
      setCostEstimate(costData)
      setDailyUsage(dailyData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch usage data')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [projectName, days])

  if (!projectName) {
    return null
  }

  if (error) {
    return (
      <div className={`bg-card border-2 border-border rounded-lg p-4 ${className}`}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle size={16} />
          <span>Failed to load usage data</span>
        </div>
      </div>
    )
  }

  const totalTokens = summary ? summary.totals.inputTokens + summary.totals.outputTokens : 0

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={20} className="text-primary" />
          <h3 className="font-semibold">Usage Analytics</h3>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-sm bg-background border border-border rounded px-2 py-1"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchData}
            disabled={isLoading}
            className="h-8 w-8 p-0"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-8 w-8 p-0"
          >
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="Total Cost"
          value={formatCost(summary?.totals.cost ?? 0)}
          subtitle={`~${formatCost(costEstimate?.avgDailyCost ?? 0)}/day`}
          icon={DollarSign}
        />
        <StatCard
          title="API Calls"
          value={summary?.totals.calls ?? 0}
          subtitle={`${days} day period`}
          icon={Zap}
        />
        <StatCard
          title="Total Tokens"
          value={formatTokens(totalTokens)}
          subtitle={`${formatTokens(summary?.totals.inputTokens ?? 0)} in / ${formatTokens(summary?.totals.outputTokens ?? 0)} out`}
          icon={Activity}
        />
        <StatCard
          title="Success Rate"
          value={`${summary?.featureStats.successRate ?? 0}%`}
          subtitle={`${summary?.featureStats.successful ?? 0}/${summary?.featureStats.totalAttempts ?? 0} features`}
          icon={TrendingUp}
        />
      </div>

      {/* Expanded Details */}
      {isExpanded && summary && (
        <div className="space-y-4 mt-4">
          {/* Cost by Model */}
          <div className="bg-card border-2 border-border rounded-lg p-4">
            <h4 className="font-medium mb-3">Cost by Model</h4>
            <div className="space-y-2">
              {summary.byModel.map((model) => (
                <div key={model.modelId} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground truncate">{model.modelId}</span>
                  <div className="flex items-center gap-4">
                    <span>{model.calls} calls</span>
                    <span className="font-medium">{formatCost(model.cost)}</span>
                  </div>
                </div>
              ))}
              {summary.byModel.length === 0 && (
                <p className="text-sm text-muted-foreground">No usage data yet</p>
              )}
            </div>
          </div>

          {/* Cost by Agent Type */}
          <div className="bg-card border-2 border-border rounded-lg p-4">
            <h4 className="font-medium mb-3">Cost by Agent Type</h4>
            <div className="space-y-2">
              {summary.byAgentType.map((agent) => (
                <div key={agent.agentType} className="flex items-center justify-between text-sm">
                  <span className="capitalize text-muted-foreground">{agent.agentType}</span>
                  <div className="flex items-center gap-4">
                    <span>{agent.calls} calls</span>
                    <span className="font-medium">{formatCost(agent.cost)}</span>
                  </div>
                </div>
              ))}
              {summary.byAgentType.length === 0 && (
                <p className="text-sm text-muted-foreground">No usage data yet</p>
              )}
            </div>
          </div>

          {/* Daily Trend (simplified bar chart) */}
          {dailyUsage.length > 0 && (
            <div className="bg-card border-2 border-border rounded-lg p-4">
              <h4 className="font-medium mb-3">Daily Cost Trend</h4>
              <div className="flex items-end gap-1 h-24">
                {dailyUsage.slice(-14).map((day) => {
                  const maxCost = Math.max(...dailyUsage.map(d => d.cost), 0.01)
                  const height = (day.cost / maxCost) * 100
                  return (
                    <div
                      key={day.date}
                      className="flex-1 bg-primary/20 hover:bg-primary/40 transition-colors rounded-t"
                      style={{ height: `${Math.max(height, 2)}%` }}
                      title={`${day.date}: ${formatCost(day.cost)}`}
                    />
                  )
                })}
              </div>
              <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                <span>{dailyUsage[dailyUsage.length - 14]?.date ?? ''}</span>
                <span>{dailyUsage[dailyUsage.length - 1]?.date ?? ''}</span>
              </div>
            </div>
          )}

          {/* Projected Costs */}
          {costEstimate && (
            <div className="bg-card border-2 border-border rounded-lg p-4">
              <h4 className="font-medium mb-3 flex items-center gap-2">
                <Clock size={16} />
                Projected Monthly Cost
              </h4>
              <p className="text-3xl font-bold text-primary">
                {formatCost(costEstimate.projectedMonthlyCost)}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Based on {formatCost(costEstimate.avgDailyCost)} average daily cost
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default UsageDashboard
