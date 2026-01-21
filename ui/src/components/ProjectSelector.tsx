import { useState } from 'react'
import { ChevronDown, Plus, FolderOpen, Loader2, LayoutGrid, Settings } from 'lucide-react'
import type { ProjectSummary } from '../lib/types'

interface ProjectSelectorProps {
  projects: ProjectSummary[]
  selectedProject: string | null
  onSelectProject: (name: string | null) => void
  isLoading: boolean
  onNewProject?: () => void
  onManageProject?: (name: string) => void
}

export function ProjectSelector({
  projects,
  selectedProject,
  onSelectProject,
  isLoading,
  onNewProject,
  onManageProject,
}: ProjectSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)

  const selectedProjectData = projects.find(p => p.name === selectedProject)

  return (
    <div className="relative">
      {/* Dropdown Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="neo-btn bg-[var(--color-neo-card)] text-[var(--color-neo-text)] min-w-[200px] justify-between"
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 size={18} className="animate-spin" />
        ) : selectedProject ? (
          <>
            <span className="flex items-center gap-2">
              <FolderOpen size={18} />
              {selectedProject}
            </span>
            {selectedProjectData && selectedProjectData.stats.total > 0 && (
              <span className="neo-badge bg-[var(--color-neo-done)] ml-2">
                {selectedProjectData.stats.percentage}%
              </span>
            )}
          </>
        ) : (
          <span className="text-[var(--color-neo-text-secondary)]">
            Select Project
          </span>
        )}
        <ChevronDown size={18} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div className="absolute top-full left-0 mt-2 w-full neo-dropdown z-50 min-w-[280px]">
            {selectedProject && (
              <>
                <button
                  onClick={() => {
                    onSelectProject(null)
                    setIsOpen(false)
                  }}
                  className="w-full neo-dropdown-item flex items-center gap-2"
                >
                  <LayoutGrid size={16} />
                  Dashboard
                </button>
                <button
                  onClick={() => {
                    onManageProject?.(selectedProject)
                    setIsOpen(false)
                  }}
                  className="w-full neo-dropdown-item flex items-center gap-2"
                >
                  <Settings size={16} />
                  Manage Project
                </button>
                <div className="border-t-2 border-[var(--color-neo-border)]" />
              </>
            )}
            {projects.length > 0 ? (
              <div className="max-h-[300px] overflow-auto">
                {projects.map(project => (
                  <button
                    key={project.name}
                    onClick={() => {
                      onSelectProject(project.name)
                      setIsOpen(false)
                    }}
                    className={`w-full neo-dropdown-item flex items-center justify-between ${
                      project.name === selectedProject
                        ? 'bg-[var(--color-neo-pending)] text-[var(--color-neo-text-on-bright)]'
                        : ''
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <FolderOpen size={16} />
                      {project.name}
                    </span>
                    {project.stats.total > 0 && (
                      <span className="text-sm font-mono">
                        {project.stats.passing}/{project.stats.total}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            ) : (
              <div className="p-4 text-center text-[var(--color-neo-text-secondary)]">
                No projects yet
              </div>
            )}

            {/* Divider */}
            <div className="border-t-3 border-[var(--color-neo-border)]" />

            {/* Create New */}
            <button
              onClick={() => {
                onNewProject?.()
                setIsOpen(false)
              }}
              className="w-full neo-dropdown-item flex items-center gap-2 font-bold"
            >
              <Plus size={16} />
              New Project
            </button>
          </div>
        </>
      )}
    </div>
  )
}
