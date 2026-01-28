/**
 * Hook for managing assistant chat WebSocket connection
 */

import { useState, useCallback, useRef, useEffect } from "react";
import type { ChatMessage, AssistantChatServerMessage } from "../lib/types";

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

interface UseAssistantChatOptions {
  projectName: string;
  onError?: (error: string) => void;
}

interface UseAssistantChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  connectionStatus: ConnectionStatus;
  conversationId: number | null;
  start: (conversationId?: number | null) => void;
  sendMessage: (content: string) => void;
  disconnect: () => void;
  clearMessages: () => void;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Type-safe helper to get a string value from unknown input
 */
function getStringValue(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

/**
 * Type-safe helper to get a feature ID from unknown input
 */
function getFeatureId(value: unknown): string {
  if (typeof value === "number" || typeof value === "string") {
    return String(value);
  }
  return "unknown";
}

/**
 * Get a user-friendly description for tool calls
 */
function getToolDescription(
  tool: string,
  input: Record<string, unknown>,
): string {
  // Handle both mcp__features__* and direct tool names
  const toolName = tool.replace("mcp__features__", "");

  switch (toolName) {
    case "feature_get_stats":
      return "Getting feature statistics...";
    case "feature_get_next":
      return "Getting next feature...";
    case "feature_get_for_regression":
      return "Getting features for regression testing...";
    case "feature_create":
      return `Creating feature: ${getStringValue(input.name, "new feature")}`;
    case "feature_create_bulk":
      return `Creating ${Array.isArray(input.features) ? input.features.length : "multiple"} features...`;
    case "feature_skip":
      return `Skipping feature #${getFeatureId(input.feature_id)}`;
    case "feature_update":
      return `Updating feature #${getFeatureId(input.feature_id)}`;
    case "feature_delete":
      return `Deleting feature #${getFeatureId(input.feature_id)}`;
    case "Read":
      return `Reading file: ${getStringValue(input.file_path, "file")}`;
    case "Glob":
      return `Searching files: ${getStringValue(input.pattern, "pattern")}`;
    case "Grep":
      return `Searching content: ${getStringValue(input.pattern, "pattern")}`;
    default:
      return `Using tool: ${tool}`;
  }
}

export function useAssistantChat({
  projectName,
  onError,
}: UseAssistantChatOptions): UseAssistantChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");
  const [conversationId, setConversationId] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const currentAssistantMessageRef = useRef<string | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 3;
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const connectTimeoutRef = useRef<number | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (connectTimeoutRef.current) {
        clearTimeout(connectTimeoutRef.current);
        connectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      currentAssistantMessageRef.current = null;
    };
  }, []);

  const connect = useCallback(() => {
    // Prevent multiple connection attempts
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    setConnectionStatus("connecting");

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/assistant/ws/${encodeURIComponent(projectName)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // Only act if this is still the current connection
      if (wsRef.current !== ws) return;

      setConnectionStatus("connected");
      reconnectAttempts.current = 0;

      // Clear any previous ping interval before starting a new one
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }

      // Start ping interval to keep connection alive
      pingIntervalRef.current = window.setInterval(() => {
        if (wsRef.current === ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000);
    };

    ws.onclose = () => {
      // Only act if this is still the current connection
      if (wsRef.current !== ws) return;

      setConnectionStatus("disconnected");
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }

      // Attempt reconnection if not intentionally closed
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current++;
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttempts.current),
          10000,
        );
        reconnectTimeoutRef.current = window.setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      // Only act if this is still the current connection
      if (wsRef.current !== ws) return;

      setConnectionStatus("error");
      onError?.("WebSocket connection error");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AssistantChatServerMessage;
        if (import.meta.env.DEV) {
          console.debug('[useAssistantChat] Received WebSocket message:', data.type, data);
        }

        switch (data.type) {
          case "text": {
            // Append text to current assistant message or create new one
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (
                lastMessage?.role === "assistant" &&
                lastMessage.isStreaming
              ) {
                // Append to existing streaming message
                return [
                  ...prev.slice(0, -1),
                  {
                    ...lastMessage,
                    content: lastMessage.content + data.content,
                  },
                ];
              } else {
                // Create new assistant message
                currentAssistantMessageRef.current = generateId();
                return [
                  ...prev,
                  {
                    id: currentAssistantMessageRef.current,
                    role: "assistant",
                    content: data.content,
                    timestamp: new Date(),
                    isStreaming: true,
                  },
                ];
              }
            });
            break;
          }

          case "tool_call": {
            // Show tool call as system message with friendly description
            // Normalize input to object to guard against null/non-object at runtime
            const input = typeof data.input === "object" && data.input !== null 
              ? (data.input as Record<string, unknown>) 
              : {};
            const toolDescription = getToolDescription(data.tool, input);
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: "system",
                content: toolDescription,
                timestamp: new Date(),
              },
            ]);
            break;
          }

          case "conversation_created": {
            setConversationId(data.conversation_id);
            break;
          }

          case "response_done": {
            setIsLoading(false);
            currentAssistantMessageRef.current = null;

            // Find and mark the most recent streaming assistant message as done
            // (may not be the last message if tool_call/system messages followed)
            setMessages((prev) => {
              // Find the most recent streaming assistant message from the end
              for (let i = prev.length - 1; i >= 0; i--) {
                const msg = prev[i];
                if (msg.role === "assistant" && msg.isStreaming) {
                  // Found it - update this message and return
                  return [
                    ...prev.slice(0, i),
                    { ...msg, isStreaming: false },
                    ...prev.slice(i + 1),
                  ];
                }
              }
              return prev;
            });
            break;
          }

          case "error": {
            setIsLoading(false);
            onError?.(data.content);

            // Add error as system message
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: "system",
                content: `Error: ${data.content}`,
                timestamp: new Date(),
              },
            ]);
            break;
          }

          case "pong": {
            // Keep-alive response, nothing to do
            break;
          }
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };
  }, [projectName, onError]);

  const start = useCallback(
    (existingConversationId?: number | null) => {
      // Clear any existing connect timeout before starting
      if (connectTimeoutRef.current) {
        clearTimeout(connectTimeoutRef.current);
        connectTimeoutRef.current = null;
      }

      connect();

      // Wait for connection then send start message
      // Add retry limit to prevent infinite polling if connection never opens
      const maxRetries = 50; // 50 * 100ms = 5 seconds max wait
      let retryCount = 0;

      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          // Connection succeeded - clear timeout ref
          connectTimeoutRef.current = null;
          setIsLoading(true);
          const payload: { type: string; conversation_id?: number } = {
            type: "start",
          };
          if (existingConversationId) {
            payload.conversation_id = existingConversationId;
            setConversationId(existingConversationId);
          }
          if (import.meta.env.DEV) {
            console.debug('[useAssistantChat] Sending start message:', payload);
          }
          wsRef.current.send(JSON.stringify(payload));
        } else if (wsRef.current?.readyState === WebSocket.CONNECTING) {
          retryCount++;
          if (retryCount >= maxRetries) {
            // Connection timeout - close stuck socket so future retries can succeed
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
            if (connectTimeoutRef.current) {
              clearTimeout(connectTimeoutRef.current);
              connectTimeoutRef.current = null;
            }
            setIsLoading(false);
            onError?.("Connection timeout: WebSocket failed to open");
            return;
          }
          connectTimeoutRef.current = window.setTimeout(checkAndSend, 100);
        } else {
          // WebSocket is closed or in an error state - close and clear ref so retries can succeed
          if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
          }
          if (connectTimeoutRef.current) {
            clearTimeout(connectTimeoutRef.current);
            connectTimeoutRef.current = null;
          }
          setIsLoading(false);
          onError?.("Failed to establish WebSocket connection");
        }
      };

      connectTimeoutRef.current = window.setTimeout(checkAndSend, 100);
    },
    [connect, onError],
  );

  const sendMessage = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        onError?.("Not connected");
        return;
      }

      // Add user message to chat
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "user",
          content,
          timestamp: new Date(),
        },
      ]);

      setIsLoading(true);

      // Send to server
      wsRef.current.send(
        JSON.stringify({
          type: "message",
          content,
        }),
      );
    },
    [onError],
  );

  const disconnect = useCallback(() => {
    reconnectAttempts.current = maxReconnectAttempts; // Prevent reconnection

    // Clear any pending connect timeout (from start polling)
    if (connectTimeoutRef.current) {
      clearTimeout(connectTimeoutRef.current);
      connectTimeoutRef.current = null;
    }

    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Clear ping interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    // Close WebSocket connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionStatus("disconnected");
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    // Don't reset conversationId here - it will be set by start() when switching
  }, []);

  return {
    messages,
    isLoading,
    connectionStatus,
    conversationId,
    start,
    sendMessage,
    disconnect,
    clearMessages,
  };
}
