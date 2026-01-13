/**
 * Assistant Quick Actions Component
 *
 * Provides quick action buttons for common assistant operations.
 * These can be clicked to send pre-formatted messages to the assistant.
 */

import {
  Play,
  Square,
  Pause,
  Plus,
  BarChart3,
  Zap,
  ArrowUpCircle,
  ListTodo,
  GitBranch,
  CheckCircle,
} from 'lucide-react'

export interface QuickAction {
  id: string
  label: string
  icon: React.ReactNode
  message: string
  variant?: 'default' | 'primary' | 'success' | 'warning'
}

interface AssistantQuickActionsProps {
  onActionClick: (message: string) => void
  disabled?: boolean
  agentStatus?: 'running' | 'paused' | 'stopped'
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: 'status',
    label: 'Project Status',
    icon: <BarChart3 size={14} />,
    message: "What's the current status of the project? Show me progress on phases and tasks.",
    variant: 'default',
  },
  {
    id: 'add-feature',
    label: 'Add Feature',
    icon: <Plus size={14} />,
    message: "I want to add a new feature to the project. Let's discuss what it should do.",
    variant: 'primary',
  },
  {
    id: 'start-agent',
    label: 'Start Agent',
    icon: <Play size={14} />,
    message: 'Start the coding agent to work on pending tasks.',
    variant: 'success',
  },
  {
    id: 'stop-agent',
    label: 'Stop Agent',
    icon: <Square size={14} />,
    message: 'Stop the coding agent.',
    variant: 'warning',
  },
  {
    id: 'pause-agent',
    label: 'Pause Agent',
    icon: <Pause size={14} />,
    message: 'Pause the coding agent so I can review progress.',
    variant: 'default',
  },
  {
    id: 'yolo-mode',
    label: 'YOLO Mode',
    icon: <Zap size={14} />,
    message: 'Start the agent in YOLO mode for rapid prototyping without browser tests.',
    variant: 'warning',
  },
  {
    id: 'next-task',
    label: 'Next Task',
    icon: <ListTodo size={14} />,
    message: "What's the next task that needs to be worked on?",
    variant: 'default',
  },
  {
    id: 'dependencies',
    label: 'Dependencies',
    icon: <GitBranch size={14} />,
    message: 'Are there any blocked tasks due to dependencies?',
    variant: 'default',
  },
  {
    id: 'migration',
    label: 'Migration',
    icon: <ArrowUpCircle size={14} />,
    message: 'Check if this project needs to be migrated to the v2 schema.',
    variant: 'default',
  },
  {
    id: 'submit-phase',
    label: 'Submit Phase',
    icon: <CheckCircle size={14} />,
    message: 'Is the current phase ready to be submitted for approval?',
    variant: 'success',
  },
]

export function AssistantQuickActions({
  onActionClick,
  disabled = false,
  agentStatus = 'stopped',
}: AssistantQuickActionsProps) {
  // Filter actions based on agent status
  const availableActions = QUICK_ACTIONS.filter((action) => {
    if (agentStatus === 'running') {
      return action.id !== 'start-agent' && action.id !== 'yolo-mode'
    } else if (agentStatus === 'paused') {
      return action.id !== 'pause-agent' && action.id !== 'yolo-mode'
    } else {
      return action.id !== 'stop-agent' && action.id !== 'pause-agent'
    }
  })

  const getVariantClasses = (variant: string = 'default') => {
    switch (variant) {
      case 'primary':
        return 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white border-transparent hover:from-indigo-400 hover:to-purple-400 shadow-lg shadow-indigo-500/20'
      case 'success':
        return 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white border-transparent hover:from-emerald-400 hover:to-teal-400 shadow-lg shadow-emerald-500/20'
      case 'warning':
        return 'bg-gradient-to-r from-amber-500 to-orange-500 text-white border-transparent hover:from-amber-400 hover:to-orange-400 shadow-lg shadow-amber-500/20'
      default:
        return 'bg-white/5 text-slate-300 border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20'
    }
  }

  return (
    <div className="px-4 py-3 border-b border-white/10 bg-[#16161d]">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          Quick Actions
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {availableActions.map((action) => (
          <button
            key={action.id}
            onClick={() => onActionClick(action.message)}
            disabled={disabled}
            className={`
              inline-flex items-center gap-1.5
              px-3 py-1.5
              text-xs font-medium
              border rounded-lg
              transition-all duration-200
              hover:scale-[1.02]
              active:scale-[0.98]
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
              ${getVariantClasses(action.variant)}
            `}
            title={action.message}
          >
            {action.icon}
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
