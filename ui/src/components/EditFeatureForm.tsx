import { useState, useId } from "react";
import { X, Save, Plus, Trash2, Loader2, AlertCircle } from "lucide-react";
import { useUpdateFeature } from "../hooks/useProjects";
import type { Feature } from "../lib/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface Step {
  id: string;
  value: string;
}

interface EditFeatureFormProps {
  feature: Feature;
  projectName: string;
  onClose: () => void;
  onSaved: () => void;
}

export function EditFeatureForm({
  feature,
  projectName,
  onClose,
  onSaved,
}: EditFeatureFormProps) {
  const formId = useId();
  const [category, setCategory] = useState(feature.category);
  const [name, setName] = useState(feature.name);
  const [description, setDescription] = useState(feature.description);
  const [priority, setPriority] = useState(String(feature.priority));
  const [steps, setSteps] = useState<Step[]>(() =>
    feature.steps.length > 0
      ? feature.steps.map((step, i) => ({
          id: `${formId}-step-${i}`,
          value: step,
        }))
      : [{ id: `${formId}-step-0`, value: "" }],
  );
  const [error, setError] = useState<string | null>(null);
  const [stepCounter, setStepCounter] = useState(feature.steps.length || 1);

  const updateFeature = useUpdateFeature(projectName);

  const handleAddStep = () => {
    setSteps([...steps, { id: `${formId}-step-${stepCounter}`, value: "" }]);
    setStepCounter(stepCounter + 1);
  };

  const handleRemoveStep = (id: string) => {
    setSteps(steps.filter((step) => step.id !== id));
  };

  const handleStepChange = (id: string, value: string) => {
    setSteps(steps.map((step) => (step.id === id ? { ...step, value } : step)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const filteredSteps = steps
      .map((s) => s.value.trim())
      .filter((s) => s.length > 0);

    try {
      await updateFeature.mutateAsync({
        featureId: feature.id,
        update: {
          category: category.trim(),
          name: name.trim(),
          description: description.trim(),
          steps: filteredSteps,
          priority: parseInt(priority, 10),
        },
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update feature");
    }
  };

  const isValid = category.trim() && name.trim() && description.trim();

  // Check if any changes were made
  const currentSteps = steps.map((s) => s.value.trim()).filter((s) => s);
  const hasChanges =
    category.trim() !== feature.category ||
    name.trim() !== feature.name ||
    description.trim() !== feature.description ||
    parseInt(priority, 10) !== feature.priority ||
    JSON.stringify(currentSteps) !== JSON.stringify(feature.steps);

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Edit Feature</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Error Message */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="flex items-center justify-between">
                <span>{error}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setError(null)}
                >
                  <X size={14} />
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Category & Priority Row */}
          <div className="flex gap-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="category">Category</Label>
              <Input
                id="category"
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="e.g., Authentication, UI, API"
                required
              />
            </div>
            <div className="w-32 space-y-2">
              <Label htmlFor="priority">Priority</Label>
              <Input
                id="priority"
                type="number"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                min="1"
                required
              />
            </div>
          </div>

          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Feature Name</Label>
            <Input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., User login form"
              required
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what this feature should do..."
              className="min-h-[100px] resize-y"
              required
            />
          </div>

          {/* Steps */}
          <div className="space-y-2">
            <Label>Test Steps</Label>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div key={step.id} className="flex gap-2 items-center">
                  <span className="w-10 h-10 flex-shrink-0 flex items-center justify-center font-mono font-semibold text-sm border rounded-md bg-muted text-muted-foreground">
                    {index + 1}
                  </span>
                  <Input
                    type="text"
                    value={step.value}
                    onChange={(e) => handleStepChange(step.id, e.target.value)}
                    placeholder="Describe this step..."
                    className="flex-1"
                  />
                  {steps.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemoveStep(step.id)}
                    >
                      <Trash2 size={18} />
                    </Button>
                  )}
                </div>
              ))}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleAddStep}
            >
              <Plus size={16} />
              Add Step
            </Button>
          </div>

          {/* Actions */}
          <DialogFooter className="pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!isValid || !hasChanges || updateFeature.isPending}
            >
              {updateFeature.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  <Save size={18} />
                  Save Changes
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
