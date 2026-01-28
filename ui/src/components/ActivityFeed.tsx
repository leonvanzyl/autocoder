import { Activity } from "lucide-react";
import { AgentAvatar } from "./AgentAvatar";
import type { AgentMascot } from "../lib/types";
import { Card, CardContent } from "@/components/ui/card";

interface ActivityItem {
  agentName: string;
  thought: string;
  timestamp: string;
  featureId: number;
}

interface ActivityFeedProps {
  activities: ActivityItem[];
  maxItems?: number;
  showHeader?: boolean;
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function ActivityFeed({
  activities,
  maxItems = 5,
  showHeader = true,
}: ActivityFeedProps) {
  const displayedActivities = activities.slice(0, maxItems);

  if (displayedActivities.length === 0) {
    return null;
  }

  return (
    <div>
      {showHeader && (
        <div className="flex items-center gap-2 mb-2">
          <Activity size={14} className="text-muted-foreground" />
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Recent Activity
          </span>
        </div>
      )}

      <div className="space-y-2">
        {displayedActivities.map((activity) => (
          <Card
            key={`${activity.featureId}-${activity.timestamp}-${activity.thought.slice(0, 20)}`}
            className="py-1.5"
          >
            <CardContent className="p-2 flex items-start gap-2">
              <AgentAvatar
                name={activity.agentName as AgentMascot}
                state="working"
                size="sm"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="text-xs font-semibold"
                    style={{
                      color: getMascotColor(activity.agentName as AgentMascot),
                    }}
                  >
                    {activity.agentName}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    #{activity.featureId}
                  </span>
                  <span className="text-[10px] text-muted-foreground ml-auto">
                    {formatTimestamp(activity.timestamp)}
                  </span>
                </div>
                <p
                  className="text-xs text-muted-foreground truncate"
                  title={activity.thought}
                >
                  {activity.thought}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function getMascotColor(name: AgentMascot): string {
  const colors: Record<AgentMascot, string> = {
    // Original 5
    Spark: "#3B82F6",
    Fizz: "#F97316",
    Octo: "#8B5CF6",
    Hoot: "#22C55E",
    Buzz: "#EAB308",
    // Tech-inspired
    Pixel: "#EC4899",
    Byte: "#06B6D4",
    Nova: "#F43F5E",
    Chip: "#84CC16",
    Bolt: "#FBBF24",
    // Energetic
    Dash: "#14B8A6",
    Zap: "#A855F7",
    Gizmo: "#64748B",
    Turbo: "#EF4444",
    Blip: "#10B981",
    // Playful
    Neon: "#D946EF",
    Widget: "#6366F1",
    Zippy: "#F59E0B",
    Quirk: "#0EA5E9",
    Flux: "#7C3AED",
  };
  return colors[name] || "#6B7280";
}
