import { Rocket, ChevronDown, ChevronUp, Activity } from "lucide-react";
import { useState } from "react";
import { AgentCard, AgentLogModal } from "./AgentCard";
import { ActivityFeed } from "./ActivityFeed";
import { OrchestratorStatusCard } from "./OrchestratorStatusCard";
import type {
  ActiveAgent,
  AgentLogEntry,
  OrchestratorStatus,
} from "../lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const ACTIVITY_COLLAPSED_KEY = "autocoder-activity-collapsed";

interface AgentMissionControlProps {
  agents: ActiveAgent[];
  orchestratorStatus: OrchestratorStatus | null;
  recentActivity: Array<{
    agentName: string;
    thought: string;
    timestamp: string;
    featureId: number;
  }>;
  isExpanded?: boolean;
  getAgentLogs?: (agentIndex: number) => AgentLogEntry[];
}

export function AgentMissionControl({
  agents,
  orchestratorStatus,
  recentActivity,
  isExpanded: defaultExpanded = true,
  getAgentLogs,
}: AgentMissionControlProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [activityCollapsed, setActivityCollapsed] = useState(() => {
    try {
      return localStorage.getItem(ACTIVITY_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });
  const [selectedAgentForLogs, setSelectedAgentForLogs] =
    useState<ActiveAgent | null>(null);

  const toggleActivityCollapsed = () => {
    const newValue = !activityCollapsed;
    setActivityCollapsed(newValue);
    try {
      localStorage.setItem(ACTIVITY_COLLAPSED_KEY, String(newValue));
    } catch {
      // localStorage not available
    }
  };

  // Don't render if no orchestrator status and no agents
  if (!orchestratorStatus && agents.length === 0) {
    return null;
  }

  return (
    <Card className="mb-6 overflow-hidden py-0">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-primary hover:bg-primary/90 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Rocket size={20} className="text-primary-foreground" />
          <span className="font-semibold text-primary-foreground uppercase tracking-wide">
            Mission Control
          </span>
          <Badge variant="secondary" className="ml-2">
            {agents.length > 0
              ? `${agents.length} ${agents.length === 1 ? "agent" : "agents"} active`
              : orchestratorStatus?.state === "initializing"
                ? "Initializing"
                : orchestratorStatus?.state === "complete"
                  ? "Complete"
                  : "Orchestrating"}
          </Badge>
        </div>
        {isExpanded ? (
          <ChevronUp size={20} className="text-primary-foreground" />
        ) : (
          <ChevronDown size={20} className="text-primary-foreground" />
        )}
      </button>

      {/* Content */}
      <div
        className={`
          transition-all duration-300 ease-out overflow-hidden
          ${isExpanded ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0"}
        `}
      >
        <CardContent className="p-4">
          {/* Orchestrator Status Card */}
          {orchestratorStatus && (
            <OrchestratorStatusCard status={orchestratorStatus} />
          )}

          {/* Agent Cards Row */}
          {agents.length > 0 && (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {agents.map((agent) => (
                <AgentCard
                  key={`agent-${agent.agentIndex}`}
                  agent={agent}
                  onShowLogs={(agentIndex) => {
                    const agentToShow = agents.find(
                      (a) => a.agentIndex === agentIndex,
                    );
                    if (agentToShow) {
                      setSelectedAgentForLogs(agentToShow);
                    }
                  }}
                />
              ))}
            </div>
          )}

          {/* Collapsible Activity Feed */}
          {recentActivity.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleActivityCollapsed}
                className="gap-2 mb-2 h-auto p-1"
              >
                <Activity size={14} className="text-muted-foreground" />
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Recent Activity
                </span>
                <span className="text-xs text-muted-foreground">
                  ({recentActivity.length})
                </span>
                {activityCollapsed ? (
                  <ChevronDown size={14} className="text-muted-foreground" />
                ) : (
                  <ChevronUp size={14} className="text-muted-foreground" />
                )}
              </Button>
              <div
                className={`
                  transition-all duration-200 ease-out overflow-hidden
                  ${activityCollapsed ? "max-h-0 opacity-0" : "max-h-[300px] opacity-100"}
                `}
              >
                <ActivityFeed
                  activities={recentActivity}
                  maxItems={5}
                  showHeader={false}
                />
              </div>
            </div>
          )}
        </CardContent>
      </div>

      {/* Log Modal */}
      {selectedAgentForLogs && getAgentLogs && (
        <AgentLogModal
          agent={selectedAgentForLogs}
          logs={getAgentLogs(selectedAgentForLogs.agentIndex)}
          onClose={() => setSelectedAgentForLogs(null)}
        />
      )}
    </Card>
  );
}
