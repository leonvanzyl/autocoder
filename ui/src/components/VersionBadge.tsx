import { useState, useEffect } from 'react'
import { Info, Sparkles } from 'lucide-react'

interface VersionInfo {
  version: string
  edition: string
  year: number
  major: number
  minor: number
  patch: number
  buildDate: string
  description: string
  fullVersion: string
  shortVersion: string
}

interface VersionBadgeProps {
  className?: string
}

/**
 * Simple version badge showing the current version
 */
export function VersionBadge({ className = '' }: VersionBadgeProps) {
  const [version, setVersion] = useState<VersionInfo | null>(null)

  useEffect(() => {
    fetch('/api/version')
      .then(res => res.json())
      .then(data => setVersion(data))
      .catch(err => console.error('Failed to fetch version:', err))
  }, [])

  if (!version) {
    return null
  }

  return (
    <span
      className={`text-xs text-muted-foreground ${className}`}
      title={version.fullVersion}
    >
      v{version.shortVersion}
    </span>
  )
}

interface VersionBadgeDetailedProps {
  className?: string
  showEdition?: boolean
}

/**
 * Detailed version badge with edition name and hover info
 */
export function VersionBadgeDetailed({ className = '', showEdition = true }: VersionBadgeDetailedProps) {
  const [version, setVersion] = useState<VersionInfo | null>(null)
  const [showTooltip, setShowTooltip] = useState(false)

  useEffect(() => {
    fetch('/api/version')
      .then(res => res.json())
      .then(data => setVersion(data))
      .catch(err => console.error('Failed to fetch version:', err))
  }, [])

  if (!version) {
    return null
  }

  return (
    <div
      className={`relative inline-flex items-center gap-1.5 ${className}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <Sparkles size={14} className="text-primary" />
      <span className="text-xs font-medium">
        v{version.version}
        {showEdition && (
          <span className="text-muted-foreground ml-1">
            - {version.edition}
          </span>
        )}
      </span>
      <Info size={12} className="text-muted-foreground cursor-help" />

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute bottom-full left-0 mb-2 w-64 p-3 bg-popover border-2 border-border rounded-lg shadow-lg z-50 animate-slide-in-up">
          <div className="space-y-2">
            <div className="font-semibold">{version.fullVersion}</div>
            <p className="text-xs text-muted-foreground">{version.description}</p>
            <div className="text-xs text-muted-foreground">
              Build: {version.buildDate}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VersionBadge
