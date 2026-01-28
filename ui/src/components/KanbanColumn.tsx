import { FeatureCard } from "./FeatureCard";
import { Plus, Sparkles, Wand2 } from "lucide-react";
import type { Feature, ActiveAgent } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface KanbanColumnProps {
  title: string;
  count: number;
  features: Feature[];
  allFeatures?: Feature[];
  activeAgents?: ActiveAgent[];
  color: "pending" | "progress" | "done";
  onFeatureClick: (feature: Feature) => void;
  onAddFeature?: () => void;
  onExpandProject?: () => void;
  showExpandButton?: boolean;
  onCreateSpec?: () => void;
  showCreateSpec?: boolean;
}

const colorMap = {
  pending: "border-t-4 border-t-muted",
  progress: "border-t-4 border-t-primary",
  done: "border-t-4 border-t-primary",
};

export function KanbanColumn({
  title,
  count,
  features,
  allFeatures = [],
  activeAgents = [],
  color,
  onFeatureClick,
  onAddFeature,
  onExpandProject,
  showExpandButton,
  onCreateSpec,
  showCreateSpec,
}: KanbanColumnProps) {
  // Create a map of feature ID to active agent for quick lookup
  const agentByFeatureId = new Map(
    activeAgents.map((agent) => [agent.featureId, agent]),
  );

  return (
    <Card className={`overflow-hidden ${colorMap[color]} py-0`}>
      {/* Header */}
      <CardHeader className="px-4 py-3 border-b flex-row items-center justify-between space-y-0">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          {title}
          <Badge variant="secondary">{count}</Badge>
        </CardTitle>
        {(onAddFeature || onExpandProject) && (
          <div className="flex items-center gap-2">
            {onAddFeature && (
              <Button
                onClick={onAddFeature}
                size="icon-sm"
                title="Add new feature (N)"
              >
                <Plus size={16} />
              </Button>
            )}
            {onExpandProject && showExpandButton && (
              <Button
                onClick={onExpandProject}
                size="icon-sm"
                variant="secondary"
                title="Expand project with AI (E)"
              >
                <Sparkles size={16} />
              </Button>
            )}
          </div>
        )}
      </CardHeader>

      {/* Cards */}
      <CardContent className="p-0">
        <div className="h-[600px] overflow-y-auto">
          <div className="p-4 space-y-3">
            {features.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {showCreateSpec && onCreateSpec ? (
                  <div className="space-y-4">
                    <p>No spec created yet</p>
                    <Button onClick={onCreateSpec}>
                      <Wand2 size={18} />
                      Create Spec with AI
                    </Button>
                  </div>
                ) : (
                  "No features"
                )}
              </div>
            ) : (
              features.map((feature, index) => (
                <div
                  key={feature.id}
                  className="animate-slide-in"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <FeatureCard
                    feature={feature}
                    onClick={() => onFeatureClick(feature)}
                    isInProgress={color === "progress"}
                    allFeatures={allFeatures}
                    activeAgent={agentByFeatureId.get(feature.id)}
                  />
                </div>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
