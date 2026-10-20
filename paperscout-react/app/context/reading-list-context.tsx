import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { apiFetch } from "~/lib/api";
import type { Article } from "~/routes/results";

// The search result fields the backend stores on the reading list.
export type SavedArticleData = Pick<
  Article,
  | "id"
  | "title"
  | "author"
  | "journal_name"
  | "publication_date"
  | "journal_publication_date"
  | "issue"
  | "doi"
  | "library_url"
  | "abstract"
  | "topic"
>;

export interface SavedArticle {
  id: number;
  article: SavedArticleData;
  isRead: boolean;
  savedAt: string;
}

interface ReadingListContextState {
  savedArticles: SavedArticle[];
  // Search result ids (bare DOIs) that are on the list.
  savedArticleIds: Set<string>;
  isLoading: boolean;
  error: string | null;
  saveArticles: (
    articles: SavedArticleData[],
  ) => Promise<{ added: number; skipped: number }>;
  updateSavedArticle: (
    savedId: number,
    changes: { isRead: boolean },
  ) => Promise<void>;
  removeSavedArticle: (savedId: number) => Promise<void>;
  removeSavedArticles: (savedIds: number[]) => Promise<void>;
}

const ReadingListContext = createContext<ReadingListContextState | undefined>(
  undefined,
);

export function ReadingListProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [savedArticles, setSavedArticles] = useState<SavedArticle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ results: SavedArticle[] }>("/api/saved-articles")
      .then((data) => setSavedArticles(data.results || []))
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "Failed to load reading list.",
        ),
      )
      .finally(() => setIsLoading(false));
  }, []);

  const savedArticleIds = useMemo(
    () => new Set(savedArticles.map((saved) => saved.article.id)),
    [savedArticles],
  );

  const saveArticles = useCallback(async (articles: SavedArticleData[]) => {
    const data = await apiFetch<{ results: SavedArticle[]; skipped: number }>(
      "/api/saved-articles",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ articles }),
      },
    );
    // Newest first, like the list the backend returns.
    setSavedArticles((prev) => [...[...data.results].reverse(), ...prev]);
    return { added: data.results.length, skipped: data.skipped };
  }, []);

  const updateSavedArticle = useCallback(
    async (savedId: number, changes: { isRead: boolean }) => {
      const updated = await apiFetch<SavedArticle>(
        `/api/saved-articles/${savedId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(changes),
        },
      );
      setSavedArticles((prev) =>
        prev.map((saved) => (saved.id === savedId ? updated : saved)),
      );
    },
    [],
  );

  const removeSavedArticle = useCallback(async (savedId: number) => {
    await apiFetch(`/api/saved-articles/${savedId}`, { method: "DELETE" });
    setSavedArticles((prev) => prev.filter((saved) => saved.id !== savedId));
  }, []);

  const removeSavedArticles = useCallback(async (savedIds: number[]) => {
    const params = new URLSearchParams(
      savedIds.map((id) => ["ids", String(id)]),
    );
    await apiFetch(`/api/saved-articles?${params}`, { method: "DELETE" });
    const removed = new Set(savedIds);
    setSavedArticles((prev) => prev.filter((saved) => !removed.has(saved.id)));
  }, []);

  const value = useMemo(
    () => ({
      savedArticles,
      savedArticleIds,
      isLoading,
      error,
      saveArticles,
      updateSavedArticle,
      removeSavedArticle,
      removeSavedArticles,
    }),
    [
      savedArticles,
      savedArticleIds,
      isLoading,
      error,
      saveArticles,
      updateSavedArticle,
      removeSavedArticle,
      removeSavedArticles,
    ],
  );

  return (
    <ReadingListContext.Provider value={value}>
      {children}
    </ReadingListContext.Provider>
  );
}

export function useReadingList() {
  const context = useContext(ReadingListContext);
  if (context === undefined) {
    throw new Error("useReadingList must be used within a ReadingListProvider");
  }
  return context;
}
