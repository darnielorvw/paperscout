import { format } from "date-fns";
import type { DateRange } from "react-day-picker";

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