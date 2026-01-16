import { useId, useState } from 'react'
import { AlertCircle, Loader2, Plus, Save, Trash2, X } from 'lucide-react'
import { useUpdateFeature } from '../hooks/useProjects'
import type { Feature } from '../lib/types'

interface StepRow {
  id: string
  value: string
}

export function EditFeatureForm({
  feature,
  projectName,
  onClose,
  onSaved,
}: {
  feature: Feature
  projectName: string
  onClose: () => void
  onSaved: () => void
}) {
  const formId = useId()
  const [category, setCategory] = useState(feature.category)
  const [name, setName] = useState(feature.name)
  const [description, setDescription] = useState(feature.description)
  const [priority, setPriority] = useState(String(feature.priority))
  const [steps, setSteps] = useState<StepRow[]>(
    feature.steps.length > 0
      ? feature.steps.map((s, i) => ({ id: `${formId}-step-${i}`, value: s }))
      : [{ id: `${formId}-step-0`, value: '' }]
  )
  const [error, setError] = useState<string | null>(null)
  const updateFeature = useUpdateFeature(projectName)

  const addStep = () => setSteps((prev) => [...prev, { id: `${formId}-step-${prev.length}`, value: '' }])
  const removeStep = (id: string) => setSteps((prev) => prev.filter((s) => s.id !== id))
  const updateStep = (id: string, value: string) => setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, value } : s)))

  const currentSteps = steps.map((s) => s.value.trim()).filter(Boolean)
  const hasChanges =
    category.trim() !== feature.category ||
    name.trim() !== feature.name ||
    description.trim() !== feature.description ||
    parseInt(priority, 10) !== feature.priority ||
    JSON.stringify(currentSteps) !== JSON.stringify(feature.steps)

  const isValid = category.trim() && name.trim() && description.trim()

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await updateFeature.mutateAsync({
        featureId: feature.id,
        update: {
          category: category.trim(),
          name: name.trim(),
          description: description.trim(),
          steps: currentSteps,
          priority: parseInt(priority, 10),
        },
      })
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update feature')
    }
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div className="neo-modal w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <h2 className="font-display text-2xl font-bold">Edit Feature</h2>
          <button onClick={onClose} className="neo-btn neo-btn-ghost p-2">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={onSubmit} className="p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-3 p-4 bg-[var(--color-neo-error-bg)] text-[var(--color-neo-error-text)] border-3 border-[var(--color-neo-error-border)]">
              <AlertCircle size={20} />
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                className="ml-auto hover:opacity-70 transition-opacity"
              >
                <X size={16} />
              </button>
            </div>
          )}

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block font-display font-bold mb-2 uppercase text-sm">Category</label>
              <input value={category} onChange={(e) => setCategory(e.target.value)} className="neo-input" required />
            </div>
            <div className="w-32">
              <label className="block font-display font-bold mb-2 uppercase text-sm">Priority</label>
              <input
                type="number"
                min={1}
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="neo-input"
                required
              />
            </div>
          </div>

          <div>
            <label className="block font-display font-bold mb-2 uppercase text-sm">Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="neo-input" required />
          </div>

          <div>
            <label className="block font-display font-bold mb-2 uppercase text-sm">Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="neo-input min-h-[120px] resize-y" required />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block font-display font-bold uppercase text-sm">Steps</label>
              <button type="button" onClick={addStep} className="neo-btn neo-btn-secondary text-sm">
                <Plus size={16} />
                Add step
              </button>
            </div>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div key={step.id} className="flex gap-2 items-center">
                  <span
                    className="w-10 h-10 flex-shrink-0 flex items-center justify-center font-mono font-bold text-sm border-3 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)] text-[var(--color-neo-text-secondary)]"
                    style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                  >
                    {index + 1}
                  </span>
                  <input
                    value={step.value}
                    onChange={(e) => updateStep(step.id, e.target.value)}
                    className="neo-input flex-1"
                    placeholder="Step…"
                  />
                  <button
                    type="button"
                    className="neo-btn neo-btn-danger"
                    onClick={() => removeStep(step.id)}
                    title="Remove step"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" className="neo-btn neo-btn-ghost flex-1" onClick={onClose} disabled={updateFeature.isPending}>
              Cancel
            </button>
            <button type="submit" className="neo-btn neo-btn-primary flex-1" disabled={!isValid || !hasChanges || updateFeature.isPending}>
              {updateFeature.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  <Save size={18} />
                  Save
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

