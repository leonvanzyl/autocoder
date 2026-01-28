/**
 * Interactive Terminal Component
 *
 * Full terminal emulation using xterm.js with WebSocket connection to the backend.
 * Supports input/output streaming, terminal resizing, and reconnection handling.
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

interface TerminalProps {
  projectName: string;
  terminalId: string;
  isActive: boolean;
}

// WebSocket message types for terminal I/O
interface TerminalInputMessage {
  type: "input";
  data: string; // base64 encoded
}

interface TerminalResizeMessage {
  type: "resize";
  cols: number;
  rows: number;
}

interface TerminalOutputMessage {
  type: "output";
  data: string; // base64 encoded
}

interface TerminalExitMessage {
  type: "exit";
  code: number;
}

type TerminalServerMessage = TerminalOutputMessage | TerminalExitMessage;

// Clean terminal theme colors
const TERMINAL_THEME = {
  background: "#09090b", // zinc-950
  foreground: "#fafafa", // zinc-50
  cursor: "#3b82f6", // blue-500
  cursorAccent: "#09090b",
  selectionBackground: "rgba(59, 130, 246, 0.3)",
  selectionForeground: "#ffffff",
  black: "#09090b",
  red: "#ef4444",
  green: "#22c55e",
  yellow: "#eab308",
  blue: "#3b82f6",
  magenta: "#a855f7",
  cyan: "#06b6d4",
  white: "#fafafa",
  brightBlack: "#52525b",
  brightRed: "#f87171",
  brightGreen: "#4ade80",
  brightYellow: "#facc15",
  brightBlue: "#60a5fa",
  brightMagenta: "#c084fc",
  brightCyan: "#22d3ee",
  brightWhite: "#ffffff",
};

// Reconnection configuration
const RECONNECT_DELAY_BASE = 1000;
const RECONNECT_DELAY_MAX = 30000;

export function Terminal({ projectName, terminalId, isActive }: TerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttempts = useRef(0);
  const isInitializedRef = useRef(false);
  const isConnectingRef = useRef(false);
  const hasExitedRef = useRef(false);
  // Track intentional disconnection to prevent auto-reconnect race condition
  const isManualCloseRef = useRef(false);
  // Store connect function in ref to avoid useEffect dependency issues
  const connectRef = useRef<(() => void) | null>(null);
  // Track last project/terminal to avoid duplicate connect on initial activation
  const lastProjectRef = useRef<string | null>(null);
  const lastTerminalIdRef = useRef<string | null>(null);
  // Track isActive in a ref to avoid stale closure issues in connect()
  const isActiveRef = useRef(isActive);

  const [isConnected, setIsConnected] = useState(false);
  const [hasExited, setHasExited] = useState(false);
  const [exitCode, setExitCode] = useState<number | null>(null);

  // Keep ref in sync with state for use in callbacks without re-creating them
  useEffect(() => {
    hasExitedRef.current = hasExited;
  }, [hasExited]);

  // Keep isActiveRef in sync with isActive prop to avoid stale closures
  useEffect(() => {
    isActiveRef.current = isActive;
  }, [isActive]);

  /**
   * Encode string to base64
   */
  const encodeBase64 = useCallback((str: string): string => {
    // Handle Unicode by encoding to UTF-8 first
    const encoder = new TextEncoder();
    const bytes = encoder.encode(str);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }, []);

  /**
   * Decode base64 to string
   */
  const decodeBase64 = useCallback((base64: string): string => {
    try {
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const decoder = new TextDecoder();
      return decoder.decode(bytes);
    } catch {
      console.error("Failed to decode base64 data");
      return "";
    }
  }, []);

  /**
   * Send a message through the WebSocket
   */
  const sendMessage = useCallback(
    (message: TerminalInputMessage | TerminalResizeMessage) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(message));
      }
    },
    [],
  );

  /**
   * Send resize message to server
   */
  const sendResize = useCallback(
    (cols: number, rows: number) => {
      const message: TerminalResizeMessage = {
        type: "resize",
        cols,
        rows,
      };
      sendMessage(message);
    },
    [sendMessage],
  );

  /**
   * Fit terminal to container and notify server of new dimensions
   */
  const fitTerminal = useCallback(() => {
    if (fitAddonRef.current && terminalRef.current) {
      try {
        // Try to get proposed dimensions first
        const dimensions = fitAddonRef.current.proposeDimensions();
        const hasValidDimensions =
          dimensions &&
          dimensions.cols &&
          dimensions.rows &&
          !isNaN(dimensions.cols) &&
          !isNaN(dimensions.rows) &&
          dimensions.cols >= 1 &&
          dimensions.rows >= 1;

        if (hasValidDimensions) {
          // Valid dimensions - fit the terminal
          fitAddonRef.current.fit();
        }

        // Always send resize with current terminal dimensions
        // This ensures the server has the correct size even if fit() was skipped
        const { cols, rows } = terminalRef.current;
        if (cols > 0 && rows > 0) {
          sendResize(cols, rows);
        }
      } catch {
        // Container may not be visible yet, ignore
      }
    }
  }, [sendResize]);

  /**
   * Connect to the terminal WebSocket
   */
  const connect = useCallback(() => {
    // Use isActiveRef.current instead of isActive to avoid stale closure issues
    // when connect is called from setTimeout callbacks
    if (!projectName || !terminalId || !isActiveRef.current) return;

    // Prevent multiple simultaneous connection attempts
    if (
      isConnectingRef.current ||
      wsRef.current?.readyState === WebSocket.CONNECTING ||
      wsRef.current?.readyState === WebSocket.OPEN
    ) {
      return;
    }

    isConnectingRef.current = true;

    // Clear any pending reconnection
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Build WebSocket URL with terminal ID
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/terminal/ws/${encodeURIComponent(projectName)}/${encodeURIComponent(terminalId)}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        isConnectingRef.current = false;
        setIsConnected(true);
        setHasExited(false);
        setExitCode(null);
        reconnectAttempts.current = 0;

        // Send initial size after connection
        if (terminalRef.current) {
          const { cols, rows } = terminalRef.current;
          sendResize(cols, rows);
        }
      };

      ws.onmessage = (event) => {
        try {
          const message: TerminalServerMessage = JSON.parse(event.data);

          switch (message.type) {
            case "output": {
              const decoded = decodeBase64(message.data);
              if (decoded && terminalRef.current) {
                terminalRef.current.write(decoded);
              }
              break;
            }
            case "exit": {
              setHasExited(true);
              setExitCode(message.code);
              if (terminalRef.current) {
                terminalRef.current.writeln("");
                terminalRef.current.writeln(
                  `\x1b[33m[Shell exited with code ${message.code}]\x1b[0m`,
                );
                terminalRef.current.writeln(
                  "\x1b[90mPress any key to reconnect...\x1b[0m",
                );
              }
              break;
            }
          }
        } catch {
          console.error("Failed to parse terminal WebSocket message");
        }
      };

      ws.onclose = () => {
        isConnectingRef.current = false;
        setIsConnected(false);
        wsRef.current = null;

        // Only reconnect if still active, not intentionally exited, and not manually closed
        // Use isActiveRef.current to get the current value, avoiding stale closure
        const shouldReconnect =
          isActiveRef.current &&
          !hasExitedRef.current &&
          !isManualCloseRef.current;
        // Reset manual close flag after checking (so subsequent disconnects can auto-reconnect)
        isManualCloseRef.current = false;

        if (shouldReconnect) {
          // Exponential backoff reconnection
          const delay = Math.min(
            RECONNECT_DELAY_BASE * Math.pow(2, reconnectAttempts.current),
            RECONNECT_DELAY_MAX,
          );
          reconnectAttempts.current++;

          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, delay);
        }
      };

      ws.onerror = () => {
        // Will trigger onclose, which handles reconnection
        ws.close();
      };
    } catch {
      isConnectingRef.current = false;
      // Failed to connect, attempt reconnection
      const delay = Math.min(
        RECONNECT_DELAY_BASE * Math.pow(2, reconnectAttempts.current),
        RECONNECT_DELAY_MAX,
      );
      reconnectAttempts.current++;

      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, delay);
    }
  }, [projectName, terminalId, sendResize, decodeBase64]);

  // Keep connect ref up to date
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  /**
   * Initialize xterm.js terminal
   */
  const initializeTerminal = useCallback(() => {
    if (!containerRef.current || isInitializedRef.current) return;

    // Create terminal instance
    const terminal = new XTerm({
      theme: TERMINAL_THEME,
      fontFamily: "JetBrains Mono, Consolas, Monaco, monospace",
      fontSize: 14,
      cursorBlink: true,
      cursorStyle: "block",
      allowProposedApi: true,
      scrollback: 10000,
    });

    // Create and load FitAddon
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);

    // Open terminal in container
    terminal.open(containerRef.current);

    // Store references
    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;
    isInitializedRef.current = true;

    // NOTE: Don't call fitTerminal() here - let the activation effect handle it
    // after layout is fully calculated. This avoids dimension calculation issues
    // when the container is first rendered.

    // Handle keyboard input
    terminal.onData((data: string) => {
      // If shell has exited, reconnect on any key
      // Use ref to avoid re-creating this callback when hasExited changes
      if (hasExitedRef.current) {
        setHasExited(false);
        setExitCode(null);
        connectRef.current?.();
        return;
      }

      // Send input to server
      const message: TerminalInputMessage = {
        type: "input",
        data: encodeBase64(data),
      };
      sendMessage(message);
    });

    // Handle terminal resize
    terminal.onResize(({ cols, rows }: { cols: number; rows: number }) => {
      sendResize(cols, rows);
    });
  }, [encodeBase64, sendMessage, sendResize]);

  /**
   * Handle window resize
   */
  useEffect(() => {
    if (!isActive) return;

    const handleResize = () => {
      fitTerminal();
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [isActive, fitTerminal]);

  /**
   * Initialize terminal and WebSocket when becoming active
   */
  useEffect(() => {
    if (!isActive) {
      // When becoming inactive, just clear reconnect timeout but keep WebSocket alive
      // This preserves the terminal buffer and connection for when we switch back
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      // DO NOT close WebSocket here - keep it alive to preserve buffer
      return;
    }

    // Initialize terminal if not already done
    if (!isInitializedRef.current) {
      initializeTerminal();
    }

    // Connect WebSocket if not already connected
    // Use double rAF + timeout to ensure terminal is rendered with correct dimensions
    // before connecting (the fit/refresh effect handles the actual fitting)
    let rafId1: number;
    let rafId2: number;

    const connectIfNeeded = () => {
      rafId1 = requestAnimationFrame(() => {
        rafId2 = requestAnimationFrame(() => {
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            connectRef.current?.();
          }
        });
      });
    };

    // Delay connection to ensure terminal dimensions are calculated first
    const timeoutId = window.setTimeout(connectIfNeeded, 50);

    return () => {
      clearTimeout(timeoutId);
      cancelAnimationFrame(rafId1);
      cancelAnimationFrame(rafId2);
    };
  }, [isActive, initializeTerminal]);

  /**
   * Fit and refresh terminal when isActive becomes true
   */
  useEffect(() => {
    if (isActive && terminalRef.current) {
      // Use double requestAnimationFrame to ensure:
      // 1. First rAF: style changes are committed
      // 2. Second rAF: layout is recalculated
      // This is more reliable than setTimeout for visibility changes
      let rafId1: number;
      let rafId2: number;

      const handleActivation = () => {
        rafId1 = requestAnimationFrame(() => {
          rafId2 = requestAnimationFrame(() => {
            if (terminalRef.current && fitAddonRef.current) {
              // Fit terminal to get correct dimensions
              fitTerminal();
              // Refresh the terminal to redraw content after becoming visible
              // This fixes rendering issues when switching between terminals
              terminalRef.current.refresh(0, terminalRef.current.rows - 1);
              // Focus the terminal to receive keyboard input
              terminalRef.current.focus();
            }
          });
        });
      };

      // Small initial delay to ensure React has committed the style changes
      const timeoutId = window.setTimeout(handleActivation, 16);

      return () => {
        clearTimeout(timeoutId);
        cancelAnimationFrame(rafId1);
        cancelAnimationFrame(rafId2);
      };
    }
  }, [isActive, fitTerminal]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (terminalRef.current) {
        terminalRef.current.dispose();
      }
      isInitializedRef.current = false;
    };
  }, []);

  /**
   * Reconnect when project or terminal changes
   */
  useEffect(() => {
    if (isActive && isInitializedRef.current) {
      // Only reconnect if project or terminal actually changed, not on initial activation
      // This prevents duplicate connect calls when both isActive and projectName/terminalId effects run
      if (
        lastProjectRef.current === null &&
        lastTerminalIdRef.current === null
      ) {
        // Initial activation - just track the project/terminal, don't reconnect (the isActive effect handles initial connect)
        lastProjectRef.current = projectName;
        lastTerminalIdRef.current = terminalId;
        return;
      }

      if (
        lastProjectRef.current === projectName &&
        lastTerminalIdRef.current === terminalId
      ) {
        // Nothing changed, skip
        return;
      }

      // Project or terminal changed - update tracking
      lastProjectRef.current = projectName;
      lastTerminalIdRef.current = terminalId;

      // Clear terminal and reset cursor position
      if (terminalRef.current) {
        terminalRef.current.clear();
        terminalRef.current.write("\x1b[H"); // Move cursor to home position
      }

      // Set manual close flag to prevent auto-reconnect race condition
      isManualCloseRef.current = true;

      // Close existing connection and reset connecting state
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      isConnectingRef.current = false;

      // Reset state
      setHasExited(false);
      setExitCode(null);
      reconnectAttempts.current = 0;

      // Connect to new project/terminal using ref to avoid dependency on connect callback
      connectRef.current?.();
    }
  }, [projectName, terminalId, isActive]);

  return (
    <div className="relative h-full w-full bg-zinc-950">
      {/* Connection status indicator */}
      <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            isConnected ? "bg-green-500" : "bg-destructive"
          }`}
          title={isConnected ? "Connected" : "Disconnected"}
        />
        {!isConnected && !hasExited && (
          <span className="text-xs font-mono text-muted-foreground">
            Connecting...
          </span>
        )}
        {hasExited && exitCode !== null && (
          <span className="text-xs font-mono text-yellow-500">
            Exit: {exitCode}
          </span>
        )}
      </div>

      {/* Terminal container */}
      <div
        ref={containerRef}
        className="h-full w-full p-2"
        style={{ minHeight: "100px" }}
        onClick={() => {
          // Ensure terminal gets focus when container is clicked
          terminalRef.current?.focus();
        }}
      />
    </div>
  );
}
