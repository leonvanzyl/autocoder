import {
  MessageCircle,
  ScrollText,
  X,
  Copy,
  Check,
  Code,
  FlaskConical,
} from "lucide-react";
import { useState } from "react";
import { createPortal } from "react-dom";
import { AgentAvatar } from "./AgentAvatar";
import type { ActiveAgent, AgentLogEntry, AgentType } from "../lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface AgentCardProps {
  agent: ActiveAgent;
  onShowLogs?: (agentIndex: number) => void;
}

// Get a friendly state description
function getStateText(state: ActiveAgent["state"]): string {
  switch (state) {
    case "idle":
      return "Standing by...";
    case "thinking":
      return "Pondering...";
    case "working":
      return "Coding away...";
    case "testing":
      return "Checking work...";
    case "success":
      return "Nailed it!";
    case "error":
      return "Trying plan B...";
    case "struggling":
      return "Being persistent...";
    default:
      return "Busy...";
  }
}

// Get state color class
function getStateColor(state: ActiveAgent["state"]): string {
  switch (state) {
    case "success":
      return "text-primary";
    case "error":
      return "text-yellow-600";
    case "struggling":
      return "text-orange-500";
    case "working":
    case "testing":
      return "text-primary";
    case "thinking":
      return "text-yellow-600";
    default:
      return "text-muted-foreground";
  }
}

// Get agent type badge config
function getAgentTypeBadge(agentType: AgentType): {
  label: string;
  className: string;
  icon: typeof Code;
} {
  if (agentType === "testing") {
    return {
      label: "TEST",
      className:
        "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
      icon: FlaskConical,
    };
  }
  return {
    label: "CODE",
    className:
      "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
    icon: Code,
  };
}

export function AgentCard({ agent, onShowLogs }: AgentCardProps) {
  const isActive = ["thinking", "working", "testing"].includes(agent.state);
  const hasLogs = agent.logs && agent.logs.length > 0;
  const typeBadge = getAgentTypeBadge(agent.agentType || "coding");
  const TypeIcon = typeBadge.icon;

  return (
    <Card
      className={`min-w-[180px] max-w-[220px] py-3 ${isActive ? "animate-pulse" : ""}`}
    >
      <CardContent className="p-3 space-y-2">
        {/* Agent type badge */}
        <div className="flex justify-end">
          <Badge
            variant="outline"
            className={`text-[10px] ${typeBadge.className}`}
          >
            <TypeIcon size={10} />
            {typeBadge.label}
          </Badge>
        </div>

        {/* Header with avatar and name */}
        <div className="flex items-center gap-2">
          <AgentAvatar name={agent.agentName} state={agent.state} size="sm" />
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-sm truncate">
              {agent.agentName}
            </div>
            <div className={`text-xs ${getStateColor(agent.state)}`}>
              {getStateText(agent.state)}
            </div>
          </div>
          {/* Log button */}
          {hasLogs && onShowLogs && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => onShowLogs(agent.agentIndex)}
              title={`View logs (${agent.logs?.length || 0} entries)`}
            >
              <ScrollText size={14} className="text-muted-foreground" />
            </Button>
          )}
        </div>

        {/* Feature info */}
        <div>
          <div className="text-xs text-muted-foreground mb-0.5">
            Feature #{agent.featureId}
          </div>
          <div
            className="text-sm font-medium truncate"
            title={agent.featureName}
          >
            {agent.featureName}
          </div>
        </div>

        {/* Thought bubble */}
        {agent.thought && (
          <div className="pt-2 border-t border-border/50">
            <div className="flex items-start gap-1.5">
              <MessageCircle
                size={14}
                className="text-primary shrink-0 mt-0.5"
              />
              <p
                className="text-xs text-muted-foreground line-clamp-2 italic"
                title={agent.thought}
              >
                {agent.thought}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Log viewer modal component
interface AgentLogModalProps {
  agent: ActiveAgent;
  logs: AgentLogEntry[];
  onClose: () => void;
}

export function AgentLogModal({ agent, logs, onClose }: AgentLogModalProps) {
  const [copied, setCopied] = useState(false);
  const typeBadge = getAgentTypeBadge(agent.agentType || "coding");
  const TypeIcon = typeBadge.icon;

  const handleCopy = async () => {
    const logText = logs
      .map((log) => `[${log.timestamp}] ${log.line}`)
      .join("\n");
    await navigator.clipboard.writeText(logText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getLogColor = (type: AgentLogEntry["type"]) => {
    switch (type) {
      case "error":
        return "text-destructive";
      case "state_change":
        return "text-primary";
      default:
        return "text-foreground";
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 flex items-center justify-center p-4 bg-black/50"
      style={{ zIndex: 9999 }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <Card className="w-full max-w-4xl max-h-[80vh] flex flex-col py-0">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-3">
            <AgentAvatar name={agent.agentName} state={agent.state} size="sm" />
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-lg">
                  {agent.agentName} Logs
                </h2>
                <Badge
                  variant="outline"
                  className={`text-[10px] ${typeBadge.className}`}
                >
                  <TypeIcon size={10} />
                  {typeBadge.label}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Feature #{agent.featureId}: {agent.featureName}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied!" : "Copy"}
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={onClose}>
              <X size={20} />
            </Button>
          </div>
        </div>

        {/* Log content */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 bg-muted/50">
          <div className="font-mono text-xs space-y-1">
            {logs.length === 0 ? (
              <p className="text-muted-foreground italic">No logs available</p>
            ) : (
              logs.map((log, idx) => (
                <div
                  key={idx}
                  className={`${getLogColor(log.type)} whitespace-pre-wrap break-all`}
                >
                  <span className="text-muted-foreground">
                    [{new Date(log.timestamp).toLocaleTimeString()}]
                  </span>{" "}
                  {log.line}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t text-xs text-muted-foreground">
          {logs.length} log entries
        </div>
      </Card>
    </div>,
    document.body,
  );
}
