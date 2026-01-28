/**
 * React Query hooks for schedule data
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/api";
import type { ScheduleCreate, ScheduleUpdate } from "../lib/types";

// ============================================================================
// Schedules
// ============================================================================

/**
 * Hook to fetch all schedules for a project.
 */
export function useSchedules(projectName: string | null) {
  return useQuery({
    queryKey: ["schedules", projectName],
    queryFn: () => api.listSchedules(projectName!),
    enabled: !!projectName,
  });
}

/**
 * Hook to fetch a single schedule.
 */
export function useSchedule(
  projectName: string | null,
  scheduleId: number | null,
) {
  return useQuery({
    queryKey: ["schedule", projectName, scheduleId],
    queryFn: () => api.getSchedule(projectName!, scheduleId!),
    enabled: !!projectName && !!scheduleId,
  });
}

/**
 * Hook to create a new schedule.
 */
export function useCreateSchedule(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (schedule: ScheduleCreate) =>
      api.createSchedule(projectName, schedule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", projectName] });
      queryClient.invalidateQueries({ queryKey: ["nextRun", projectName] });
    },
  });
}

/**
 * Hook to update an existing schedule.
 */
export function useUpdateSchedule(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      scheduleId,
      update,
    }: {
      scheduleId: number;
      update: ScheduleUpdate;
    }) => api.updateSchedule(projectName, scheduleId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", projectName] });
      queryClient.invalidateQueries({ queryKey: ["nextRun", projectName] });
    },
  });
}

/**
 * Hook to delete a schedule.
 */
export function useDeleteSchedule(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scheduleId: number) =>
      api.deleteSchedule(projectName, scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", projectName] });
      queryClient.invalidateQueries({ queryKey: ["nextRun", projectName] });
    },
  });
}

/**
 * Hook to toggle a schedule's enabled state.
 */
export function useToggleSchedule(projectName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      scheduleId,
      enabled,
    }: {
      scheduleId: number;
      enabled: boolean;
    }) => api.updateSchedule(projectName, scheduleId, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules", projectName] });
      queryClient.invalidateQueries({ queryKey: ["nextRun", projectName] });
    },
  });
}

// ============================================================================
// Next Run
// ============================================================================

/**
 * Hook to fetch the next scheduled run for a project.
 * Polls every 30 seconds to keep status up-to-date.
 */
export function useNextScheduledRun(projectName: string | null) {
  return useQuery({
    queryKey: ["nextRun", projectName],
    queryFn: () => api.getNextScheduledRun(projectName!),
    enabled: !!projectName,
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}
