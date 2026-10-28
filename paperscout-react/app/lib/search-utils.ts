import type { DateRange } from "react-day-picker";
import isEqual from "fast-deep-equal";
import { formatDateForApi } from "./date-utils";


interface SearchParams {
  rowSelection: Record<string, boolean>;
  date: DateRange | undefined;
  searchTerm: string;
  semanticQuery?: string;
  // Without "semantic", the semantic query is left out.
  searchMode?: "keywords" | "semantic";
}

/**
 * Builds the search URL for the results page from the given parameters.
 * @param params - An object containing rowSelection, date, searchTerm and an optional semanticQuery.
 * @returns The relative URL string for the results page, e.g. /results?journal_ids=...
 */
export function buildResultsUrl({
  rowSelection,
  date,
  searchTerm,
  semanticQuery,
  searchMode,
}: SearchParams): string {
  const selectedJournalIds = Object.keys(rowSelection).filter((id) => rowSelection[id]);

  const params = new URLSearchParams();
  selectedJournalIds.forEach(id => params.append("journal_ids", id));
  // The semantic search replaces the keywords; the two don't go together.
  // Only the active field counts; an empty one searches without a query.
  if (searchMode === "semantic") {
    params.append("keywords", "");
    if (semanticQuery?.trim()) {
      params.append("semantic_query", semanticQuery.trim());
    }
  } else {
    params.append("keywords", searchTerm.trim());
  }

  if (date?.from && date?.to) {
    params.append("from_date", formatDateForApi(date.from)!);
    params.append("to_date", formatDateForApi(date.to)!);
  }

  return `/results?${params.toString()}`;
}

type Filters = Pick<SearchParams, "rowSelection" | "searchTerm" | "semanticQuery" | "searchMode">;

// The query of the active search mode; the other field doesn't count.
function activeQuery({ searchTerm, semanticQuery, searchMode }: Filters): string {
  return (searchMode === "semantic" ? semanticQuery ?? "" : searchTerm).trim();
}

/**
 * Compares the filter settings of two profiles or search states.
 * The function checks for deep equality of journal selection, search mode and
 * the query of that mode; the query of the inactive mode is ignored.
 * Profiles no longer store a date range, so the date is intentionally not compared.
 *
 * @param a The first profile or search state.
 * @param b The second profile or search state.
 * @returns `true` if the filters are identical, otherwise `false`.
 */
export function areFiltersEqual(a: Filters, b: Filters): boolean {
  return (a.searchMode ?? "keywords") === (b.searchMode ?? "keywords") &&
         activeQuery(a) === activeQuery(b) &&
         isEqual(a.rowSelection, b.rowSelection);
}