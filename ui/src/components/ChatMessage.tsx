/**
 * Chat Message Component
 *
 * Displays a single message in the spec creation chat.
 * Supports user, assistant, and system messages with clean styling.
 */

import { memo } from "react";
import { Bot, User, Info } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "../lib/types";
import { Card } from "@/components/ui/card";

interface ChatMessageProps {
  message: ChatMessageType;
}

// Module-level regex to avoid recreating on each render
const BOLD_REGEX = /\*\*(.*?)\*\*/g;

export const ChatMessage = memo(function ChatMessage({
  message,
}: ChatMessageProps) {
  const { role, content, attachments, timestamp, isStreaming } = message;

  // Format timestamp
  const timeString = timestamp.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Role-specific styling
  const roleConfig = {
    user: {
      icon: User,
      bgColor: "bg-primary",
      textColor: "text-primary-foreground",
      align: "justify-end",
      bubbleAlign: "items-end",
      iconBg: "bg-primary",
      iconColor: "text-primary-foreground",
    },
    assistant: {
      icon: Bot,
      bgColor: "bg-muted",
      textColor: "text-foreground",
      align: "justify-start",
      bubbleAlign: "items-start",
      iconBg: "bg-secondary",
      iconColor: "text-secondary-foreground",
    },
    system: {
      icon: Info,
      bgColor: "bg-green-100 dark:bg-green-900/30",
      textColor: "text-green-900 dark:text-green-100",
      align: "justify-center",
      bubbleAlign: "items-center",
      iconBg: "bg-green-500",
      iconColor: "text-white",
    },
  };

  const config = roleConfig[role];
  const Icon = config.icon;

  // System messages are styled differently
  if (role === "system") {
    return (
      <div className={`flex ${config.align} px-4 py-2`}>
        <div
          className={`${config.bgColor} border border-border rounded-lg px-4 py-2 text-sm font-mono ${config.textColor}`}
        >
          <span className="flex items-center gap-2">
            <Icon size={14} />
            {content}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${config.align} px-4 py-2`}>
      <div className={`flex flex-col ${config.bubbleAlign} max-w-[80%] gap-1`}>
        {/* Message bubble */}
        <div className="flex items-start gap-2">
          {role === "assistant" && (
            <div className={`${config.iconBg} p-1.5 rounded flex-shrink-0`}>
              <Icon size={16} className={config.iconColor} />
            </div>
          )}

          <Card
            className={`${config.bgColor} px-4 py-3 border ${isStreaming ? "animate-pulse" : ""}`}
          >
            {/* Parse content for basic markdown-like formatting */}
            {content && (
              <div
                className={`whitespace-pre-wrap text-sm leading-relaxed ${config.textColor}`}
              >
                {content.split("\n").map((line, i) => {
                  // Bold text - use module-level regex, reset lastIndex for each line
                  BOLD_REGEX.lastIndex = 0;
                  const parts = [];
                  let lastIndex = 0;
                  let match;

                  while ((match = BOLD_REGEX.exec(line)) !== null) {
                    if (match.index > lastIndex) {
                      parts.push(line.slice(lastIndex, match.index));
                    }
                    parts.push(
                      <strong
                        key={`bold-${i}-${match.index}`}
                        className="font-bold"
                      >
                        {match[1]}
                      </strong>,
                    );
                    lastIndex = match.index + match[0].length;
                  }

                  if (lastIndex < line.length) {
                    parts.push(line.slice(lastIndex));
                  }

                  return (
                    <span key={i}>
                      {parts.length > 0 ? parts : line}
                      {i < content.split("\n").length - 1 && "\n"}
                    </span>
                  );
                })}
              </div>
            )}

            {/* Display image attachments */}
            {attachments && attachments.length > 0 && (
              <div className={`flex flex-wrap gap-2 ${content ? "mt-3" : ""}`}>
                {attachments.map((attachment) => (
                  <div
                    key={attachment.id}
                    className="border border-border rounded p-1 bg-card"
                  >
                    <img
                      src={attachment.previewUrl}
                      alt={attachment.filename}
                      className="max-w-48 max-h-48 object-contain cursor-pointer hover:opacity-90 transition-opacity rounded"
                      onClick={() =>
                        window.open(attachment.previewUrl, "_blank")
                      }
                      title={`${attachment.filename} (click to enlarge)`}
                    />
                    <span className="text-xs text-muted-foreground block mt-1 text-center">
                      {attachment.filename}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Streaming indicator */}
            {isStreaming && (
              <span className="inline-block w-2 h-4 bg-primary ml-1 animate-pulse rounded" />
            )}
          </Card>

          {role === "user" && (
            <div className={`${config.iconBg} p-1.5 rounded flex-shrink-0`}>
              <Icon size={16} className={config.iconColor} />
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span className="text-xs text-muted-foreground font-mono px-2">
          {timeString}
        </span>
      </div>
    </div>
  );
});
