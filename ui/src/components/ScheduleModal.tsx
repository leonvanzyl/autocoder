/**
 * Schedule Modal Component
 *
 * Modal for managing agent schedules (create, edit, delete).
 */

import { useState, useEffect, useRef } from "react";
import { Clock, GitBranch, Trash2 } from "lucide-react";
import {
  useSchedules,
  useCreateSchedule,
  useDeleteSchedule,
  useToggleSchedule,
} from "../hooks/useSchedules";
import {
  utcToLocalWithDayShift,
  localToUTCWithDayShift,
  adjustDaysForDayShift,
  formatDuration,
  DAYS,
  isDayActive,
  toggleDay,
} from "../lib/timeUtils";
import type { ScheduleCreate } from "../lib/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";

interface ScheduleModalProps {
  projectName: string;
  isOpen: boolean;
  onClose: () => void;
}

export function ScheduleModal({
  projectName,
  isOpen,
  onClose,
}: ScheduleModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const firstFocusableRef = useRef<HTMLButtonElement>(null);

  // Queries and mutations
  const { data: schedulesData, isLoading } = useSchedules(projectName);
  const createSchedule = useCreateSchedule(projectName);
  const deleteSchedule = useDeleteSchedule(projectName);
  const toggleSchedule = useToggleSchedule(projectName);

  // Form state for new schedule
  const [newSchedule, setNewSchedule] = useState<ScheduleCreate>({
    start_time: "22:00",
    duration_minutes: 240,
    days_of_week: 31, // Weekdays by default
    enabled: true,
    yolo_mode: false,
    model: null,
    max_concurrency: 3,
  });

  const [error, setError] = useState<string | null>(null);

  // Focus trap
  useEffect(() => {
    if (isOpen && firstFocusableRef.current) {
      firstFocusableRef.current.focus();
    }
  }, [isOpen]);

  const schedules = schedulesData?.schedules || [];

  const handleCreateSchedule = async () => {
    try {
      setError(null);

      // Validate
      if (newSchedule.days_of_week === 0) {
        setError("Please select at least one day");
        return;
      }

      // Validate duration
      if (
        newSchedule.duration_minutes < 1 ||
        newSchedule.duration_minutes > 1440
      ) {
        setError("Duration must be between 1 and 1440 minutes");
        return;
      }

      // Convert local time to UTC and get day shift
      const { time: utcTime, dayShift } = localToUTCWithDayShift(
        newSchedule.start_time,
      );

      // Adjust days_of_week based on day shift
      const adjustedDays = adjustDaysForDayShift(
        newSchedule.days_of_week,
        dayShift,
      );

      const scheduleToCreate = {
        ...newSchedule,
        start_time: utcTime,
        days_of_week: adjustedDays,
      };

      await createSchedule.mutateAsync(scheduleToCreate);

      // Reset form
      setNewSchedule({
        start_time: "22:00",
        duration_minutes: 240,
        days_of_week: 31,
        enabled: true,
        yolo_mode: false,
        model: null,
        max_concurrency: 3,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create schedule",
      );
    }
  };

  const handleToggleSchedule = async (scheduleId: number, enabled: boolean) => {
    try {
      setError(null);
      await toggleSchedule.mutateAsync({ scheduleId, enabled: !enabled });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to toggle schedule",
      );
    }
  };

  const handleDeleteSchedule = async (scheduleId: number) => {
    if (!confirm("Are you sure you want to delete this schedule?")) return;

    try {
      setError(null);
      await deleteSchedule.mutateAsync(scheduleId);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete schedule",
      );
    }
  };

  const handleToggleDay = (dayBit: number) => {
    setNewSchedule((prev) => ({
      ...prev,
      days_of_week: toggleDay(prev.days_of_week, dayBit),
    }));
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        ref={modalRef}
        className="sm:max-w-[650px] max-h-[80vh] flex flex-col p-0"
      >
        {/* Header */}
        <DialogHeader className="p-6 pb-4">
          <DialogTitle className="flex items-center gap-2">
            <Clock size={24} className="text-primary" />
            Agent Schedules
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto px-6">
          {/* Error display */}
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Loading state */}
          {isLoading && (
            <div className="text-center py-8 text-muted-foreground">
              Loading schedules...
            </div>
          )}

          {/* Existing schedules */}
          {!isLoading && schedules.length > 0 && (
            <div className="space-y-3 mb-6">
              {schedules.map((schedule) => {
                // Convert UTC time to local and get day shift for display
                const { time: localTime, dayShift } = utcToLocalWithDayShift(
                  schedule.start_time,
                );
                const duration = formatDuration(schedule.duration_minutes);
                const displayDays = adjustDaysForDayShift(
                  schedule.days_of_week,
                  dayShift,
                );

                return (
                  <Card key={schedule.id}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          {/* Time and duration */}
                          <div className="flex items-baseline gap-2 mb-2">
                            <span className="text-lg font-semibold">
                              {localTime}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              for {duration}
                            </span>
                          </div>

                          {/* Days */}
                          <div className="flex gap-1 mb-2">
                            {DAYS.map((day) => {
                              const isActive = isDayActive(
                                displayDays,
                                day.bit,
                              );
                              return (
                                <span
                                  key={day.label}
                                  className={`text-xs px-2 py-1 rounded border ${
                                    isActive
                                      ? "border-primary bg-primary text-primary-foreground font-medium"
                                      : "border-border text-muted-foreground"
                                  }`}
                                >
                                  {day.label}
                                </span>
                              );
                            })}
                          </div>

                          {/* Metadata */}
                          <div className="flex gap-3 text-xs text-muted-foreground">
                            {schedule.yolo_mode && (
                              <span className="font-semibold text-yellow-600">
                                YOLO mode
                              </span>
                            )}
                            <span className="flex items-center gap-1">
                              <GitBranch size={12} />
                              {schedule.max_concurrency}x
                            </span>
                            {schedule.model && (
                              <span>Model: {schedule.model}</span>
                            )}
                            {schedule.crash_count > 0 && (
                              <span className="text-destructive">
                                Crashes: {schedule.crash_count}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2">
                          {/* Enable/disable toggle */}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              handleToggleSchedule(
                                schedule.id,
                                schedule.enabled,
                              )
                            }
                            disabled={toggleSchedule.isPending}
                            className={
                              schedule.enabled
                                ? "text-primary"
                                : "text-muted-foreground"
                            }
                          >
                            {schedule.enabled ? "Enabled" : "Disabled"}
                          </Button>

                          {/* Delete button */}
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => handleDeleteSchedule(schedule.id)}
                            disabled={deleteSchedule.isPending}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 size={16} />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Empty state */}
          {!isLoading && schedules.length === 0 && (
            <div className="text-center py-6 text-muted-foreground mb-6">
              <Clock size={48} className="mx-auto mb-2 opacity-50" />
              <p>No schedules configured yet</p>
            </div>
          )}

          <Separator className="my-6" />

          {/* Add new schedule form */}
          <div className="pb-6">
            <h3 className="text-lg font-semibold mb-4">Add New Schedule</h3>

            {/* Time and duration */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="space-y-2">
                <Label>Start Time (Local)</Label>
                <Input
                  type="time"
                  value={newSchedule.start_time}
                  onChange={(e) =>
                    setNewSchedule((prev) => ({
                      ...prev,
                      start_time: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Duration (minutes)</Label>
                <Input
                  type="number"
                  min="1"
                  max="1440"
                  value={newSchedule.duration_minutes}
                  onChange={(e) => {
                    const parsed = parseInt(e.target.value, 10);
                    const value = isNaN(parsed)
                      ? 1
                      : Math.max(1, Math.min(1440, parsed));
                    setNewSchedule((prev) => ({
                      ...prev,
                      duration_minutes: value,
                    }));
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  {formatDuration(newSchedule.duration_minutes)}
                </p>
              </div>
            </div>

            {/* Days of week */}
            <div className="mb-4 space-y-2">
              <Label>Days</Label>
              <div className="flex gap-2">
                {DAYS.map((day) => {
                  const isActive = isDayActive(
                    newSchedule.days_of_week,
                    day.bit,
                  );
                  return (
                    <Button
                      key={day.label}
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      onClick={() => handleToggleDay(day.bit)}
                    >
                      {day.label}
                    </Button>
                  );
                })}
              </div>
            </div>

            {/* YOLO mode toggle */}
            <div className="mb-4 flex items-center space-x-2">
              <Checkbox
                id="yolo-mode"
                checked={newSchedule.yolo_mode}
                onCheckedChange={(checked) =>
                  setNewSchedule((prev) => ({
                    ...prev,
                    yolo_mode: checked === true,
                  }))
                }
              />
              <Label htmlFor="yolo-mode" className="font-normal">
                YOLO Mode (skip testing)
              </Label>
            </div>

            {/* Concurrency slider */}
            <div className="mb-4 space-y-2">
              <Label>Concurrent Agents (1-5)</Label>
              <div className="flex items-center gap-3">
                <GitBranch
                  size={16}
                  className={
                    newSchedule.max_concurrency > 1
                      ? "text-primary"
                      : "text-muted-foreground"
                  }
                />
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={newSchedule.max_concurrency}
                  onChange={(e) =>
                    setNewSchedule((prev) => ({
                      ...prev,
                      max_concurrency: Number(e.target.value),
                    }))
                  }
                  className="flex-1 h-2 accent-primary cursor-pointer"
                />
                <span className="text-sm font-medium min-w-[2rem] text-center">
                  {newSchedule.max_concurrency}x
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Run {newSchedule.max_concurrency} agent
                {newSchedule.max_concurrency > 1 ? "s" : ""} in parallel for
                faster feature completion
              </p>
            </div>

            {/* Model selection (optional) */}
            <div className="mb-4 space-y-2">
              <Label>Model (optional, defaults to global setting)</Label>
              <Input
                placeholder="e.g., claude-3-5-sonnet-20241022"
                value={newSchedule.model || ""}
                onChange={(e) =>
                  setNewSchedule((prev) => ({
                    ...prev,
                    model: e.target.value || null,
                  }))
                }
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <DialogFooter className="p-6 pt-4 border-t">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            onClick={handleCreateSchedule}
            disabled={
              createSchedule.isPending || newSchedule.days_of_week === 0
            }
          >
            {createSchedule.isPending ? "Creating..." : "Create Schedule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
