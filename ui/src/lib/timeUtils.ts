/**
 * Time Zone Utilities
 * ====================
 *
 * Utilities for converting between UTC and local time for schedule management.
 * All times in the database are stored in UTC and displayed in the user's local timezone.
 *
 * IMPORTANT: When converting times, day boundaries may be crossed. For example:
 * - Tokyo (UTC+9) user sets 02:00 local → 17:00 UTC previous day
 * - New York (UTC-5) user sets 22:00 local → 03:00 UTC next day
 *
 * The days_of_week bitfield must be adjusted accordingly using shiftDaysForward/shiftDaysBackward.
 */

/**
 * Result of time conversion including day shift information.
 */
export interface TimeConversionResult {
  time: string;
  dayShift: -1 | 0 | 1; // -1 = previous day, 0 = same day, 1 = next day
}

/**
 * Convert "HH:MM" UTC time to user's local time.
 * @param utcTime Time string in "HH:MM" format (UTC)
 * @returns Object with local time string and day shift indicator
 */
export function utcToLocalWithDayShift(utcTime: string): TimeConversionResult {
  const [hours, minutes] = utcTime.split(":").map(Number);

  // Use a fixed reference date to calculate the shift
  const utcDate = new Date(Date.UTC(2000, 0, 15, hours, minutes, 0, 0)); // Jan 15, 2000
  const localDay = utcDate.getDate();

  let dayShift: -1 | 0 | 1 = 0;
  if (localDay === 14) dayShift = -1; // Went to previous day
  if (localDay === 16) dayShift = 1; // Went to next day

  const localHours = utcDate.getHours();
  const localMinutes = utcDate.getMinutes();

  return {
    time: `${String(localHours).padStart(2, "0")}:${String(localMinutes).padStart(2, "0")}`,
    dayShift,
  };
}

/**
 * Convert "HH:MM" UTC time to user's local time (legacy function for backwards compatibility).
 * @param utcTime Time string in "HH:MM" format (UTC)
 * @returns Time string in "HH:MM" format (local)
 */
export function utcToLocal(utcTime: string): string {
  return utcToLocalWithDayShift(utcTime).time;
}

/**
 * Convert "HH:MM" local time to UTC for storage.
 * @param localTime Time string in "HH:MM" format (local)
 * @returns Object with UTC time string and day shift indicator
 */
export function localToUTCWithDayShift(
  localTime: string,
): TimeConversionResult {
  const [hours, minutes] = localTime.split(":").map(Number);

  // Use a fixed reference date to calculate the shift
  // Set local time on Jan 15, then check UTC date
  const localDate = new Date(2000, 0, 15, hours, minutes, 0, 0); // Jan 15, 2000 local
  const utcDay = localDate.getUTCDate();

  let dayShift: -1 | 0 | 1 = 0;
  if (utcDay === 14) dayShift = -1; // UTC is previous day
  if (utcDay === 16) dayShift = 1; // UTC is next day

  const utcHours = localDate.getUTCHours();
  const utcMinutes = localDate.getUTCMinutes();

  return {
    time: `${String(utcHours).padStart(2, "0")}:${String(utcMinutes).padStart(2, "0")}`,
    dayShift,
  };
}

/**
 * Convert "HH:MM" local time to UTC for storage (legacy function for backwards compatibility).
 * @param localTime Time string in "HH:MM" format (local)
 * @returns Time string in "HH:MM" format (UTC)
 */
export function localToUTC(localTime: string): string {
  return localToUTCWithDayShift(localTime).time;
}

/**
 * Shift days_of_week bitfield forward by one day.
 * Used when UTC time is on the next day relative to local time.
 * Example: Mon(1) -> Tue(2), Sun(64) -> Mon(1)
 */
export function shiftDaysForward(bitfield: number): number {
  let shifted = 0;
  if (bitfield & 1) shifted |= 2; // Mon -> Tue
  if (bitfield & 2) shifted |= 4; // Tue -> Wed
  if (bitfield & 4) shifted |= 8; // Wed -> Thu
  if (bitfield & 8) shifted |= 16; // Thu -> Fri
  if (bitfield & 16) shifted |= 32; // Fri -> Sat
  if (bitfield & 32) shifted |= 64; // Sat -> Sun
  if (bitfield & 64) shifted |= 1; // Sun -> Mon
  return shifted;
}

