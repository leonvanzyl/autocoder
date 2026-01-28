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
  const checkAndSendTimeoutRef = useRef<number | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (checkAndSendTimeoutRef.current) {
        clearTimeout(checkAndSendTimeoutRef.current);
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
        if (import.meta.env.DEV) {
          console.debug(
            "[useAssistantChat] Received WebSocket message:",
            data.type,
            data,
          );
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
            // Generate user-friendly tool descriptions
            let toolDescription = `Using tool: ${data.tool}`;

            if (data.tool === "mcp__features__feature_create") {
              const input = data.input as { name?: string; category?: string };
              toolDescription = `Creating feature: "${input.name || "New Feature"}" in ${input.category || "General"}`;
            } else if (data.tool === "mcp__features__feature_create_bulk") {
              const input = data.input as {
                features?: Array<{ name: string }>;
              };
              const count = input.features?.length || 0;
              toolDescription = `Creating ${count} feature${count !== 1 ? "s" : ""}`;
            } else if (data.tool === "mcp__features__feature_skip") {
              toolDescription = `Skipping feature (moving to end of queue)`;
            } else if (data.tool === "mcp__features__feature_get_stats") {
              toolDescription = `Checking project progress`;
            } else if (data.tool === "mcp__features__feature_get_next") {
              toolDescription = `Getting next pending feature`;
            } else if (data.tool === "Read") {
              const input = data.input as { file_path?: string };
              const path = input.file_path || "";
              const filename = path.split("/").pop() || path;
              toolDescription = `Reading file: ${filename}`;
            } else if (data.tool === "Glob") {
              const input = data.input as { pattern?: string };
              toolDescription = `Searching for files: ${input.pattern || "..."}`;
            } else if (data.tool === "Grep") {
              const input = data.input as { pattern?: string };
              toolDescription = `Searching for: ${input.pattern || "..."}`;
            }

            // Show tool call as system message
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
      // Clear any pending check timeout from previous call
      if (checkAndSendTimeoutRef.current) {
        clearTimeout(checkAndSendTimeoutRef.current);
        checkAndSendTimeoutRef.current = null;
      }

      connect();

      // Wait for connection then send start message
      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          checkAndSendTimeoutRef.current = null;
          setIsLoading(true);
          const payload: { type: string; conversation_id?: number } = {
            type: "start",
          };
          if (existingConversationId) {
            payload.conversation_id = existingConversationId;
            setConversationId(existingConversationId);
          }
          if (import.meta.env.DEV) {
            console.debug("[useAssistantChat] Sending start message:", payload);
          }
          wsRef.current.send(JSON.stringify(payload));
        } else if (wsRef.current?.readyState === WebSocket.CONNECTING) {
          checkAndSendTimeoutRef.current = window.setTimeout(checkAndSend, 100);
        } else {
          checkAndSendTimeoutRef.current = null;
        }
      };

      checkAndSendTimeoutRef.current = window.setTimeout(checkAndSend, 100);
    },
    [connect],
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
