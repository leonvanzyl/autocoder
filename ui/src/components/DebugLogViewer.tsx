/**
 * Logs Drawer Component
 *
 * Collapsible panel at the bottom of the screen showing real-time
 * agent output (tool calls, results, steps). Similar to browser DevTools.
 * Features a resizable height via drag handle.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { ChevronUp, ChevronDown, Trash2, Terminal, GripHorizontal, FileText, Server } from 'lucide-react'
import { WorkerLogsPanel } from './WorkerLogsPanel'
import { DevServerControl } from './DevServerControl'
import { TerminalTabsPanel } from './TerminalTabsPanel'

const MIN_HEIGHT = 150
const MAX_HEIGHT = 600
const DEFAULT_HEIGHT = 288
const STORAGE_KEY = 'logs-drawer-height'

interface DebugLogViewerProps {
  logs: Array<{ line: string; timestamp: string }>
  isOpen: boolean
  onToggle: () => void
  onClear: () => void
  onHeightChange?: (height: number) => void
  projectName?: string | null
  openTab?: 'live' | 'workers' | 'devserver' | 'terminal'
}

type LogLevel = 'error' | 'warn' | 'debug' | 'info'

export function DebugLogViewer({
  logs,
  isOpen,
  onToggle,
  onClear,
  onHeightChange,
  projectName,
  openTab = 'live',
}: DebugLogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [isResizing, setIsResizing] = useState(false)
  const [tab, setTab] = useState<'live' | 'workers' | 'devserver' | 'terminal'>(openTab)
  const [panelHeight, setPanelHeight] = useState(() => {
    // Load saved height from localStorage
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? Math.min(Math.max(parseInt(saved, 10), MIN_HEIGHT), MAX_HEIGHT) : DEFAULT_HEIGHT
  })

  useEffect(() => {
    if (isOpen) setTab(openTab)
  }, [openTab, isOpen])

  // Auto-scroll to bottom when new logs arrive (if user hasn't scrolled up)
  useEffect(() => {
    if (tab === 'live' && autoScroll && scrollRef.current && isOpen) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll, isOpen, tab])

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

  // Detect if user scrolled up
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 50
    setAutoScroll(isAtBottom)
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
        className="flex items-center justify-between h-10 px-4 bg-[#1a1a1a] border-t-3 border-black cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2">
          {tab === 'workers' ? (
            <FileText size={16} className="text-cyan-300" />
          ) : tab === 'devserver' ? (
            <Server size={16} className="text-yellow-300" />
          ) : (
            <Terminal size={16} className="text-green-400" />
          )}
          <span className="font-mono text-sm text-white font-bold">
            Logs
          </span>
          <span className="px-1.5 py-0.5 text-xs font-mono bg-[#333] text-gray-500 rounded" title="Toggle logs drawer (live)">
            D
          </span>
          <span className="px-1.5 py-0.5 text-xs font-mono bg-[#333] text-gray-500 rounded" title="Open worker logs">
            L
          </span>
          <span className="px-1.5 py-0.5 text-xs font-mono bg-[#333] text-gray-500 rounded" title="Open terminal tab">
            T
          </span>

          {tab === 'live' && logs.length > 0 && (
            <span className="px-2 py-0.5 text-xs font-mono bg-[#333] text-gray-300 rounded">{logs.length}</span>
          )}
          {tab === 'live' && !autoScroll && isOpen && (
            <span className="px-2 py-0.5 text-xs font-mono bg-yellow-600 text-white rounded">
              Paused
            </span>
          )}

          {isOpen && (
            <div className="ml-2 flex items-center gap-1">
              <button
                className={`px-2 py-1 text-xs font-mono rounded border border-[#333] ${
                  tab === 'live' ? 'bg-[#333] text-white' : 'text-gray-400 hover:bg-[#222]'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  setTab('live')
                }}
                title="Live logs"
              >
                Live
              </button>
              <button
                className={`px-2 py-1 text-xs font-mono rounded border border-[#333] ${
                  tab === 'workers' ? 'bg-[#333] text-white' : 'text-gray-400 hover:bg-[#222]'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  setTab('workers')
                }}
                title="Worker log files"
              >
                Workers
              </button>
              <button
                className={`px-2 py-1 text-xs font-mono rounded border border-[#333] ${
                  tab === 'devserver' ? 'bg-[#333] text-white' : 'text-gray-400 hover:bg-[#222]'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  setTab('devserver')
                }}
                title="Dev server"
              >
                Dev
              </button>
              <button
                className={`px-2 py-1 text-xs font-mono rounded border border-[#333] ${
                  tab === 'terminal' ? 'bg-[#333] text-white' : 'text-gray-400 hover:bg-[#222]'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  setTab('terminal')
                }}
                title="Interactive terminal"
              >
                Term
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isOpen && tab === 'live' && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onClear()
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

      {/* Log content area */}
      {isOpen && (
        <div className="h-[calc(100%-2.5rem)] overflow-hidden bg-[#1a1a1a]">
          {tab === 'live' ? (
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
                        <span className="text-gray-500 select-none shrink-0">{timestamp}</span>
                        <span className={`${colorClass} whitespace-pre-wrap break-all`}>{log.line}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ) : tab === 'workers' ? (
            <div className="h-full p-2 overflow-hidden">
              {projectName ? (
                <WorkerLogsPanel projectName={projectName} />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500 font-mono text-sm">
                  Select a project to view worker logs.
                </div>
              )}
            </div>
          ) : tab === 'devserver' ? (
            <div className="h-full p-2 overflow-hidden">
              {projectName ? (
                <DevServerControl projectName={projectName} />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500 font-mono text-sm">
                  Select a project to manage a dev server.
                </div>
              )}
            </div>
          ) : (
            <div className="h-full p-2 overflow-hidden">
              {projectName ? (
                <TerminalTabsPanel projectName={projectName} />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500 font-mono text-sm">
                  Select a project to use terminals.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
