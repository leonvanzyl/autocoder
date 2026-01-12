/**
 * Debug Log Viewer Component
 *
 * Collapsible panel at the bottom of the screen showing real-time
 * agent output (tool calls, results, steps). Similar to browser DevTools.
 * Features a resizable height via drag handle and tabs for different log sources.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { ChevronUp, ChevronDown, Trash2, Terminal as TerminalIcon, GripHorizontal, Cpu, Server } from 'lucide-react'
import { Terminal } from './Terminal'
import { TerminalTabs } from './TerminalTabs'
import { listTerminals, createTerminal, renameTerminal, deleteTerminal } from '@/lib/api'
import type { TerminalInfo } from '@/lib/types'

const MIN_HEIGHT = 150
const MAX_HEIGHT = 600
const DEFAULT_HEIGHT = 288
const STORAGE_KEY = 'debug-panel-height'
const TAB_STORAGE_KEY = 'debug-panel-tab'

type TabType = 'agent' | 'devserver' | 'terminal'

interface DebugLogViewerProps {
  logs: Array<{ line: string; timestamp: string }>
  devLogs: Array<{ line: string; timestamp: string }>
  isOpen: boolean
  onToggle: () => void
  onClear: () => void
  onClearDevLogs: () => void
  onHeightChange?: (height: number) => void
  projectName: string
  activeTab?: TabType
  onTabChange?: (tab: TabType) => void
}

type LogLevel = 'error' | 'warn' | 'debug' | 'info'

export function DebugLogViewer({
  logs,
  devLogs,
  isOpen,
  onToggle,
  onClear,
  onClearDevLogs,
  onHeightChange,
  projectName,
  activeTab: controlledActiveTab,
  onTabChange,
}: DebugLogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const devScrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [devAutoScroll, setDevAutoScroll] = useState(true)
  const [isResizing, setIsResizing] = useState(false)
  const [panelHeight, setPanelHeight] = useState(() => {
    // Load saved height from localStorage
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? Math.min(Math.max(parseInt(saved, 10), MIN_HEIGHT), MAX_HEIGHT) : DEFAULT_HEIGHT
  })
  const [internalActiveTab, setInternalActiveTab] = useState<TabType>(() => {
    // Load saved tab from localStorage
    const saved = localStorage.getItem(TAB_STORAGE_KEY)
    return (saved as TabType) || 'agent'
  })

  // Terminal management state
  const [terminals, setTerminals] = useState<TerminalInfo[]>([])
  const [activeTerminalId, setActiveTerminalId] = useState<string | null>(null)
  const [isLoadingTerminals, setIsLoadingTerminals] = useState(false)

  // Use controlled tab if provided, otherwise use internal state
  const activeTab = controlledActiveTab ?? internalActiveTab
  const setActiveTab = (tab: TabType) => {
    setInternalActiveTab(tab)
    localStorage.setItem(TAB_STORAGE_KEY, tab)
    onTabChange?.(tab)
  }

  // Fetch terminals for the project
  const fetchTerminals = useCallback(async () => {
    if (!projectName) return

    setIsLoadingTerminals(true)
    try {
      const terminalList = await listTerminals(projectName)
      setTerminals(terminalList)

      // Set active terminal to first one if not set or current one doesn't exist
      if (terminalList.length > 0) {
        if (!activeTerminalId || !terminalList.find((t) => t.id === activeTerminalId)) {
          setActiveTerminalId(terminalList[0].id)
        }
      }
    } catch (err) {
      console.error('Failed to fetch terminals:', err)
    } finally {
      setIsLoadingTerminals(false)
    }
  }, [projectName, activeTerminalId])

  // Handle creating a new terminal
  const handleCreateTerminal = useCallback(async () => {
    if (!projectName) return

    try {
      const newTerminal = await createTerminal(projectName)
      setTerminals((prev) => [...prev, newTerminal])
      setActiveTerminalId(newTerminal.id)
    } catch (err) {
      console.error('Failed to create terminal:', err)
    }
  }, [projectName])

  // Handle renaming a terminal
  const handleRenameTerminal = useCallback(
    async (terminalId: string, newName: string) => {
      if (!projectName) return

      try {
        const updated = await renameTerminal(projectName, terminalId, newName)
        setTerminals((prev) =>
          prev.map((t) => (t.id === terminalId ? updated : t))
        )
      } catch (err) {
        console.error('Failed to rename terminal:', err)
      }
    },
    [projectName]
  )

  // Handle closing a terminal
  const handleCloseTerminal = useCallback(
    async (terminalId: string) => {
      if (!projectName || terminals.length <= 1) return

      try {
        await deleteTerminal(projectName, terminalId)
        setTerminals((prev) => prev.filter((t) => t.id !== terminalId))

        // If we closed the active terminal, switch to another one
        if (activeTerminalId === terminalId) {
          const remaining = terminals.filter((t) => t.id !== terminalId)
          if (remaining.length > 0) {
            setActiveTerminalId(remaining[0].id)
          }
        }
      } catch (err) {
        console.error('Failed to close terminal:', err)
      }
    },
    [projectName, terminals, activeTerminalId]
  )

  // Fetch terminals when project changes
  useEffect(() => {
    if (projectName) {
      fetchTerminals()
    } else {
      setTerminals([])
      setActiveTerminalId(null)
    }
  }, [projectName]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll to bottom when new agent logs arrive (if user hasn't scrolled up)
  useEffect(() => {
    if (autoScroll && scrollRef.current && isOpen && activeTab === 'agent') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll, isOpen, activeTab])

  // Auto-scroll to bottom when new dev logs arrive (if user hasn't scrolled up)
  useEffect(() => {
    if (devAutoScroll && devScrollRef.current && isOpen && activeTab === 'devserver') {
      devScrollRef.current.scrollTop = devScrollRef.current.scrollHeight
    }
  }, [devLogs, devAutoScroll, isOpen, activeTab])

  // Notify parent of height changes
  useEffect(() => {
    if (onHeightChange && isOpen) {
      onHeightChange(panelHeight)
    }
  }, [panelHeight, isOpen, onHeightChange])

  // Handle mouse move during resize
  const handleMouseMove = useCallback((e: MouseEvent) => {
    const newHeight = window.innerHeight - e.clientY
    const clampedHeight = Math.min(Math.max(newHeight, MIN_HEIGHT), MAX_HEIGHT)
    setPanelHeight(clampedHeight)
  }, [])

  // Handle mouse up to stop resizing
  const handleMouseUp = useCallback(() => {
    setIsResizing(false)
    // Save to localStorage
    localStorage.setItem(STORAGE_KEY, panelHeight.toString())
  }, [panelHeight])

  // Set up global mouse event listeners during resize
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'ns-resize'
      document.body.style.userSelect = 'none'
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isResizing, handleMouseMove, handleMouseUp])

  // Start resizing
  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsResizing(true)
  }

  // Detect if user scrolled up (agent logs)
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 50
    setAutoScroll(isAtBottom)
  }

  // Detect if user scrolled up (dev logs)
  const handleDevScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 50
    setDevAutoScroll(isAtBottom)
  }

  // Handle clear button based on active tab
  const handleClear = () => {
    if (activeTab === 'agent') {
      onClear()
    } else if (activeTab === 'devserver') {
      onClearDevLogs()
    }
    // Terminal has no clear button (it's managed internally)
  }

  // Get the current log count based on active tab
  const getCurrentLogCount = () => {
    if (activeTab === 'agent') return logs.length
    if (activeTab === 'devserver') return devLogs.length
    return 0
  }

  // Check if current tab has auto-scroll paused
  const isAutoScrollPaused = () => {
    if (activeTab === 'agent') return !autoScroll
    if (activeTab === 'devserver') return !devAutoScroll
    return false
  }

  // Parse log level from line content
  const getLogLevel = (line: string): LogLevel => {
    const lowerLine = line.toLowerCase()
    if (lowerLine.includes('error') || lowerLine.includes('exception') || lowerLine.includes('traceback')) {
      return 'error'
    }
    if (lowerLine.includes('warn') || lowerLine.includes('warning')) {
      return 'warn'
    }
    if (lowerLine.includes('debug')) {
      return 'debug'
    }
    return 'info'
  }

  // Get color class for log level
  const getLogColor = (level: LogLevel): string => {
    switch (level) {
      case 'error':
        return 'text-red-400'
      case 'warn':
        return 'text-yellow-400'
      case 'debug':
        return 'text-gray-400'
      case 'info':
      default:
        return 'text-green-400'
    }
  }

  // Format timestamp to HH:MM:SS
  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return ''
    }
  }

  return (
    <div
      className={`fixed bottom-0 left-0 right-0 z-40 ${
        isResizing ? '' : 'transition-all duration-200'
      }`}
      style={{ height: isOpen ? panelHeight : 40 }}
    >
      {/* Resize handle - only visible when open */}
      {isOpen && (
        <div
          className="absolute top-0 left-0 right-0 h-2 cursor-ns-resize group flex items-center justify-center -translate-y-1/2 z-50"
          onMouseDown={handleResizeStart}
        >
          <div className="w-16 h-1.5 bg-[#333] rounded-full group-hover:bg-[#555] transition-colors flex items-center justify-center">
            <GripHorizontal size={12} className="text-gray-500 group-hover:text-gray-400" />
          </div>
        </div>
      )}

      {/* Header bar */}
      <div
        className="flex items-center justify-between h-10 px-4 bg-[#1a1a1a] border-t-3 border-black"
      >
        <div className="flex items-center gap-2">
          {/* Collapse/expand toggle */}
          <button
            onClick={onToggle}
            className="flex items-center gap-2 hover:bg-[#333] px-2 py-1 rounded transition-colors cursor-pointer"
          >
            <TerminalIcon size={16} className="text-green-400" />
            <span className="font-mono text-sm text-white font-bold">
              Debug
            </span>
            <span className="px-1.5 py-0.5 text-xs font-mono bg-[#333] text-gray-500 rounded" title="Toggle debug panel">
              D
            </span>
          </button>

          {/* Tabs - only visible when open */}
          {isOpen && (
            <div className="flex items-center gap-1 ml-4">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setActiveTab('agent')
                }}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded transition-colors ${
                  activeTab === 'agent'
                    ? 'bg-[#333] text-white'
                    : 'text-gray-400 hover:text-white hover:bg-[#2a2a2a]'
                }`}
              >
                <Cpu size={12} />
                Agent
                {logs.length > 0 && (
                  <span className="px-1.5 py-0.5 text-[10px] bg-[#444] rounded">
                    {logs.length}
                  </span>
                )}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setActiveTab('devserver')
                }}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded transition-colors ${
                  activeTab === 'devserver'
                    ? 'bg-[#333] text-white'
                    : 'text-gray-400 hover:text-white hover:bg-[#2a2a2a]'
                }`}
              >
                <Server size={12} />
                Dev Server
                {devLogs.length > 0 && (
                  <span className="px-1.5 py-0.5 text-[10px] bg-[#444] rounded">
                    {devLogs.length}
                  </span>
                )}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setActiveTab('terminal')
                }}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded transition-colors ${
                  activeTab === 'terminal'
                    ? 'bg-[#333] text-white'
                    : 'text-gray-400 hover:text-white hover:bg-[#2a2a2a]'
                }`}
              >
                <TerminalIcon size={12} />
                Terminal
                <span className="px-1.5 py-0.5 text-[10px] bg-[#444] text-gray-500 rounded" title="Toggle terminal">
                  T
                </span>
              </button>
            </div>
          )}

          {/* Log count and status - only for log tabs */}
          {isOpen && activeTab !== 'terminal' && (
            <>
              {getCurrentLogCount() > 0 && (
                <span className="px-2 py-0.5 text-xs font-mono bg-[#333] text-gray-300 rounded ml-2">
                  {getCurrentLogCount()}
                </span>
              )}
              {isAutoScrollPaused() && (
                <span className="px-2 py-0.5 text-xs font-mono bg-yellow-600 text-white rounded">
                  Paused
                </span>
              )}
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Clear button - only for log tabs */}
          {isOpen && activeTab !== 'terminal' && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleClear()
              }}
              className="p-1.5 hover:bg-[#333] rounded transition-colors"
              title="Clear logs"
            >
              <Trash2 size={14} className="text-gray-400" />
            </button>
          )}
          <div className="p-1">
            {isOpen ? (
              <ChevronDown size={16} className="text-gray-400" />
            ) : (
              <ChevronUp size={16} className="text-gray-400" />
            )}
          </div>
        </div>
      </div>

      {/* Content area */}
      {isOpen && (
        <div className="h-[calc(100%-2.5rem)] bg-[#1a1a1a]">
          {/* Agent Logs Tab */}
          {activeTab === 'agent' && (
            <div
              ref={scrollRef}
              onScroll={handleScroll}
              className="h-full overflow-y-auto p-2 font-mono text-sm"
            >
              {logs.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-500">
                  No logs yet. Start the agent to see output.
                </div>
              ) : (
                <div className="space-y-0.5">
                  {logs.map((log, index) => {
                    const level = getLogLevel(log.line)
                    const colorClass = getLogColor(level)
                    const timestamp = formatTimestamp(log.timestamp)

                    return (
                      <div
                        key={`${log.timestamp}-${index}`}
                        className="flex gap-2 hover:bg-[#2a2a2a] px-1 py-0.5 rounded"
                      >
                        <span className="text-gray-500 select-none shrink-0">
                          {timestamp}
                        </span>
                        <span className={`${colorClass} whitespace-pre-wrap break-all`}>
                          {log.line}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Dev Server Logs Tab */}
          {activeTab === 'devserver' && (
            <div
              ref={devScrollRef}
              onScroll={handleDevScroll}
              className="h-full overflow-y-auto p-2 font-mono text-sm"
            >
              {devLogs.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-500">
                  No dev server logs yet.
                </div>
              ) : (
                <div className="space-y-0.5">
                  {devLogs.map((log, index) => {
                    const level = getLogLevel(log.line)
                    const colorClass = getLogColor(level)
                    const timestamp = formatTimestamp(log.timestamp)

                    return (
                      <div
                        key={`${log.timestamp}-${index}`}
                        className="flex gap-2 hover:bg-[#2a2a2a] px-1 py-0.5 rounded"
                      >
                        <span className="text-gray-500 select-none shrink-0">
                          {timestamp}
                        </span>
                        <span className={`${colorClass} whitespace-pre-wrap break-all`}>
                          {log.line}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Terminal Tab */}
          {activeTab === 'terminal' && (
            <div className="h-full flex flex-col">
              {/* Terminal tabs bar */}
              {terminals.length > 0 && (
                <TerminalTabs
                  terminals={terminals}
                  activeTerminalId={activeTerminalId}
                  onSelect={setActiveTerminalId}
                  onCreate={handleCreateTerminal}
                  onRename={handleRenameTerminal}
                  onClose={handleCloseTerminal}
                />
              )}

              {/* Terminal content - render all terminals and show/hide to preserve buffers */}
              <div className="flex-1 min-h-0 relative">
                {isLoadingTerminals ? (
                  <div className="h-full flex items-center justify-center text-gray-500 font-mono text-sm">
                    Loading terminals...
                  </div>
                ) : terminals.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-gray-500 font-mono text-sm">
                    No terminal available
                  </div>
                ) : (
                  /* Render all terminals stacked on top of each other.
                   * Active terminal is visible and receives input.
                   * Inactive terminals are moved off-screen with transform to:
                   * 1. Trigger IntersectionObserver (xterm.js pauses rendering)
                   * 2. Preserve terminal buffer content
                   * 3. Allow proper dimension calculation when becoming visible
                   * Using transform instead of opacity/display:none for best xterm.js compatibility.
                   */
                  terminals.map((terminal) => {
                    const isActiveTerminal = terminal.id === activeTerminalId
                    return (
                      <div
                        key={terminal.id}
                        className="absolute inset-0"
                        style={{
                          zIndex: isActiveTerminal ? 10 : 1,
                          transform: isActiveTerminal ? 'none' : 'translateX(-200%)',
                          pointerEvents: isActiveTerminal ? 'auto' : 'none',
                        }}
                      >
                        <Terminal
                          projectName={projectName}
                          terminalId={terminal.id}
                          isActive={activeTab === 'terminal' && isActiveTerminal}
                        />
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Export the TabType for use in parent components
export type { TabType }
