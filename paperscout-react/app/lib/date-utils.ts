// app/lib/date-utils.ts

import { format, startOfDay, isValid } from "date-fns";
import type { DateRange } from "react-day-picker";

/**
 * Normalizes a single date by setting the time to 00:00:00 UTC.
 * This is the most important step to avoid timezone issues.
 * @param date The date to normalize (can be a Date object or a string).
 * @returns A new Date object normalized to the start of the day, or null on invalid input.
 */
export function normalizeToStartOfDay(date: Date | string | undefined | null): Date | null {
  if (!date) return null;
  const d = new Date(date);
  return isValid(d) ? startOfDay(d) : null;
}

/**
 * Normalizes an entire date range.
 * @param dateRange The range to normalize.
 * @returns A new DateRange with normalized dates, or undefined.
 */
export function normalizeDateRange(dateRange: DateRange | undefined): DateRange | undefined {
  if (!dateRange) return undefined;
  const from = normalizeToStartOfDay(dateRange.from);
  const to = normalizeToStartOfDay(dateRange.to);
  return { from: from ?? undefined, to: to ?? undefined };
}

/**
 * Safely formats a date for use in API calls or URL parameters.
 * @param date The date to format.
 * @returns A string in the format "yyyy-MM-dd" or undefined.
 */
export function formatDateForApi(date: Date | undefined | null): string | undefined {
  return date && isValid(date) ? format(date, "yyyy-MM-dd") : undefined;
}

/**
 * Formats a date for display in the user interface. This is the single
 * source of truth for human-readable dates across the app.
 * @param date The date to format.
 * @returns A string in the format "MMM yyyy" or an empty string.
 */
export function formatDateForDisplay(date: Date | string | undefined | null): string {
    const d = normalizeToStartOfDay(date);
    return d ? format(d, "MMM yyyy") : "";
}
