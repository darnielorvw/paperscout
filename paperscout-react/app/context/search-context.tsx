import { endOfMonth, startOfMonth } from "date-fns";
import React, { createContext, useContext, useEffect, useState } from "react";
import type { DateRange } from "react-day-picker";
import { normalizeDateRange } from "~/lib/date-utils";

interface SearchState {
  rowSelection: Record<string, boolean>;
  date: DateRange | undefined;
  searchTerm: string;
}

interface SearchContextType extends SearchState {
  setRowSelection: React.Dispatch<
    React.SetStateAction<Record<string, boolean>>
  >;
  setDate: (newDate: DateRange | undefined) => void;
  setSearchTerm: React.Dispatch<React.SetStateAction<string>>;
  isInitialized: boolean;
}

const SearchContext = createContext<SearchContextType | undefined>(undefined);

export function SearchProvider({ children }: { children: React.ReactNode }) {
  const [isInitialized, setIsInitialized] = useState(false);

  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});
  const [date, setDateState] = useState<DateRange | undefined>();
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Wrapper around setDate to ensure the time is always set to 00:00:00 UTC.
  const setDate = (newDate: DateRange | undefined) => {
    console.log(normalizeDateRange(newDate))
    setDateState(normalizeDateRange(newDate));
  };

  // Restore data from sessionStorage on first load
  useEffect(() => {
    try {
      const savedSelection = sessionStorage.getItem("ps_row_selection");
      setRowSelection(savedSelection ? JSON.parse(savedSelection) : {});

      const savedDate = sessionStorage.getItem("ps_date_range");
      if (savedDate) {
        const parsed = JSON.parse(savedDate);
        setDate(parsed);
      } else {
        const now = new Date();
        setDate({ from: startOfMonth(now), to: endOfMonth(now) });
      }

      const savedSearchTerm = sessionStorage.getItem("ps_search_term");
      setSearchTerm(savedSearchTerm || "");
    } catch (error) {
      console.error("Failed to parse from sessionStorage", error);
    } finally {
      setIsInitialized(true);
    }
  }, []);

  // Write changes back to sessionStorage
  useEffect(() => {
    if (isInitialized) {
      sessionStorage.setItem("ps_row_selection", JSON.stringify(rowSelection));
    }
  }, [rowSelection, isInitialized]);

  useEffect(() => {
    if (isInitialized) {
      sessionStorage.setItem("ps_date_range", JSON.stringify(date));
    }
  }, [date, isInitialized]);

  useEffect(() => {
    if (isInitialized) {
      sessionStorage.setItem("ps_search_term", searchTerm);
    }
  }, [searchTerm, isInitialized]);

  const value = {
    rowSelection,
    setRowSelection,
    date,
    setDate,
    searchTerm,
    setSearchTerm,
    isInitialized,
  };

  return (
    <SearchContext.Provider value={value}>{children}</SearchContext.Provider>
  );
}

export function useSearch() {
  const context = useContext(SearchContext);
  if (context === undefined) {
    throw new Error("useSearch must be used within a SearchProvider");
  }
  return context;
}
