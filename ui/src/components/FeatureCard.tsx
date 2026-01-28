import { CheckCircle2, Circle, Loader2, MessageCircle } from "lucide-react";
import type { Feature, ActiveAgent } from "../lib/types";
import { DependencyBadge } from "./DependencyBadge";
import { AgentAvatar } from "./AgentAvatar";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface FeatureCardProps {
  feature: Feature;
  onClick: () => void;
  isInProgress?: boolean;
  allFeatures?: Feature[];
  activeAgent?: ActiveAgent;
}

// Generate consistent color for category
function getCategoryColor(category: string): string {
  const colors = [
    "bg-pink-500",
    "bg-cyan-500",
    "bg-green-500",
    "bg-yellow-500",
    "bg-orange-500",
    "bg-purple-500",
    "bg-blue-500",
  ];

  let hash = 0;
  for (let i = 0; i < category.length; i++) {
    hash = category.charCodeAt(i) + ((hash << 5) - hash);
  }

  return colors[Math.abs(hash) % colors.length];
}

export function FeatureCard({
  feature,
  onClick,
  isInProgress,
  allFeatures = [],
  activeAgent,
}: FeatureCardProps) {
  const categoryColor = getCategoryColor(feature.category);
  const isBlocked =
    feature.blocked ||
    (feature.blocking_dependencies && feature.blocking_dependencies.length > 0);
  const hasActiveAgent = !!activeAgent;

  return (
    <Card
      onClick={onClick}
      className={`
        cursor-pointer transition-all hover:border-primary py-3
        ${isInProgress ? "animate-pulse" : ""}
        ${feature.passes ? "border-primary/50" : ""}
        ${isBlocked && !feature.passes ? "border-destructive/50 opacity-80" : ""}
        ${hasActiveAgent ? "ring-2 ring-primary ring-offset-2" : ""}
      `}
    >
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge className={`${categoryColor} text-white`}>
              {feature.category}
            </Badge>
            <DependencyBadge
              feature={feature}
              allFeatures={allFeatures}
              compact
            />
          </div>
          <span className="font-mono text-sm text-muted-foreground">
            #{feature.priority}
          </span>
        </div>

        {/* Name */}
        <h3 className="font-semibold line-clamp-2">{feature.name}</h3>

        {/* Description */}
        <p className="text-sm text-muted-foreground line-clamp-2">
          {feature.description}
        </p>

        {/* Agent working on this feature */}
        {activeAgent && (
          <div className="flex items-center gap-2 py-2 px-2 rounded-md bg-primary/10 border border-primary/30">
            <AgentAvatar
              name={activeAgent.agentName}
              state={activeAgent.state}
              size="sm"
            />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-primary">
                {activeAgent.agentName} is working on this!
              </div>
              {activeAgent.thought && (
                <div className="flex items-center gap-1 mt-0.5">
                  <MessageCircle
                    size={10}
                    className="text-muted-foreground shrink-0"
                  />
                  <p className="text-[10px] text-muted-foreground truncate italic">
                    {activeAgent.thought}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Status */}
        <div className="flex items-center gap-2 text-sm">
          {isInProgress ? (
            <>
              <Loader2 size={16} className="animate-spin text-primary" />
              <span className="text-primary font-medium">Processing...</span>
            </>
          ) : feature.passes ? (
            <>
              <CheckCircle2 size={16} className="text-primary" />
              <span className="text-primary font-medium">Complete</span>
            </>
          ) : isBlocked ? (
            <>
              <Circle size={16} className="text-destructive" />
              <span className="text-destructive">Blocked</span>
            </>
          ) : (
            <>
              <Circle size={16} className="text-muted-foreground" />
              <span className="text-muted-foreground">Pending</span>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
