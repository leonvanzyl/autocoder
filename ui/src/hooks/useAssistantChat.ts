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
      return `Creating feature: ${input.name || "new feature"}`;
    case "feature_create_bulk":
      return `Creating ${Array.isArray(input.features) ? input.features.length : "multiple"} features...`;
    case "feature_skip":
      return `Skipping feature #${input.feature_id}`;
    case "feature_update":
      return `Updating feature #${input.feature_id}`;
    case "feature_delete":
      return `Deleting feature #${input.feature_id}`;
    case "Read":
      return `Reading file: ${input.file_path || "file"}`;
    case "Glob":
      return `Searching files: ${input.pattern || "pattern"}`;
    case "Grep":
      return `Searching content: ${input.pattern || "pattern"}`;
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

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
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
      setConnectionStatus("connected");
      reconnectAttempts.current = 0;

      // Start ping interval to keep connection alive
      pingIntervalRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000);
    };

    ws.onclose = () => {
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
      setConnectionStatus("error");
      onError?.("WebSocket connection error");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AssistantChatServerMessage;

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
            const toolDescription = getToolDescription(
              data.tool,
              data.input as Record<string, unknown>,
            );
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

            // Mark current message as done streaming
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (
                lastMessage?.role === "assistant" &&
                lastMessage.isStreaming
              ) {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, isStreaming: false },
                ];
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
      connect();

      // Wait for connection then send start message
      // Add retry limit to prevent infinite polling if connection never opens
      const maxRetries = 50; // 50 * 100ms = 5 seconds max wait
      let retryCount = 0;

      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          setIsLoading(true);
          const payload: { type: string; conversation_id?: number } = {
            type: "start",
          };
          if (existingConversationId) {
            payload.conversation_id = existingConversationId;
            setConversationId(existingConversationId);
          }
          wsRef.current.send(JSON.stringify(payload));
        } else if (wsRef.current?.readyState === WebSocket.CONNECTING) {
          retryCount++;
          if (retryCount >= maxRetries) {
            // Connection timeout - stop polling and report error
            setIsLoading(false);
            onError?.("Connection timeout: WebSocket failed to open");
            return;
          }
          setTimeout(checkAndSend, 100);
        } else {
          // WebSocket is closed or in an error state
          setIsLoading(false);
          onError?.("Failed to establish WebSocket connection");
        }
      };

      setTimeout(checkAndSend, 100);
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
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnectionStatus("disconnected");
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(null);
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
