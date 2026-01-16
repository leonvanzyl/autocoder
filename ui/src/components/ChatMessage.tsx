/**
 * Chat Message Component
 *
 * Displays a single message in the spec creation chat.
 * Supports user, assistant, and system messages with neobrutalism styling.
 */

import { Bot, User, Info } from 'lucide-react'
import type { ChatMessage as ChatMessageType } from '../lib/types'

interface ChatMessageProps {
  message: ChatMessageType
}

export function ChatMessage({ message }: ChatMessageProps) {
  const { role, content, attachments, timestamp, isStreaming } = message

  // Format timestamp
  const timeString = timestamp.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })

  // Role-specific styling using CSS variables for theme consistency
  const roleConfig = {
    user: {
      icon: User,
      bgColor: 'bg-[var(--color-neo-pending)]',
      textColor: 'text-[var(--color-neo-text-on-bright)]',
      borderColor: 'border-[var(--color-neo-border)]',
      align: 'justify-end',
      bubbleAlign: 'items-end',
      iconBg: 'bg-[var(--color-neo-pending)]',
      shadow: 'var(--shadow-neo-md)',
    },
    assistant: {
      icon: Bot,
      bgColor: 'bg-[var(--color-neo-card)]',
      textColor: 'text-[var(--color-neo-text)]',
      borderColor: 'border-[var(--color-neo-border)]',
      align: 'justify-start',
      bubbleAlign: 'items-start',
      iconBg: 'bg-[var(--color-neo-progress)]',
      shadow: 'var(--shadow-neo-md)',
    },
    system: {
      icon: Info,
      bgColor: 'bg-[var(--color-neo-done)]',
      textColor: 'text-[var(--color-neo-text-on-bright)]',
      borderColor: 'border-[var(--color-neo-border)]',
      align: 'justify-center',
      bubbleAlign: 'items-center',
      iconBg: 'bg-[var(--color-neo-done)]',
      shadow: 'var(--shadow-neo-sm)',
    },
  }

  const config = roleConfig[role]
  const Icon = config.icon

  // System messages are styled differently
  if (role === 'system') {
    return (
      <div className={`flex ${config.align} px-4 py-2`}>
        <div
          className={`
            ${config.bgColor}
            border-2 ${config.borderColor}
            px-4 py-2
            text-sm font-mono text-[var(--color-neo-text-on-bright)]
          `}
          style={{ boxShadow: 'var(--shadow-neo-sm)' }}
        >
          <span className="flex items-center gap-2">
            <Icon size={14} />
            {content}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex ${config.align} px-4 py-2`}>
      <div className={`flex flex-col ${config.bubbleAlign} max-w-[80%] gap-1`}>
        {/* Message bubble */}
        <div className="flex items-start gap-2">
          {role === 'assistant' && (
            <div
              className={`
                ${config.iconBg}
                border-2 border-[var(--color-neo-border)]
                p-1.5
                flex-shrink-0
              `}
              style={{ boxShadow: 'var(--shadow-neo-sm)' }}
            >
              <Icon size={16} className="text-[var(--color-neo-text-on-bright)]" />
            </div>
          )}

          <div
            className={`
              ${config.bgColor}
              border-3 ${config.borderColor}
              px-4 py-3
              ${isStreaming ? 'animate-pulse-neo' : ''}
            `}
            style={{ boxShadow: config.shadow }}
          >
            {/* Parse content for basic markdown-like formatting */}
            {content && (
              <div className={`whitespace-pre-wrap text-sm leading-relaxed ${config.textColor}`}>
                {content.split('\n').map((line, i) => {
                  // Bold text
                  const boldRegex = /\*\*(.*?)\*\*/g
                  const parts = []
                  let lastIndex = 0
                  let match

                  while ((match = boldRegex.exec(line)) !== null) {
                    if (match.index > lastIndex) {
                      parts.push(line.slice(lastIndex, match.index))
                    }
                    parts.push(
                      <strong key={`bold-${i}-${match.index}`} className="font-bold">
                        {match[1]}
                      </strong>
                    )
                    lastIndex = match.index + match[0].length
                  }

                  if (lastIndex < line.length) {
                    parts.push(line.slice(lastIndex))
                  }

                  return (
                    <span key={i}>
                      {parts.length > 0 ? parts : line}
                      {i < content.split('\n').length - 1 && '\n'}
                    </span>
                  )
                })}
              </div>
            )}

            {/* Display image attachments */}
            {attachments && attachments.length > 0 && (
              <div className={`flex flex-wrap gap-2 ${content ? 'mt-3' : ''}`}>
                {attachments.map((attachment) => (
                  <div
                    key={attachment.id}
                    className="border-2 border-[var(--color-neo-border)] p-1 bg-[var(--color-neo-card)]"
                    style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                  >
                    <img
                      src={attachment.previewUrl}
                      alt={attachment.filename}
                      className="max-w-48 max-h-48 object-contain cursor-pointer hover:opacity-90 transition-opacity"
                      onClick={() => window.open(attachment.previewUrl, '_blank')}
                      title={`${attachment.filename} (click to enlarge)`}
                    />
                    <span className="text-xs text-neo-text-secondary block mt-1 text-center">
                      {attachment.filename}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Streaming indicator */}
            {isStreaming && (
              <span className="inline-block w-2 h-4 bg-neo-accent ml-1 animate-pulse" />
            )}
          </div>

          {role === 'user' && (
            <div
              className={`
                ${config.iconBg}
                border-2 border-[var(--color-neo-border)]
                p-1.5
                flex-shrink-0
              `}
              style={{ boxShadow: 'var(--shadow-neo-sm)' }}
            >
              <Icon size={16} className="text-[var(--color-neo-text-on-bright)]" />
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span className="text-xs text-[var(--color-neo-text-secondary)] font-mono px-2">
          {timeString}
        </span>
      </div>
    </div>
  )
}
