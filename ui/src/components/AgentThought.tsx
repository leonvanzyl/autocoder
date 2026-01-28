import { useMemo, useState, useEffect } from "react";
import { Brain, Sparkles } from "lucide-react";
import type { AgentStatus } from "../lib/types";
import { Card } from "@/components/ui/card";

interface AgentThoughtProps {
  logs: Array<{ line: string; timestamp: string }>;
  agentStatus: AgentStatus;
}

const IDLE_TIMEOUT = 30000; // 30 seconds

/**
 * Determines if a log line is an agent "thought" (narrative text)
 * vs. tool mechanics that should be hidden
 */
function isAgentThought(line: string): boolean {
  const trimmed = line.trim();

  // Skip tool mechanics
  if (/^\[Tool:/.test(trimmed)) return false;
  if (/^\s*Input:\s*\{/.test(trimmed)) return false;
  if (/^\[(Done|Error)\]/.test(trimmed)) return false;
  if (/^\[Error\]/.test(trimmed)) return false;
  if (/^Output:/.test(trimmed)) return false;

  // Skip JSON and very short lines
  if (/^[[{]/.test(trimmed)) return false;
  if (trimmed.length < 10) return false;

  // Skip lines that are just paths or technical output
  if (/^[A-Za-z]:\\/.test(trimmed)) return false;
  if (/^\/[a-z]/.test(trimmed)) return false;

  // Keep narrative text (looks like a sentence, relaxed filter)
  return trimmed.length > 10;
}

/**
 * Extracts the latest agent thought from logs
 */
function getLatestThought(
  logs: Array<{ line: string; timestamp: string }>,
): string | null {
  // Search from most recent
  for (let i = logs.length - 1; i >= 0; i--) {
    if (isAgentThought(logs[i].line)) {
      return logs[i].line.trim();
    }
  }
  return null;
}

export function AgentThought({ logs, agentStatus }: AgentThoughtProps) {
  const thought = useMemo(() => getLatestThought(logs), [logs]);
  const [displayedThought, setDisplayedThought] = useState<string | null>(null);
  const [textVisible, setTextVisible] = useState(true);
  const [isVisible, setIsVisible] = useState(false);

  // Get last log timestamp for idle detection
  const lastLogTimestamp =
    logs.length > 0 ? new Date(logs[logs.length - 1].timestamp).getTime() : 0;

  // Determine if component should be visible
  const shouldShow = useMemo(() => {
    if (!thought) return false;
    if (agentStatus === "running") return true;
    if (agentStatus === "paused") {
      return Date.now() - lastLogTimestamp < IDLE_TIMEOUT;
    }
    return false;
  }, [thought, agentStatus, lastLogTimestamp]);

  // Animate text changes using CSS transitions
  useEffect(() => {
    if (thought !== displayedThought && thought) {
      // Fade out
      setTextVisible(false);
      // After fade out, update text and fade in
      const timeout = setTimeout(() => {
        setDisplayedThought(thought);
        setTextVisible(true);
      }, 150); // Match transition duration
      return () => clearTimeout(timeout);
    }
  }, [thought, displayedThought]);

  // Handle visibility transitions
  useEffect(() => {
    if (shouldShow) {
      setIsVisible(true);
    } else {
      // Delay hiding to allow exit animation
      const timeout = setTimeout(() => setIsVisible(false), 300);
      return () => clearTimeout(timeout);
    }
  }, [shouldShow]);

  if (!isVisible || !displayedThought) return null;

  const isRunning = agentStatus === "running";

  return (
    <div
      className={`
        transition-all duration-300 ease-out overflow-hidden
        ${shouldShow ? "opacity-100 max-h-20" : "opacity-0 max-h-0"}
      `}
    >
      <Card
        className={`relative px-4 py-3 flex items-center gap-3 ${isRunning ? "animate-pulse" : ""}`}
      >
        {/* Brain Icon with subtle glow */}
        <div className="relative shrink-0">
          <Brain size={22} className="text-primary" strokeWidth={2.5} />
          {isRunning && (
            <Sparkles
              size={10}
              className="absolute -top-1 -right-1 text-yellow-500 animate-pulse"
            />
          )}
        </div>

        {/* Thought text with fade transition */}
        <p
          className="font-mono text-sm truncate transition-all duration-150 ease-out text-foreground"
          style={{
            opacity: textVisible ? 1 : 0,
            transform: textVisible ? "translateY(0)" : "translateY(-4px)",
          }}
        >
          {displayedThought?.replace(/:$/, "")}
        </p>

        {/* Subtle running indicator bar */}
        {isRunning && (
          <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary/50">
            <div
              className="h-full bg-primary animate-pulse"
              style={{ width: "100%" }}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