/**
 * Shift days_of_week bitfield backward by one day.
 * Used when UTC time is on the previous day relative to local time.
 * Example: Tue(2) -> Mon(1), Mon(1) -> Sun(64)
 */
export function shiftDaysBackward(bitfield: number): number {
  let shifted = 0;
  if (bitfield & 1) shifted |= 64; // Mon -> Sun
  if (bitfield & 2) shifted |= 1; // Tue -> Mon
  if (bitfield & 4) shifted |= 2; // Wed -> Tue
  if (bitfield & 8) shifted |= 4; // Thu -> Wed
  if (bitfield & 16) shifted |= 8; // Fri -> Thu
  if (bitfield & 32) shifted |= 16; // Sat -> Fri
  if (bitfield & 64) shifted |= 32; // Sun -> Sat
  return shifted;
}

/**
 * Adjust days_of_week bitfield based on day shift from time conversion.
 * @param bitfield Original days_of_week bitfield
 * @param dayShift Day shift from time conversion (-1, 0, or 1)
 * @returns Adjusted bitfield
 */
export function adjustDaysForDayShift(
  bitfield: number,
  dayShift: -1 | 0 | 1,
): number {
  if (dayShift === 1) return shiftDaysForward(bitfield);
  if (dayShift === -1) return shiftDaysBackward(bitfield);
  return bitfield;
}

/**
 * Format a duration in minutes to a human-readable string.
 * @param minutes Duration in minutes
 * @returns Formatted string (e.g., "4h", "1h 30m", "30m")
 */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;

  if (hours === 0) return `${mins}m`;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
}

/**
 * Format an ISO datetime string to a human-readable next run format.
 * Uses the browser's locale settings for 12/24-hour format.
 * @param isoString ISO datetime string in UTC
 * @returns Formatted string (e.g., "22:00", "10:00 PM", "Mon 22:00")
 */
export function formatNextRun(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffHours < 24) {
    // Same day or within 24 hours - just show time
    return date.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  // Further out - show day and time
  return date.toLocaleString([], {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Format an ISO datetime string to show the end time.
 * Uses the browser's locale settings for 12/24-hour format.
 * @param isoString ISO datetime string in UTC
 * @returns Formatted string (e.g., "14:00", "2:00 PM")
 */
export function formatEndTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Day bit values for the days_of_week bitfield.
 */
export const DAY_BITS = {
  Mon: 1,
  Tue: 2,
  Wed: 4,
  Thu: 8,
  Fri: 16,
  Sat: 32,
  Sun: 64,
} as const;

/**
 * Array of days with their labels and bit values.
 */
export const DAYS = [
  { label: "Mon", bit: 1 },
  { label: "Tue", bit: 2 },
  { label: "Wed", bit: 4 },
  { label: "Thu", bit: 8 },
  { label: "Fri", bit: 16 },
  { label: "Sat", bit: 32 },
  { label: "Sun", bit: 64 },
] as const;

/**
 * Check if a day is active in a bitfield.
 * @param bitfield The days_of_week bitfield
 * @param dayBit The bit value for the day to check
 * @returns True if the day is active
 */
export function isDayActive(bitfield: number, dayBit: number): boolean {
  return (bitfield & dayBit) !== 0;
}

/**
 * Toggle a day in a bitfield.
 * @param bitfield The current days_of_week bitfield
 * @param dayBit The bit value for the day to toggle
 * @returns New bitfield with the day toggled
 */
export function toggleDay(bitfield: number, dayBit: number): number {
  return bitfield ^ dayBit;
}

/**
 * Get human-readable description of active days.
 * @param bitfield The days_of_week bitfield
 * @returns Description string (e.g., "Every day", "Weekdays", "Mon, Wed, Fri")
 */
export function formatDaysDescription(bitfield: number): string {
  if (bitfield === 127) return "Every day";
  if (bitfield === 31) return "Weekdays";
  if (bitfield === 96) return "Weekends";

  const activeDays = DAYS.filter((d) => isDayActive(bitfield, d.bit));
  return activeDays.map((d) => d.label).join(", ");
}
