import type { DateRange } from "react-day-picker";
import isEqual from "fast-deep-equal";
import { formatDateForApi, normalizeDateRange } from "./date-utils";


interface SearchParams {
  rowSelection: Record<string, boolean>;
  date: DateRange | undefined;
  searchTerm: string;
}

/**
 * Baut die Such-URL für die Ergebnisseite aus den übergebenen Parametern.
 * @param params - Ein Objekt, das rowSelection, date und searchTerm enthält.
 * @returns Den relativen URL-String für die Ergebnisseite, z.B. /results?journal_ids=...
 */
export function buildResultsUrl({
  rowSelection,
  date,
  searchTerm,
}: SearchParams): string {
  const selectedJournalIds = Object.keys(rowSelection).filter((id) => rowSelection[id]);

  const params = new URLSearchParams();
  selectedJournalIds.forEach(id => params.append("journal_ids", id));
  params.append("keywords", searchTerm.trim());

  if (date?.from && date?.to) {
    params.append("from_date", formatDateForApi(date.from)!);
    params.append("to_date", formatDateForApi(date.to)!);
  }

  return `/results?${params.toString()}`;
}

/**
 * Vergleicht die Filtereinstellungen von zwei Profilen oder Suchzuständen.
 * Die Funktion prüft auf tiefe Gleichheit der Journal-Auswahl, des Datumsbereichs und des Suchbegriffs.
 *
 * @param a Das erste Profil oder der erste Suchzustand.
 * @param b Das zweite Profil oder der zweite Suchzustand.
 * @returns `true`, wenn die Filter identisch sind, andernfalls `false`.
 */
export function areFiltersEqual(a: SearchParams, b: SearchParams): boolean {
  return a.searchTerm.trim() === b.searchTerm.trim() &&
         isEqual(normalizeDateRange(a.date), normalizeDateRange(b.date)) &&
         isEqual(a.rowSelection, b.rowSelection);
}