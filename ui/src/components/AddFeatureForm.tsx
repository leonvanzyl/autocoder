import { useState, useId } from "react";
import { X, Plus, Trash2, Loader2, AlertCircle } from "lucide-react";
import { useCreateFeature } from "../hooks/useProjects";
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

interface AddFeatureFormProps {
  projectName: string;
  onClose: () => void;
}

export function AddFeatureForm({ projectName, onClose }: AddFeatureFormProps) {
  const formId = useId();
  const [category, setCategory] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("");
  const [steps, setSteps] = useState<Step[]>([
    { id: `${formId}-step-0`, value: "" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [stepCounter, setStepCounter] = useState(1);

  const createFeature = useCreateFeature(projectName);

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

    // Filter out empty steps
    const filteredSteps = steps
      .map((s) => s.value.trim())
      .filter((s) => s.length > 0);

    try {
      await createFeature.mutateAsync({
        category: category.trim(),
        name: name.trim(),
        description: description.trim(),
        steps: filteredSteps,
        priority: priority ? parseInt(priority, 10) : undefined,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create feature");
    }
  };

  const isValid = category.trim() && name.trim() && description.trim();

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add Feature</DialogTitle>
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
                placeholder="Auto"
                min="1"
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
            <Label>Test Steps (Optional)</Label>
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
              disabled={!isValid || createFeature.isPending}
            >
              {createFeature.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  <Plus size={18} />
                  Create Feature
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
