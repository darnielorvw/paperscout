import { Download } from "lucide-react";
import { Suspense, useEffect, useState, useTransition } from "react";
import { Await, useLoaderData, useLocation, useNavigate } from "react-router";
import { ArticleCard } from "~/components/article-card";
import { ResultsPagination } from "~/components/results-pagination";
import { SkeletonList } from "~/components/skeletons";
import { Button } from "~/components/ui/button";
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
  pdf_landing_page: string;
  pdf_url: string;
  journal_name: string;
  abstract: string;
  topic: string;
  author: string;
  has_fulltext: boolean;
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

  const articlePromise = apiFetch(`/api/articles?${paramsString}`).then(
    (data) => {
      const meta = data.meta || {};
      const results = (data.results as Article[]) || [];
      return {
        articles: results,
        totalCount: meta.count || 0,
        perPage: meta.per_page || 25,
        currentPage: meta.page || 1,
      };
    },
  );

  return { articlePromise };
}

export default function Results() {
  const { articlePromise, error } = useLoaderData<LoaderData>();
  const navigate = useNavigate();
  const location = useLocation();
  const [isPending, startTransition] = useTransition();
  const [openingPdf, setOpeningPdf] = useState<Record<string, boolean>>({});
  const [selectedArticleIds, setSelectedArticleIds] = useState<Set<string>>(
    new Set(),
  );
  const { setRowSelection, setSearchTerm, setDate, isInitialized } =
    useSearch();

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

  const handleOpenPdfInNewTab = async (article: Article) => {
    if (!article.pdf_url) return;
    setOpeningPdf((prev) => ({ ...prev, [article.id]: true }));
    try {
      window.open(article.pdf_url, "_blank", "noopener,noreferrer");
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "An unknown error occurred.";
      console.error("Error opening the PDF:", error);
      toast.error(errorMessage, { position: "top-center" });
    } finally {
      setOpeningPdf((prev) => ({ ...prev, [article.id]: false }));
    }
  };

  const handleOpenLandingPage = (url: string) => {
    window.open(url, "_blank");
  };

  const toggleSelectedArticle = (articleId: string, checked: boolean) => {
    setSelectedArticleIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(articleId);
      } else {
        next.delete(articleId);
      }
      return next;
    });
  };

  const selectAllCurrentPage = (articles: Article[]) => {
    setSelectedArticleIds((prev) => {
      const next = new Set(prev);
      articles.forEach((article) => {
        if (article.has_fulltext) {
          next.add(article.id);
        }
      });
      return next;
    });
  };

  const clearAllSelections = () => {
    setSelectedArticleIds(new Set());
  };

  const [isDownloading, setIsDownloading] = useState(false);

  const handleBulkDownload = async (articles: Article[]) => {
    const selectedArticles = articles.filter((article) =>
      selectedArticleIds.has(article.id),
    );

    if (selectedArticles.length === 0) {
      toast.error("No downloadable PDFs selected.", {
        position: "top-center",
      });
      return;
    }

    const workIds = selectedArticles.map((article) => article.id).join(",");
    const titles = selectedArticles.map((article) => article.title);
    const params = new URLSearchParams({
      work_ids: workIds,
      titles: JSON.stringify(titles),
    });

    setIsDownloading(true);
    try {
      const response = await apiFetch<Blob>(
        `/api/bulk-download?${params.toString()}`,
        {
          responseType: "blob",
        },
      );

      const objectUrl = URL.createObjectURL(response);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "papers.zip";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);

      toast.success(
        `${selectedArticles.length} Dateien wurden als ZIP heruntergeladen.`,
        {
          position: "top-center",
        },
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Bulk-Download fehlgeschlagen.";
      toast.error(message, { position: "top-center" });
    } finally {
      setIsDownloading(false);
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
                        {selectedArticleIds.size > 0
                          ? `${selectedArticleIds.size} selected`
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
                        disabled={selectedArticleIds.size === 0}
                      >
                        Clear selection
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => handleBulkDownload(articles)}
                      disabled={selectedArticleIds.size === 0 || isDownloading}
                    >
                      {isDownloading ? (
                        <Spinner data-icon="inline-start" />
                      ) : (
                        <Download />
                      )}
                      Bulk Download
                    </Button>
                  </div>

                  {articles.length > 0 ? (
                    articles.map((article) => (
                      <ArticleCard
                        key={article.id}
                        article={article}
                        openingPdf={openingPdf[article.id] || false}
                        isSelected={selectedArticleIds.has(article.id)}
                        onToggleSelect={toggleSelectedArticle}
                        onOpenPdf={handleOpenPdfInNewTab}
                        onOpenLandingPage={handleOpenLandingPage}
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
