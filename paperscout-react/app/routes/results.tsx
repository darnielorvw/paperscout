import { BookmarkPlusIcon } from "lucide-react";
import { Suspense, useEffect, useRef, useState, useTransition } from "react";
import {
  Await,
  useLoaderData,
  useLocation,
  useNavigate
} from "react-router";
import { ArticleCard, MetaItem } from "~/components/article-card";
import { ResultsPagination } from "~/components/results-pagination";
import { SkeletonList } from "~/components/skeletons";
import { Button } from "~/components/ui/button";
import { Checkbox } from "~/components/ui/checkbox";
import { Field, FieldLabel } from "~/components/ui/field";
import { useReadingList } from "~/context/reading-list-context";
import { useSearch } from "~/context/search-context";

import { toast } from "sonner";
import { Spinner } from "~/components/ui/spinner";
import { apiFetch } from "~/lib/api";
import { protectPage } from "~/lib/auth";
import type { Route } from "../+types/root";

// Define the article type based on the return value of search_service.py
export type Article = {
  id: string;
  title: string;
  doi: string | null;
  publication_date: string;
  journal_publication_date: string | null;
  issue: string | null;
  library_url: string | null;
  journal_name: string;
  abstract: string;
  topic: string;
  author: string;
};

type LoaderData = {
  articlePromise: Promise<{
    articles: Article[];
    totalCount: number;
    perPage: number;
    currentPage: number;
  }>;
  error?: string;
};

export function clientLoader({ request }: Route.ClientLoaderArgs): LoaderData {
  // Protect this page: if there's no token, execution stops here and redirects.
  protectPage();

  const url = new URL(request.url);
  const currentPage = parseInt(url.searchParams.get("page") || "1", 10);
  url.searchParams.set("page", currentPage.toString());

  const paramsString = url.searchParams.toString();

  // If we still have no parameters, we can't load anything.
  if (!url.searchParams.has("journal_ids")) {
    return {
      articlePromise: Promise.resolve({
        articles: [],
        totalCount: 0,
        perPage: 0,
        currentPage: 1,
      }),
      error: "No search parameters found. Please run a search first.",
    };
  }

  const articlePromise = apiFetch<{
    meta?: { count?: number; per_page?: number; page?: number };
    results?: Article[];
  }>(`/api/articles?${paramsString}`).then((data) => {
    const meta = data.meta || {};
    const results = data.results || [];
    return {
      articles: results,
      totalCount: meta.count || 0,
      perPage: meta.per_page || 25,
      currentPage: meta.page || 1,
    };
  });

  return { articlePromise };
}

// Selection checkbox of a result; once saved, it links to the reading list instead.
function SelectForReadingList({
  article,
  isSaved,
  isSelected,
  onToggle,
}: {
  article: Article;
  isSaved: boolean;
  isSelected: boolean;
  onToggle: (article: Article, checked: boolean) => void;
}) {
  if (isSaved) {
    return <MetaItem label="Reading list">On your reading list</MetaItem>;
  }
  return (
    <MetaItem label="Select">
      <Field orientation="horizontal" className="mt-1 w-auto">
        <Checkbox
          id={`select-${article.id}`}
          checked={isSelected}
          onCheckedChange={(checked) => onToggle(article, checked === true)}
        />
        <FieldLabel
          htmlFor={`select-${article.id}`}
          className="font-normal text-muted-foreground"
        >
          Mark for reading list
        </FieldLabel>
      </Field>
    </MetaItem>
  );
}

