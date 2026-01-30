import { useState } from 'react'
import { Activity, ChevronLeft, X } from 'lucide-react'
import { ActivityFeed } from './ActivityFeed'
import { Button } from '@/components/ui/button'

const SIDEBAR_COLLAPSED_KEY = 'autocoder-activity-sidebar-collapsed'

interface ActivitySidebarProps {
  activities: Array<{
    agentName: string
    thought: string
    timestamp: string
    featureId: number
  }>
}

export function ActivitySidebar({ activities }: ActivitySidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
    } catch {
      return false
    }
  })

  const toggleCollapsed = () => {
    const newValue = !isCollapsed
    setIsCollapsed(newValue)
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(newValue))
    } catch {
      // localStorage not available
    }
  }

  // Don't render if no activities
  if (activities.length === 0) {
    return null
  }

  return (
    <>
      {/* Collapsed toggle button - on left edge */}
      {isCollapsed && (
        <button
          onClick={toggleCollapsed}
          className="fixed left-0 top-1/2 -translate-y-1/2 z-40 bg-primary text-primary-foreground p-2 rounded-r-lg shadow-lg hover:bg-primary/90 transition-colors"
          title="Show Activity"
        >
          <Activity size={20} />
          {activities.length > 0 && (
            <span className="absolute -top-1 -right-1 bg-destructive text-destructive-foreground text-xs w-5 h-5 rounded-full flex items-center justify-center font-bold">
              {activities.length > 9 ? '9+' : activities.length}
            </span>
          )}
        </button>
      )}

      {/* Sidebar panel - positioned on left */}
      <div
        className={`
          fixed left-0 top-0 h-full z-40 bg-card border-r-2 border-border shadow-xl
          transition-transform duration-300 ease-out
          ${isCollapsed ? '-translate-x-full' : 'translate-x-0'}
        `}
        style={{ width: '320px' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-border bg-muted/50">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-primary" />
            <span className="font-semibold text-sm uppercase tracking-wide">
              Activity
            </span>
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {activities.length}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleCollapsed}
            className="h-7 w-7 p-0"
            title="Hide Activity"
          >
            <X size={16} />
          </Button>
        </div>

        {/* Activity list - scrollable */}
        <div className="h-[calc(100%-49px)] overflow-y-auto p-3">
          <ActivityFeed activities={activities} maxItems={50} showHeader={false} />
        </div>

        {/* Collapse tab on the right edge */}
        <button
          onClick={toggleCollapsed}
          className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-full bg-card border-2 border-l-0 border-border p-1.5 rounded-r-lg hover:bg-muted transition-colors"
          title="Hide Activity"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* Overlay for mobile */}
      {!isCollapsed && (
        <div
          className="fixed inset-0 bg-black/20 z-30 lg:hidden"
          onClick={toggleCollapsed}
        />
      )}
    </>
  )
}
