// app/lib/date-utils.ts

import { format, startOfDay, isValid } from "date-fns";
import type { DateRange } from "react-day-picker";

/**
 * Normalisiert ein einzelnes Datum, indem die Uhrzeit auf 00:00:00 UTC gesetzt wird.
 * Dies ist der wichtigste Schritt, um Zeitzonenprobleme zu vermeiden.
 * @param date Das zu normalisierende Datum (kann ein Date-Objekt oder ein String sein).
 * @returns Ein neues Date-Objekt, das auf den Tagesanfang normalisiert ist, oder null bei ungültiger Eingabe.
 */
export function normalizeToStartOfDay(date: Date | string | undefined | null): Date | null {
  if (!date) return null;
  const d = new Date(date);
  return isValid(d) ? startOfDay(d) : null;
}

/**
 * Normalisiert einen gesamten Datumsbereich.
 * @param dateRange Der zu normalisierende Bereich.
 * @returns Ein neuer DateRange mit normalisierten Daten oder undefined.
 */
export function normalizeDateRange(dateRange: DateRange | undefined): DateRange | undefined {
  if (!dateRange) return undefined;
  const from = normalizeToStartOfDay(dateRange.from);
  const to = normalizeToStartOfDay(dateRange.to);
  return { from: from ?? undefined, to: to ?? undefined };
}

/**
 * Formatiert ein Datum sicher für die Verwendung in API-Aufrufen oder URL-Parametern.
 * @param date Das zu formatierende Datum.
 * @returns Ein String im Format "yyyy-MM-dd" oder undefined.
 */
export function formatDateForApi(date: Date | undefined | null): string | undefined {
  return date && isValid(date) ? format(date, "yyyy-MM-dd") : undefined;
}

/**
 * Formatiert ein Datum für die Anzeige in der Benutzeroberfläche.
 * @param date Das zu formatierende Datum.
 * @returns Ein String im Format "MMM yyyy" oder ein leerer String.
 */
export function formatDateForDisplay(date: Date | string | undefined | null): string {
    const d = normalizeToStartOfDay(date);
    return d ? format(d, "MMM yyyy") : "";
}
