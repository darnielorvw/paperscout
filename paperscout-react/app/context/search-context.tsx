import { endOfMonth, startOfMonth } from "date-fns";
import React, { createContext, useContext, useEffect, useState } from "react";
import type { DateRange } from "react-day-picker";

interface SearchState {
  rowSelection: Record<string, boolean>;
  date: DateRange | undefined;
  searchTerm: string;
}

interface SearchContextType extends SearchState {
  setRowSelection: React.Dispatch<
    React.SetStateAction<Record<string, boolean>>
  >;
  setDate: React.Dispatch<React.SetStateAction<DateRange | undefined>>;
  setSearchTerm: React.Dispatch<React.SetStateAction<string>>;
  isInitialized: boolean;
}

const SearchContext = createContext<SearchContextType | undefined>(undefined);

export function SearchProvider({ children }: { children: React.ReactNode }) {
  const [isInitialized, setIsInitialized] = useState(false);

  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});
  const [date, setDate] = useState<DateRange | undefined>();
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Beim ersten Laden die Daten aus dem sessionStorage wiederherstellen
  useEffect(() => {
    try {
      const savedSelection = sessionStorage.getItem("ps_row_selection");
      setRowSelection(savedSelection ? JSON.parse(savedSelection) : {});

      const savedDate = sessionStorage.getItem("ps_date_range");
      if (savedDate) {
        const parsed = JSON.parse(savedDate);
        setDate({
          from: parsed.from ? new Date(parsed.from) : undefined,
          to: parsed.to ? new Date(parsed.to) : undefined,
        });
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

  // Änderungen zurück in den sessionStorage schreiben
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
