import type { DateRange } from "react-day-picker";
import isEqual from "fast-deep-equal";
import { formatDateForApi } from "./date-utils";


interface SearchParams {
  rowSelection: Record<string, boolean>;
  date: DateRange | undefined;
  searchTerm: string;
}

/**
 * Builds the search URL for the results page from the given parameters.
 * @param params - An object containing rowSelection, date, and searchTerm.
 * @returns The relative URL string for the results page, e.g. /results?journal_ids=...
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
 * Compares the filter settings of two profiles or search states.
 * The function checks for deep equality of journal selection and search term.
 * Profiles no longer store a date range, so the date is intentionally not compared.
 *
 * @param a The first profile or search state.
 * @param b The second profile or search state.
 * @returns `true` if the filters are identical, otherwise `false`.
 */
export function areFiltersEqual(
  a: Pick<SearchParams, "rowSelection" | "searchTerm">,
  b: Pick<SearchParams, "rowSelection" | "searchTerm">,
): boolean {
  return a.searchTerm.trim() === b.searchTerm.trim() &&
         isEqual(a.rowSelection, b.rowSelection);
}