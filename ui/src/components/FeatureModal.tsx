import { useState } from "react";
import {
  X,
  CheckCircle2,
  Circle,
  SkipForward,
  Trash2,
  Loader2,
  AlertCircle,
  Pencil,
  Link2,
  AlertTriangle,
} from "lucide-react";
import {
  useSkipFeature,
  useDeleteFeature,
  useFeatures,
} from "../hooks/useProjects";
import { EditFeatureForm } from "./EditFeatureForm";
import type { Feature } from "../lib/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";

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

interface FeatureModalProps {
  feature: Feature;
  projectName: string;
  onClose: () => void;
}

export function FeatureModal({
  feature,
  projectName,
  onClose,
}: FeatureModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  const skipFeature = useSkipFeature(projectName);
  const deleteFeature = useDeleteFeature(projectName);
  const { data: allFeatures } = useFeatures(projectName);

  // Build a map of feature ID to feature for looking up dependency names
  const featureMap = new Map<number, Feature>();
  if (allFeatures) {
    [
      ...allFeatures.pending,
      ...allFeatures.in_progress,
      ...allFeatures.done,
    ].forEach((f) => {
      featureMap.set(f.id, f);
    });
  }

  // Get dependency features
  const dependencies = (feature.dependencies || [])
    .map((id) => featureMap.get(id))
    .filter((f): f is Feature => f !== undefined);

  // Get blocking dependencies (unmet dependencies)
  const blockingDeps = (feature.blocking_dependencies || [])
    .map((id) => featureMap.get(id))
    .filter((f): f is Feature => f !== undefined);

  const handleSkip = async () => {
    setError(null);
    try {
      await skipFeature.mutateAsync(feature.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to skip feature");
    }
  };

  const handleDelete = async () => {
    setError(null);
    try {
      await deleteFeature.mutateAsync(feature.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete feature");
    }
  };

  // Show edit form when in edit mode
  if (showEdit) {
    return (
      <EditFeatureForm
        feature={feature}
        projectName={projectName}
        onClose={() => setShowEdit(false)}
        onSaved={onClose}
      />
    );
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl p-0 gap-0">
        {/* Header */}
        <DialogHeader className="p-6 pb-4">
          <div className="flex items-start gap-3">
            <Badge
              className={`${getCategoryColor(feature.category)} text-white`}
            >
              {feature.category}
            </Badge>
          </div>
          <DialogTitle className="text-xl mt-2">{feature.name}</DialogTitle>
        </DialogHeader>

        <Separator />

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[60vh] overflow-y-auto">
          {/* Error Message */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="flex items-center justify-between">
                <span>{error}</span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setError(null)}
                >
                  <X size={14} />
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Status */}
          <div className="flex items-center gap-3 p-4 bg-muted rounded-lg">
            {feature.passes ? (
              <>
                <CheckCircle2 size={24} className="text-primary" />
                <span className="font-semibold text-primary">COMPLETE</span>
              </>
            ) : (
              <>
                <Circle size={24} className="text-muted-foreground" />
                <span className="font-semibold text-muted-foreground">
                  PENDING
                </span>
              </>
            )}
            <span className="ml-auto font-mono text-sm text-muted-foreground">
              Priority: #{feature.priority}
            </span>
          </div>

          {/* Description */}
          <div>
            <h3 className="font-semibold mb-2 text-sm uppercase tracking-wide text-muted-foreground">
              Description
            </h3>
            <p className="text-foreground">{feature.description}</p>
          </div>

          {/* Blocked By Warning */}
          {blockingDeps.length > 0 && (
            <Alert
              variant="destructive"
              className="border-orange-500 bg-orange-50 dark:bg-orange-950/20"
            >
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              <AlertDescription>
                <h4 className="font-semibold mb-1 text-orange-700 dark:text-orange-400">
                  Blocked By
                </h4>
                <p className="text-sm text-orange-600 dark:text-orange-300 mb-2">
                  This feature cannot start until the following dependencies are
                  complete:
                </p>
                <ul className="space-y-1">
                  {blockingDeps.map((dep) => (
                    <li
                      key={dep.id}
                      className="flex items-center gap-2 text-sm text-orange-600 dark:text-orange-300"
                    >
                      <Circle size={14} />
                      <span className="font-mono text-xs">#{dep.id}</span>
                      <span>{dep.name}</span>
                    </li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Dependencies */}
          {dependencies.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2 text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                <Link2 size={16} />
                Depends On
              </h3>
              <ul className="space-y-1">
                {dependencies.map((dep) => (
                  <li
                    key={dep.id}
                    className="flex items-center gap-2 p-2 bg-muted rounded-md text-sm"
                  >
                    {dep.passes ? (
                      <CheckCircle2 size={16} className="text-primary" />
                    ) : (
                      <Circle size={16} className="text-muted-foreground" />
                    )}
                    <span className="font-mono text-xs text-muted-foreground">
                      #{dep.id}
                    </span>
                    <span className={dep.passes ? "text-primary" : ""}>
                      {dep.name}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Steps */}
          {feature.steps.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2 text-sm uppercase tracking-wide text-muted-foreground">
                Test Steps
              </h3>
              <ol className="list-decimal list-inside space-y-2">
                {feature.steps.map((step, index) => (
                  <li key={index} className="p-3 bg-muted rounded-md text-sm">
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {/* Actions */}
        {!feature.passes && (
          <>
            <Separator />
            <DialogFooter className="p-4 bg-muted/50">
              {showDeleteConfirm ? (
                <div className="w-full space-y-4">
                  <p className="font-medium text-center">
                    Are you sure you want to delete this feature?
                  </p>
                  <div className="flex gap-3">
                    <Button
                      variant="destructive"
                      onClick={handleDelete}
                      disabled={deleteFeature.isPending}
                      className="flex-1"
                    >
                      {deleteFeature.isPending ? (
                        <Loader2 size={18} className="animate-spin" />
                      ) : (
                        "Yes, Delete"
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowDeleteConfirm(false)}
                      disabled={deleteFeature.isPending}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-3 w-full">
                  <Button
                    onClick={() => setShowEdit(true)}
                    disabled={skipFeature.isPending}
                    className="flex-1"
                  >
                    <Pencil size={18} />
                    Edit
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={handleSkip}
                    disabled={skipFeature.isPending}
                    className="flex-1"
                  >
                    {skipFeature.isPending ? (
                      <Loader2 size={18} className="animate-spin" />
                    ) : (
                      <>
                        <SkipForward size={18} />
                        Skip
                      </>
                    )}
                  </Button>
                  <Button
                    variant="destructive"
                    size="icon"
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={skipFeature.isPending}
                  >
                    <Trash2 size={18} />
                  </Button>
                </div>
              )}
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
