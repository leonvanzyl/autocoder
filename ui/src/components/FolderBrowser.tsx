/**
 * Folder Browser Component
 *
 * Server-side filesystem browser for selecting project directories.
 * Cross-platform support for Windows, macOS, and Linux.
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Folder,
  FolderOpen,
  ChevronRight,
  HardDrive,
  Loader2,
  AlertCircle,
  FolderPlus,
  ArrowLeft,
} from 'lucide-react'
import * as api from '../lib/api'
import type { DirectoryEntry, DriveInfo } from '../lib/types'

interface FolderBrowserProps {
  onSelect: (path: string) => void
  onCancel: () => void
  initialPath?: string
}

export function FolderBrowser({ onSelect, onCancel, initialPath }: FolderBrowserProps) {
  const [currentPath, setCurrentPath] = useState<string | undefined>(initialPath)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [isCreatingFolder, setIsCreatingFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [createError, setCreateError] = useState<string | null>(null)

  // Fetch directory listing
  const {
    data: directoryData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['filesystem', 'list', currentPath],
    queryFn: () => api.listDirectory(currentPath),
  })

  // Update selected path when directory changes
  useEffect(() => {
    if (directoryData?.current_path) {
      setSelectedPath(directoryData.current_path)
    }
  }, [directoryData?.current_path])

  const handleNavigate = (path: string) => {
    setCurrentPath(path)
    setSelectedPath(path)
    setIsCreatingFolder(false)
    setNewFolderName('')
    setCreateError(null)
  }

  const handleNavigateUp = () => {
    if (directoryData?.parent_path) {
      handleNavigate(directoryData.parent_path)
    }
  }

  const handleDriveSelect = (drive: DriveInfo) => {
    handleNavigate(`${drive.letter}:/`)
  }

  const handleEntryClick = (entry: DirectoryEntry) => {
    if (entry.is_directory) {
      handleNavigate(entry.path)
    }
  }

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      setCreateError('Folder name is required')
      return
    }

    // Basic validation
    if (!/^[a-zA-Z0-9_\-. ]+$/.test(newFolderName)) {
      setCreateError('Invalid folder name')
      return
    }

    const newPath = `${directoryData?.current_path}/${newFolderName.trim()}`

    try {
      await api.createDirectory(newPath)
      // Refresh the directory listing
      await refetch()
      // Navigate to the new folder
      handleNavigate(newPath)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create folder')
    }
  }

  const handleSelect = () => {
    if (selectedPath) {
      onSelect(selectedPath)
    }
  }

  // Parse breadcrumb segments from path
  const getBreadcrumbs = (path: string): { name: string; path: string }[] => {
    if (!path) return []

    const segments: { name: string; path: string }[] = []

    // Handle Windows drive letters
    if (/^[A-Za-z]:/.test(path)) {
      const drive = path.slice(0, 2)
      segments.push({ name: drive, path: `${drive}/` })
      path = path.slice(3)
    } else if (path.startsWith('/')) {
      segments.push({ name: '/', path: '/' })
      path = path.slice(1)
    }

    // Split remaining path
    const parts = path.split('/').filter(Boolean)
    let currentPath = segments.length > 0 ? segments[0].path : ''

    for (const part of parts) {
      currentPath = currentPath.endsWith('/') ? currentPath + part : currentPath + '/' + part
      segments.push({ name: part, path: currentPath })
    }

    return segments
  }

  const breadcrumbs = directoryData?.current_path ? getBreadcrumbs(directoryData.current_path) : []

  return (
    <div className="flex flex-col h-full max-h-[70vh]">
      {/* Header with breadcrumb navigation */}
      <div className="flex-shrink-0 p-4 border-b-3 border-[var(--color-neo-border)] bg-white">
        <div className="flex items-center gap-2 mb-3">
          <Folder size={20} className="text-[var(--color-neo-progress)]" />
          <span className="font-bold text-[#1a1a1a]">Select Project Folder</span>
        </div>

        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-1 flex-wrap text-sm">
          {directoryData?.parent_path && (
            <button
              onClick={handleNavigateUp}
              className="neo-btn neo-btn-ghost p-1"
              title="Go up"
            >
              <ArrowLeft size={16} />
            </button>
          )}

          {breadcrumbs.map((crumb, index) => (
            <div key={crumb.path} className="flex items-center">
              {index > 0 && <ChevronRight size={14} className="text-gray-400 mx-1" />}
              <button
                onClick={() => handleNavigate(crumb.path)}
                className={`
                  px-2 py-1 rounded text-[#1a1a1a]
                  hover:bg-[var(--color-neo-bg)]
                  ${index === breadcrumbs.length - 1 ? 'font-bold' : ''}
                `}
              >
                {crumb.name}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Drive selector (Windows only) */}
      {directoryData?.drives && directoryData.drives.length > 0 && (
        <div className="flex-shrink-0 p-3 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-[var(--color-neo-text-secondary)]">Drives:</span>
            {directoryData.drives.map((drive) => (
              <button
                key={drive.letter}
                onClick={() => handleDriveSelect(drive)}
                className={`
                  neo-btn neo-btn-ghost py-1 px-2 text-sm
                  flex items-center gap-1
                  ${currentPath?.startsWith(drive.letter) ? 'bg-[var(--color-neo-progress)] text-white' : ''}
                `}
              >
                <HardDrive size={14} />
                {drive.letter}: {drive.label && `(${drive.label})`}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Directory listing */}
      <div className="flex-1 overflow-y-auto p-2 bg-white">
        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 size={24} className="animate-spin text-[var(--color-neo-progress)]" />
          </div>
        ) : error ? (
          <div className="p-4 text-center">
            <AlertCircle size={32} className="mx-auto mb-2 text-[var(--color-neo-danger)]" />
            <p className="text-[var(--color-neo-danger)]">
              {error instanceof Error ? error.message : 'Failed to load directory'}
            </p>
            <button onClick={() => refetch()} className="neo-btn neo-btn-ghost mt-2">
              Retry
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-1">
            {/* Directory entries - only show directories */}
            {directoryData?.entries
              .filter((entry) => entry.is_directory)
              .map((entry) => (
                <button
                  key={entry.path}
                  onClick={() => handleEntryClick(entry)}
                  onDoubleClick={() => handleNavigate(entry.path)}
                  className={`
                    w-full text-left p-2 rounded
                    flex items-center gap-2
                    hover:bg-[var(--color-neo-bg)]
                    border-2 border-transparent
                    text-[var(--color-neo-text)]
                    ${selectedPath === entry.path ? 'bg-[var(--color-neo-progress)] bg-opacity-10 border-[var(--color-neo-progress)]' : ''}
                  `}
                >
                  {selectedPath === entry.path ? (
                    <FolderOpen size={18} className="text-[var(--color-neo-progress)] flex-shrink-0" />
                  ) : (
                    <Folder size={18} className="text-[var(--color-neo-pending)] flex-shrink-0" />
                  )}
                  <span className="truncate flex-1 text-[#1a1a1a]">{entry.name}</span>
                  {entry.has_children && (
                    <ChevronRight size={14} className="ml-auto text-gray-400 flex-shrink-0" />
                  )}
                </button>
              ))}

            {/* Empty state */}
            {directoryData?.entries.filter((e) => e.is_directory).length === 0 && (
              <div className="p-4 text-center text-[var(--color-neo-text-secondary)]">
                <Folder size={32} className="mx-auto mb-2 opacity-50" />
                <p>No subfolders</p>
                <p className="text-sm">You can create a new folder or select this directory.</p>
              </div>
            )}
          </div>
        )}

        {/* New folder creation */}
        {isCreatingFolder && (
          <div className="mt-2 p-3 bg-[var(--color-neo-bg)] border-2 border-[var(--color-neo-border)] rounded">
            <div className="flex items-center gap-2">
              <FolderPlus size={18} className="text-[var(--color-neo-progress)]" />
              <input
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="New folder name"
                className="neo-input flex-1 py-1"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateFolder()
                  if (e.key === 'Escape') {
                    setIsCreatingFolder(false)
                    setNewFolderName('')
                    setCreateError(null)
                  }
                }}
              />
              <button onClick={handleCreateFolder} className="neo-btn neo-btn-primary py-1 px-3">
                Create
              </button>
              <button
                onClick={() => {
                  setIsCreatingFolder(false)
                  setNewFolderName('')
                  setCreateError(null)
                }}
                className="neo-btn neo-btn-ghost py-1 px-2"
              >
                Cancel
              </button>
            </div>
            {createError && (
              <p className="text-sm text-[var(--color-neo-danger)] mt-1">{createError}</p>
            )}
          </div>
        )}
      </div>

      {/* Footer with selected path and actions */}
      <div className="flex-shrink-0 p-4 border-t-3 border-[var(--color-neo-border)] bg-white">
        {/* Selected path display */}
        <div className="mb-3 p-2 bg-[var(--color-neo-bg)] rounded border-2 border-[var(--color-neo-border)]">
          <div className="text-xs text-[#4a4a4a] mb-1">Selected path:</div>
          <div className="font-mono text-sm truncate text-[#1a1a1a]">{selectedPath || 'No folder selected'}</div>
          {selectedPath && (
            <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2 italic">
              This folder will contain all project files
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setIsCreatingFolder(true)}
            className="neo-btn neo-btn-ghost"
            disabled={isCreatingFolder}
          >
            <FolderPlus size={16} />
            New Folder
          </button>

          <div className="flex items-center gap-2">
            <button onClick={onCancel} className="neo-btn neo-btn-ghost">
              Cancel
            </button>
            <button
              onClick={handleSelect}
              className="neo-btn neo-btn-primary"
              disabled={!selectedPath}
            >
              Select This Folder
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
