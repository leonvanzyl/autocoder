import { useState, useEffect } from 'react'
import {
  Rocket,
  Cloud,
  Check,
  X,
  Clock,
  RefreshCw,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  ExternalLink,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import type {
  Deployment,
  DeploymentEnvironment,
  DeploymentStatus,
  DeploymentStrategy,
  EnvironmentStatusResponse,
} from '../lib/types'
import * as api from '../lib/api'

interface DeployPanelProps {
  projectName: string | null
  className?: string
}

const ENVIRONMENTS: { id: DeploymentEnvironment; name: string; color: string }[] = [
  { id: 'development', name: 'Dev', color: 'bg-blue-500/20 text-blue-600' },
  { id: 'staging', name: 'Staging', color: 'bg-yellow-500/20 text-yellow-600' },
  { id: 'production', name: 'Prod', color: 'bg-green-500/20 text-green-600' },
  { id: 'preview', name: 'Preview', color: 'bg-purple-500/20 text-purple-600' },
]

const STRATEGIES: { id: DeploymentStrategy; name: string }[] = [
  { id: 'direct', name: 'Direct' },
  { id: 'blue_green', name: 'Blue/Green' },
  { id: 'canary', name: 'Canary' },
  { id: 'rolling', name: 'Rolling' },
]

function StatusBadge({ status }: { status: DeploymentStatus | string }) {
  const statusConfig: Record<string, { color: string; icon: typeof Check }> = {
    pending: { color: 'bg-gray-500/20 text-gray-600', icon: Clock },
    in_progress: { color: 'bg-blue-500/20 text-blue-600', icon: RefreshCw },
    success: { color: 'bg-green-500/20 text-green-600', icon: Check },
    failed: { color: 'bg-red-500/20 text-red-600', icon: X },
    rolled_back: { color: 'bg-orange-500/20 text-orange-600', icon: ArrowLeft },
    cancelled: { color: 'bg-gray-500/20 text-gray-600', icon: X },
    never_deployed: { color: 'bg-gray-500/20 text-gray-600', icon: Cloud },
  }

  const config = statusConfig[status] || statusConfig.pending
  const Icon = config.icon

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.color}`}>
      <Icon size={12} className={status === 'in_progress' ? 'animate-spin' : ''} />
      {status.replace('_', ' ')}
    </span>
  )
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Unknown'
  const date = new Date(dateStr)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function DeployPanel({ projectName, className = '' }: DeployPanelProps) {
  const [envStatus, setEnvStatus] = useState<EnvironmentStatusResponse | null>(null)
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isDeploying, setIsDeploying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showDeployForm, setShowDeployForm] = useState(false)

  // Deploy form state
  const [deployEnv, setDeployEnv] = useState<DeploymentEnvironment>('development')
  const [deployStrategy, setDeployStrategy] = useState<DeploymentStrategy>('direct')
  const [deployCommand, setDeployCommand] = useState('')

  const fetchData = async () => {
    if (!projectName) return

    setIsLoading(true)
    setError(null)

    try {
      const [envData, deploymentsData] = await Promise.all([
        api.getEnvironmentStatus(projectName),
        api.listDeployments(projectName).catch(() => ({ deployments: [] })),
      ])
      setEnvStatus(envData)
      setDeployments(deploymentsData.deployments)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch deployment data')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [projectName])

  const handleDeploy = async () => {
    if (!projectName) return

    setIsDeploying(true)
    setError(null)

    try {
      const result = await api.startDeployment(projectName, {
        environment: deployEnv,
        strategy: deployStrategy,
        deploy_command: deployCommand || undefined,
      })

      if (result.success) {
        setShowDeployForm(false)
        setDeployCommand('')
        await fetchData()
      } else {
        setError(result.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deployment failed')
    } finally {
      setIsDeploying(false)
    }
  }

  const handleRollback = async (deploymentId: number) => {
    if (!projectName) return

    try {
      const result = await api.rollbackDeployment(projectName, deploymentId)
      if (result.success) {
        await fetchData()
      } else {
        setError(result.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rollback failed')
    }
  }

  if (!projectName) {
    return null
  }

  return (
    <div className={`bg-card border-2 border-border rounded-lg ${className}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <Rocket size={18} className="text-primary" />
          <span className="font-medium">Deployments</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation()
              fetchData()
            }}
            disabled={isLoading}
            className="h-7 w-7 p-0"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </Button>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-border p-3 space-y-4">
          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {/* Environment Status Grid */}
          {envStatus && (
            <div className="grid grid-cols-2 gap-2">
              {ENVIRONMENTS.map((env) => {
                const status = envStatus[env.id]
                return (
                  <div
                    key={env.id}
                    className="p-2 bg-muted/50 rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${env.color}`}>
                        {env.name}
                      </span>
                      {status && <StatusBadge status={status.status} />}
                    </div>
                    {status?.latestDeployment && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {status.latestDeployment.commitSha?.slice(0, 7) || 'No commit'}
                        {' • '}
                        {formatDate(status.latestDeployment.completedAt)}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Deploy Button or Form */}
          {!showDeployForm ? (
            <Button
              size="sm"
              onClick={() => setShowDeployForm(true)}
              className="w-full gap-2"
            >
              <Rocket size={14} />
              New Deployment
            </Button>
          ) : (
            <div className="space-y-3 p-3 bg-muted/30 rounded-lg">
              <div className="space-y-1.5">
                <Label className="text-xs">Environment</Label>
                <div className="grid grid-cols-4 gap-1">
                  {ENVIRONMENTS.map((env) => (
                    <button
                      key={env.id}
                      onClick={() => setDeployEnv(env.id)}
                      className={`py-1.5 px-2 text-xs font-medium rounded border transition-colors ${
                        deployEnv === env.id
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'bg-background border-border hover:border-primary/50'
                      }`}
                    >
                      {env.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">Strategy</Label>
                <div className="grid grid-cols-2 gap-1">
                  {STRATEGIES.map((strategy) => (
                    <button
                      key={strategy.id}
                      onClick={() => setDeployStrategy(strategy.id)}
                      className={`py-1.5 px-2 text-xs font-medium rounded border transition-colors ${
                        deployStrategy === strategy.id
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'bg-background border-border hover:border-primary/50'
                      }`}
                    >
                      {strategy.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">Deploy Command (optional)</Label>
                <input
                  type="text"
                  value={deployCommand}
                  onChange={(e) => setDeployCommand(e.target.value)}
                  placeholder="npm run deploy"
                  className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded"
                />
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeployForm(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleDeploy}
                  disabled={isDeploying}
                  className="flex-1"
                >
                  {isDeploying ? 'Deploying...' : 'Deploy'}
                </Button>
              </div>
            </div>
          )}

          {/* Recent Deployments */}
          {deployments.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Recent Deployments</h4>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {deployments.slice(0, 5).map((deployment) => (
                  <div
                    key={deployment.id}
                    className="p-2 bg-muted/30 rounded-lg text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">#{deployment.id}</span>
                        <StatusBadge status={deployment.status} />
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {deployment.environment}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-1 text-xs text-muted-foreground">
                      <span>
                        {deployment.branch || 'unknown'} • {deployment.commitSha?.slice(0, 7) || 'no commit'}
                      </span>
                      <div className="flex items-center gap-2">
                        {deployment.deployUrl && (
                          <a
                            href={deployment.deployUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline flex items-center gap-1"
                          >
                            View <ExternalLink size={10} />
                          </a>
                        )}
                        {deployment.status === 'success' && (
                          <button
                            onClick={() => handleRollback(deployment.id)}
                            className="text-orange-500 hover:underline"
                          >
                            Rollback
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DeployPanel