export default function Results() {
  const { articlePromise, error } = useLoaderData<LoaderData>();
  const navigate = useNavigate();
  const location = useLocation();
  const [isPending, startTransition] = useTransition();
  const [selectedArticles, setSelectedArticles] = useState<
    Map<string, Article>
  >(new Map());
  const [isSaving, setIsSaving] = useState(false);
  const { savedArticleIds, saveArticles } = useReadingList();
  const { setRowSelection, setSearchTerm, setDate, isInitialized } =
    useSearch();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // The list scrolls in its own container, which <ScrollRestoration> (window
  // only) doesn't reset; so a new page or search would open where the last one
  // was scrolled to. Jump back to the top once its articles have arrived.
  useEffect(() => {
    let cancelled = false;
    Promise.resolve(articlePromise).then(
      () => {
        if (!cancelled) scrollAreaRef.current?.scrollTo({ top: 0 });
      },
      () => {},
    );
    return () => {
      cancelled = true;
    };
  }, [articlePromise]);

  // Sync the search context (journal dropdown, search term, date range) with the
  // URL params, so a shared or bookmarked results link shows the same selection
  // in the app UI as it does in the fetched results.
  useEffect(() => {
    // Wait for the context to finish restoring from sessionStorage, otherwise
    // that restore runs after this effect and overwrites the URL-derived state.
    if (!isInitialized) return;

    const params = new URLSearchParams(location.search);
    const journalIds = params.getAll("journal_ids");
    if (journalIds.length === 0) return;

    setRowSelection(Object.fromEntries(journalIds.map((id) => [id, true])));
    setSearchTerm(params.get("keywords") || "");

    const from = params.get("from_date");
    const to = params.get("to_date");
    if (from && to) {
      setDate({ from: new Date(from), to: new Date(to) });
    }
    // Only re-sync when the query string itself changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, isInitialized]);

  // Selection is kept across pages, so it stores the articles themselves.
  // Articles already on the reading list can't be selected.
  const toggleSelectedArticle = (article: Article, checked: boolean) => {
    setSelectedArticles((prev) => {
      const next = new Map(prev);
      if (checked && !savedArticleIds.has(article.id)) {
        next.set(article.id, article);
      } else {
        next.delete(article.id);
      }
      return next;
    });
  };

  const selectAllCurrentPage = (articles: Article[]) => {
    setSelectedArticles((prev) => {
      const next = new Map(prev);
      articles.forEach((article) => {
        if (!savedArticleIds.has(article.id)) {
          next.set(article.id, article);
        }
      });
      return next;
    });
  };

  const clearAllSelections = () => {
    setSelectedArticles(new Map());
  };

  const handleSaveSelected = async () => {
    setIsSaving(true);
    try {
      const { added, skipped } = await saveArticles([
        ...selectedArticles.values(),
      ]);
      setSelectedArticles(new Map());
      toast.success(
        `${added} ${added === 1 ? "paper" : "papers"} added to your reading list` +
          (skipped > 0 ? ` (${skipped} already on it).` : "."),
        { position: "top-center" },
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not save the papers.",
        { position: "top-center" },
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handlePageChange = (page: number) => {
    startTransition(() => {
      const params = new URLSearchParams(location.search);
      params.set("page", page.toString());
      navigate(`${location.pathname}?${params.toString()}`);
    });
  };

  if (error) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
        {error}
      </div>
    );
  }

  return (
    <Suspense fallback={<SkeletonList />}>
      <Await resolve={articlePromise}>
        {(resolvedData) => {
          const { articles, totalCount, perPage, currentPage } = resolvedData;
          const totalPages = Math.ceil(Math.min(totalCount, 10000) / perPage);

          return (
            <div className="flex h-full w-full flex-col overflow-hidden">
              {/* Scrollable area for the articles */}
              <div
                ref={scrollAreaRef}
                className="flex-1 overflow-y-auto"
                style={{
                  opacity: isPending ? 0.3 : 1,
                  transition: "opacity 1s",
                }}
              >
                <div className="space-y-4 pt-4 pr-2">
                  <div className="sticky top-2 z-10 flex items-center justify-between rounded-lg border bg-background/80 px-4 py-3 shadow-sm backdrop-blur">
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-muted-foreground">
                        {selectedArticles.size > 0
                          ? `${selectedArticles.size} selected`
                          : "Nothing selected"}
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => selectAllCurrentPage(articles)}
                        disabled={articles.length === 0}
                      >
                        Select all elements on this page
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={clearAllSelections}
                        disabled={selectedArticles.size === 0}
                      >
                        Clear selection
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      onClick={handleSaveSelected}
                      disabled={selectedArticles.size === 0 || isSaving}
                    >
                      {isSaving ? (
                        <Spinner data-icon="inline-start" />
                      ) : (
                        <BookmarkPlusIcon />
                      )}
                      Save to reading list
                    </Button>
                  </div>

                  {articles.length > 0 ? (
                    articles.map((article) => (
                      <ArticleCard
                        key={article.id}
                        article={article}
                        leftTop={
                          <SelectForReadingList
                            article={article}
                            isSaved={savedArticleIds.has(article.id)}
                            isSelected={selectedArticles.has(article.id)}
                            onToggle={toggleSelectedArticle}
                          />
                        }
                      />
                    ))
                  ) : (
                    <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
                      Keine Artikel gefunden.
                    </div>
                  )}
                </div>
              </div>

              <ResultsPagination
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={handlePageChange}
              />
            </div>
          );
        }}
      </Await>
    </Suspense>
  );
}
