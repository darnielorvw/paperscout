import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import isEqual from "fast-deep-equal";


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
    // Die Daten aus dem sessionStorage müssen wieder in Date-Objekte umgewandelt werden
    params.append("from_date", format(new Date(date.from), "yyyy-MM-dd"));
    params.append("to_date", format(new Date(date.to), "yyyy-MM-dd"));
  }

  return `/results?${params.toString()}`;
}


/**
 * Normalisiert einen Datumsbereich, indem die Daten in ISO-Datumsstrings (YYYY-MM-DD) umgewandelt werden.
 * Dies ermöglicht einen robusten Vergleich, unabhängig davon, ob die Daten als Date-Objekte oder Strings vorliegen.
 * @param dateRange Der zu normalisierende Datumsbereich.
 * @returns Ein normalisierter Datumsbereich mit `from` und `to` als Strings oder undefined.
 */
function normalizeDateRange(dateRange: DateRange | undefined) {
  if (!dateRange) {
    return { from: undefined, to: undefined };
  }
  return {
    from: dateRange.from ? new Date(dateRange.from).toISOString().split("T")[0] : undefined,
    to: dateRange.to ? new Date(dateRange.to).toISOString().split("T")[0] : undefined,
  };
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