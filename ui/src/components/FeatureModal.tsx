import { useState, useId, useEffect } from "react";
import {
  X,
  CheckCircle2,
  Circle,
  SkipForward,
  Trash2,
  Loader2,
  AlertCircle,
  Pencil,
  Plus,
  Save,
} from "lucide-react";
import {
  useSkipFeature,
  useDeleteFeature,
  useUpdateFeature,
} from "../hooks/useProjects";
import type { Feature } from "../lib/types";

interface Step {
  id: string;
  value: string;
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
  const formId = useId();
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editCategory, setEditCategory] = useState(feature.category);
  const [editName, setEditName] = useState(feature.name);
  const [editDescription, setEditDescription] = useState(feature.description);
  const [editSteps, setEditSteps] = useState<Step[]>(
    feature.steps.length > 0
      ? feature.steps.map((s, i) => ({ id: `${formId}-step-${i}`, value: s }))
      : [{ id: `${formId}-step-0`, value: "" }],
  );
  const [stepCounter, setStepCounter] = useState(feature.steps.length || 1);

  const skipFeature = useSkipFeature(projectName);
  const deleteFeature = useDeleteFeature(projectName);
  const updateFeature = useUpdateFeature(projectName);

  // Reset edit form when feature changes or edit mode is exited
  useEffect(() => {
    if (!isEditing) {
      setEditCategory(feature.category);
      setEditName(feature.name);
      setEditDescription(feature.description);
      setEditSteps(
        feature.steps.length > 0
          ? feature.steps.map((s, i) => ({
              id: `${formId}-step-${i}`,
              value: s,
            }))
          : [{ id: `${formId}-step-0`, value: "" }],
      );
      setStepCounter(feature.steps.length || 1);
    }
  }, [feature, isEditing, formId]);

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

  // Edit mode step management
  const handleAddStep = () => {
    setEditSteps([
      ...editSteps,
      { id: `${formId}-step-${stepCounter}`, value: "" },
    ]);
    setStepCounter(stepCounter + 1);
  };

  const handleRemoveStep = (id: string) => {
    setEditSteps(editSteps.filter((step) => step.id !== id));
  };

  const handleStepChange = (id: string, value: string) => {
    setEditSteps(
      editSteps.map((step) => (step.id === id ? { ...step, value } : step)),
    );
  };

  const handleSaveEdit = async () => {
    setError(null);

    // Filter out empty steps
    const filteredSteps = editSteps
      .map((s) => s.value.trim())
      .filter((s) => s.length > 0);

    try {
      await updateFeature.mutateAsync({
        featureId: feature.id,
        update: {
          category: editCategory.trim(),
          name: editName.trim(),
          description: editDescription.trim(),
          steps: filteredSteps.length > 0 ? filteredSteps : undefined,
        },
      });
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update feature");
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setError(null);
  };

  const isEditValid =
    editCategory.trim() && editName.trim() && editDescription.trim();

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-2xl p-0"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <div>
            {isEditing ? (
              <h2 className="font-display text-2xl font-bold">Edit Feature</h2>
            ) : (
              <>
                <span className="neo-badge bg-[var(--color-neo-accent)] text-white mb-2">
                  {feature.category}
                </span>
                <h2 className="font-display text-2xl font-bold">
                  {feature.name}
                </h2>
              </>
            )}
          </div>
          <button onClick={onClose} className="neo-btn neo-btn-ghost p-2">
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-3 p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
              <AlertCircle size={20} />
              <span>{error}</span>
              <button onClick={() => setError(null)} className="ml-auto">
                <X size={16} />
              </button>
            </div>
          )}

          {isEditing ? (
            /* Edit Form */
            <>
              {/* Category */}
              <div>
                <label className="block font-display font-bold mb-2 uppercase text-sm">
                  Category
                </label>
                <input
                  type="text"
                  value={editCategory}
                  onChange={(e) => setEditCategory(e.target.value)}
                  placeholder="e.g., Authentication, UI, API"
                  className="neo-input"
                  required
                />
              </div>

              {/* Name */}
              <div>
                <label className="block font-display font-bold mb-2 uppercase text-sm">
                  Feature Name
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="e.g., User login form"
                  className="neo-input"
                  required
                />
              </div>

              {/* Description */}
              <div>
                <label className="block font-display font-bold mb-2 uppercase text-sm">
                  Description
                </label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Describe what this feature should do..."
                  className="neo-input min-h-[100px] resize-y"
                  required
                />
              </div>

              {/* Steps */}
              <div>
                <label className="block font-display font-bold mb-2 uppercase text-sm">
                  Test Steps
                </label>
                <div className="space-y-2">
                  {editSteps.map((step, index) => (
                    <div key={step.id} className="flex gap-2">
                      <span className="neo-input w-12 text-center flex-shrink-0 flex items-center justify-center">
                        {index + 1}
                      </span>
                      <input
                        type="text"
                        value={step.value}
                        onChange={(e) =>
                          handleStepChange(step.id, e.target.value)
                        }
                        placeholder="Describe this step..."
                        className="neo-input flex-1"
                      />
                      {editSteps.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveStep(step.id)}
                          className="neo-btn neo-btn-ghost p-2"
                        >
                          <Trash2 size={18} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={handleAddStep}
                  className="neo-btn neo-btn-ghost mt-2 text-sm"
                >
                  <Plus size={16} />
                  Add Step
                </button>
              </div>
            </>
          ) : (
            /* Read-Only View */
            <>
              {/* Status */}
              <div className="flex items-center gap-3 p-4 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]">
                {feature.passes ? (
                  <>
                    <CheckCircle2
                      size={24}
                      className="text-[var(--color-neo-done)]"
                    />
                    <span className="font-display font-bold text-[var(--color-neo-done)]">
                      COMPLETE
                    </span>
                  </>
                ) : (
                  <>
                    <Circle
                      size={24}
                      className="text-[var(--color-neo-text-secondary)]"
                    />
                    <span className="font-display font-bold text-[var(--color-neo-text-secondary)]">
                      PENDING
                    </span>
                  </>
                )}
                <span className="ml-auto font-mono text-sm">
                  Priority: #{feature.priority}
                </span>
              </div>

              {/* Description */}
              <div>
                <h3 className="font-display font-bold mb-2 uppercase text-sm">
                  Description
                </h3>
                <p className="text-[var(--color-neo-text-secondary)]">
                  {feature.description}
                </p>
              </div>

              {/* Steps */}
              {feature.steps.length > 0 && (
                <div>
                  <h3 className="font-display font-bold mb-2 uppercase text-sm">
                    Test Steps
                  </h3>
                  <ol className="list-decimal list-inside space-y-2">
                    {feature.steps.map((step, index) => (
                      <li
                        key={index}
                        className="p-3 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]"
                      >
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </>
          )}
        </div>

        {/* Actions */}
        <div className="p-6 border-t-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          {isEditing ? (
            /* Edit Mode Actions */
            <div className="flex gap-3">
              <button
                onClick={handleSaveEdit}
                disabled={!isEditValid || updateFeature.isPending}
                className="neo-btn neo-btn-success flex-1"
              >
                {updateFeature.isPending ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <>
                    <Save size={18} />
                    Save Changes
                  </>
                )}
              </button>
              <button
                onClick={handleCancelEdit}
                disabled={updateFeature.isPending}
                className="neo-btn neo-btn-ghost"
              >
                Cancel
              </button>
            </div>
          ) : showDeleteConfirm ? (
            <div className="space-y-4">
              <p className="font-bold text-center">
                Are you sure you want to delete this feature?
                {feature.passes && (
                  <span className="block text-sm font-normal text-[var(--color-neo-text-secondary)] mt-1">
                    Note: This only removes it from tracking. The code remains.
                  </span>
                )}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={handleDelete}
                  disabled={deleteFeature.isPending}
                  className="neo-btn neo-btn-danger flex-1"
                >
                  {deleteFeature.isPending ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    "Yes, Delete"
                  )}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleteFeature.isPending}
                  className="neo-btn neo-btn-ghost flex-1"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : feature.passes ? (
            /* Completed Feature Actions - Edit and Delete only */
            <div className="flex gap-3">
              <button
                onClick={() => setIsEditing(true)}
                className="neo-btn neo-btn-primary flex-1"
              >
                <Pencil size={18} />
                Edit
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="neo-btn neo-btn-danger"
              >
                <Trash2 size={18} />
              </button>
            </div>
          ) : (
            /* Pending Feature Actions - Edit, Skip, and Delete */
            <div className="flex gap-3">
              <button
                onClick={() => setIsEditing(true)}
                disabled={skipFeature.isPending}
                className="neo-btn neo-btn-primary flex-1"
              >
                <Pencil size={18} />
                Edit
              </button>
              <button
                onClick={handleSkip}
                disabled={skipFeature.isPending}
                className="neo-btn neo-btn-warning flex-1"
              >
                {skipFeature.isPending ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <>
                    <SkipForward size={18} />
                    Skip
                  </>
                )}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                disabled={skipFeature.isPending}
                className="neo-btn neo-btn-danger"
              >
                <Trash2 size={18} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
