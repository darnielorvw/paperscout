import { Download } from "lucide-react";
import { Suspense, useState, useTransition } from "react";
import { Await, useLoaderData, useLocation, useNavigate } from "react-router";
import { ArticleCard } from "~/components/article-card";
import { ResultsPagination } from "~/components/results-pagination";
import { SkeletonList } from "~/components/skeletons";
import { Button } from "~/components/ui/button";

import { toast } from "sonner";
import { apiFetch } from "~/lib/api";
import { protectPage } from "~/lib/auth";
import type { Route } from "../+types/root";

// Definiere den Artikel-Typ basierend auf der Rückgabe der search_service.py
export type Article = {
  id: string;
  title: string;
  doi: string | null;
  publication_date: string;
  pdf_landing_page: string;
  pdf_url: string;
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
  // Schütze diese Seite: Wenn kein Token, wird hier abgebrochen und umgeleitet.
  protectPage();

  const url = new URL(request.url);
  const currentPage = parseInt(url.searchParams.get("page") || "1", 10);
  url.searchParams.set("page", currentPage.toString());

  const paramsString = url.searchParams.toString();

  // Wenn wir immer noch keine Parameter haben, können wir nichts laden.
  if (!url.searchParams.has("journal_ids")) {
    return {
      articlePromise: Promise.resolve({
        articles: [],
        totalCount: 0,
        perPage: 0,
        currentPage: 1,
      }),
      error:
        "Keine Suchparameter gefunden. Bitte führen Sie zuerst eine Suche durch.",
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

type DirectoryPickerWindow = Window &
  typeof globalThis & {
    showDirectoryPicker?: (options?: { mode: "readwrite" }) => Promise<any>;
  };

export default function Results() {
  const { articlePromise, error } = useLoaderData<LoaderData>();
  const navigate = useNavigate();
  const location = useLocation();
  const [isPending, startTransition] = useTransition();
  const [openingPdf, setOpeningPdf] = useState<Record<string, boolean>>({});
  const [selectedArticleIds, setSelectedArticleIds] = useState<Set<string>>(
    new Set(),
  );

  const getSafeFileName = (article: Article) => {
    const baseName = article.title
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9._-]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 80);

    return `${baseName || article.id}.pdf`;
  };

  const chooseDownloadDirectory = async () => {
    const pickerWindow = window as DirectoryPickerWindow;

    if (typeof window === "undefined" || !pickerWindow.showDirectoryPicker) {
      return null;
    }

    try {
      return await pickerWindow.showDirectoryPicker({ mode: "readwrite" });
    } catch {
      return null;
    }
  };

  const handleOpenPdfInNewTab = async (article: Article) => {
    if (!article.pdf_url) return;
    setOpeningPdf((prev) => ({ ...prev, [article.id]: true }));
    try {
      window.open(article.pdf_url, "_blank", "noopener,noreferrer");
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Ein unbekannter Fehler ist aufgetreten.";
      console.error("Fehler beim Öffnen der PDF:", error);
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
        if (article.pdf_url) {
          next.add(article.id);
        }
      });
      return next;
    });
  };

  const clearAllSelections = () => {
    setSelectedArticleIds(new Set());
  };

  const handleBulkDownload = async (articles: Article[]) => {
    const selectedArticles = articles.filter((article) =>
      selectedArticleIds.has(article.id),
    );

    const downloadableArticles = selectedArticles.filter(
      (article) => article.pdf_url,
    );

    if (downloadableArticles.length === 0) {
      toast.error("Keine herunterladbaren PDFs ausgewählt.", {
        position: "top-center",
      });
      return;
    }

    const workIds = downloadableArticles.map((article) => article.id).join(",");
    const titles = downloadableArticles.map((article) => article.title);
    const params = new URLSearchParams({
      work_ids: workIds,
      titles: JSON.stringify(titles),
    });

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

      toast.success(`${downloadableArticles.length} Dateien wurden als ZIP heruntergeladen.`, {
        position: "top-center",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Bulk-Download fehlgeschlagen.";
      toast.error(message, { position: "top-center" });
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
              {/* Scrollbarer Bereich für die Artikel */}
              <div
                className="flex-1 overflow-y-auto"
                style={{
                  opacity: isPending ? 0.3 : 1,
                  transition: "opacity 1s",
                }}
              >
                <div className="space-y-4 pr-2 py-4">
                  <div className="sticky top-0 z-10 flex items-center justify-between rounded-lg border bg-background/90 px-4 py-3 shadow-sm backdrop-blur">
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-muted-foreground">
                        {selectedArticleIds.size > 0
                          ? `${selectedArticleIds.size} ausgewählt`
                          : "Keine Auswahl"}
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => selectAllCurrentPage(articles)}
                        disabled={articles.length === 0}
                      >
                        Alle auf dieser Seite
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={clearAllSelections}
                        disabled={selectedArticleIds.size === 0}
                      >
                        Auswahl löschen
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => handleBulkDownload(articles)}
                      disabled={selectedArticleIds.size === 0}
                    >
                      <Download className="mr-2 h-4 w-4" />
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
