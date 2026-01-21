/**
 * Hook for managing assistant chat WebSocket connection
 *
 * Automatically resumes the most recent conversation when mounted.
 * Provides startNewConversation() to begin a fresh chat.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import type {
  ChatMessage,
  AssistantChatServerMessage,
  AssistantConversation,
} from "../lib/types";
import {
  listAssistantConversations,
  getAssistantConversation,
} from "../lib/api";

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
  conversations: AssistantConversation[];
  isLoadingHistory: boolean;
  start: (conversationId?: number | null) => void;
  sendMessage: (content: string) => void;
  disconnect: () => void;
  clearMessages: () => void;
  startNewConversation: () => void;
  switchConversation: (conversationId: number) => void;
  refreshConversations: () => Promise<void>;
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
  const [conversations, setConversations] = useState<AssistantConversation[]>(
    [],
  );
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const currentAssistantMessageRef = useRef<string | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 3;
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const checkAndSendTimeoutRef = useRef<number | null>(null);
  const hasInitializedRef = useRef(false);
  const resumeTimeoutRef = useRef<number | null>(null);

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
      if (resumeTimeoutRef.current) {
        clearTimeout(resumeTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      currentAssistantMessageRef.current = null;
    };
  }, []);

  // Fetch conversation list for the project
  const refreshConversations = useCallback(async () => {
    try {
      const convos = await listAssistantConversations(projectName);
      // Sort by updated_at descending (most recent first)
      convos.sort((a, b) => {
        const dateA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
        const dateB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
        return dateB - dateA;
      });
      setConversations(convos);
    } catch (err) {
      console.error("Failed to fetch conversations:", err);
    }
  }, [projectName]);

  // Load messages from a specific conversation
  const loadConversationMessages = useCallback(
    async (convId: number): Promise<ChatMessage[]> => {
      try {
        const detail = await getAssistantConversation(projectName, convId);
        return detail.messages.map((m) => ({
          id: `db-${m.id}`,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
          isStreaming: false,
        }));
      } catch (err) {
        console.error("Failed to load conversation messages:", err);
        return [];
      }
    },
    [projectName],
  );

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
    setConversationId(null);
  }, []);

  // Start a brand new conversation (clears history, no conversation_id)
  const startNewConversation = useCallback(() => {
    disconnect();
    setMessages([]);
    setConversationId(null);
    // Start fresh - pass null to not resume any conversation
    start(null);
  }, [disconnect, start]);

  // Resume an existing conversation - just connect WebSocket, no greeting
  const resumeConversation = useCallback(
    (convId: number) => {
      // Clear any pending resume timeout
      if (resumeTimeoutRef.current) {
        clearTimeout(resumeTimeoutRef.current);
        resumeTimeoutRef.current = null;
      }

      connect();
      setConversationId(convId);

      // Wait for connection then send resume message (no greeting)
      const maxRetries = 50;
      let retryCount = 0;

      const checkAndResume = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          // Clear timeout ref since we're done
          resumeTimeoutRef.current = null;
          // Send start with conversation_id but backend won't send greeting
          // for resumed conversations with messages
          wsRef.current.send(
            JSON.stringify({
              type: "resume",
              conversation_id: convId,
            }),
          );
        } else if (wsRef.current?.readyState === WebSocket.CONNECTING) {
          retryCount++;
          if (retryCount < maxRetries) {
            resumeTimeoutRef.current = window.setTimeout(checkAndResume, 100);
          } else {
            resumeTimeoutRef.current = null;
          }
        } else {
          resumeTimeoutRef.current = null;
        }
      };

      resumeTimeoutRef.current = window.setTimeout(checkAndResume, 100);
    },
    [connect],
  );

  // Switch to a specific existing conversation
  const switchConversation = useCallback(
    async (convId: number) => {
      setIsLoadingHistory(true);
      disconnect();

      // Load messages from the database
      const loadedMessages = await loadConversationMessages(convId);
      setMessages(loadedMessages);

      // Resume without greeting if has messages, otherwise start fresh
      if (loadedMessages.length > 0) {
        resumeConversation(convId);
      } else {
        start(convId);
      }
      setIsLoadingHistory(false);
    },
    [disconnect, loadConversationMessages, start, resumeConversation],
  );

  // Initialize on mount - fetch conversations and resume most recent
  useEffect(() => {
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;

    const initialize = async () => {
      setIsLoadingHistory(true);
      try {
        // Fetch conversation list
        const convos = await listAssistantConversations(projectName);
        convos.sort((a, b) => {
          const dateA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
          const dateB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
          return dateB - dateA;
        });
        setConversations(convos);

        // If there's a recent conversation with messages, resume without greeting
        if (convos.length > 0) {
          const mostRecent = convos[0];
          const loadedMessages = await loadConversationMessages(mostRecent.id);
          setMessages(loadedMessages);

          if (loadedMessages.length > 0) {
            // Has messages - just reconnect, don't request greeting
            resumeConversation(mostRecent.id);
          } else {
            // Empty conversation - request greeting
            start(mostRecent.id);
          }
        } else {
          // No existing conversations, start fresh
          start(null);
        }
      } catch (err) {
        console.error("Failed to initialize chat:", err);
        // Fall back to starting fresh
        start(null);
      } finally {
        setIsLoadingHistory(false);
      }
    };

    initialize();
  }, [projectName, loadConversationMessages, start, resumeConversation]);

  return {
    messages,
    isLoading,
    connectionStatus,
    conversationId,
    conversations,
    isLoadingHistory,
    start,
    sendMessage,
    disconnect,
    clearMessages,
    startNewConversation,
    switchConversation,
    refreshConversations,
  };
}
