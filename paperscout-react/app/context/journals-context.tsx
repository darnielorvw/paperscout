import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { apiFetch } from "~/lib/api";
import type { Journal } from "~/pages/journals/columns";

interface JournalsContextState {
  journals: Journal[];
  isLoading: boolean;
  error: string | null;
  /** Refetches the journal list. Call this after an admin import or delete. */
  reloadJournals: () => Promise<void>;
}

const JournalsContext = createContext<JournalsContextState | undefined>(
  undefined,
);

/**
 * Holds the full journal list for the whole app. The list only changes when an
 * admin imports or deletes journals, so it is fetched once per session and then
 * read from context everywhere instead of being reloaded on every navigation.
 */
export function JournalsProvider({ children }: { children: React.ReactNode }) {
  const [journals, setJournals] = useState<Journal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJournals = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiFetch("/api/journals");
      setJournals((data.results as Journal[]) || []);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to fetch journals.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJournals();
  }, [fetchJournals]);

  const value = useMemo(
    () => ({ journals, isLoading, error, reloadJournals: fetchJournals }),
    [journals, isLoading, error, fetchJournals],
  );

  return (
    <JournalsContext.Provider value={value}>
      {children}
    </JournalsContext.Provider>
  );
}

export function useJournals() {
  const context = useContext(JournalsContext);
  if (context === undefined) {
    throw new Error("useJournals must be used within a JournalsProvider");
  }
  return context;
}
