import { Suspense, useMemo } from "react";
import { Await, useLoaderData, useLocation, useNavigate } from "react-router";
import { SkeletonList } from "~/components/skeletons";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "~/components/ui/pagination";
import type { Route } from "../+types/root";

// Definiere den Artikel-Typ basierend auf der Rückgabe der search_service.py
export type Article = {
  id: string;
  title: string;
  doi: string | null;
  publication_date: string;
  journal_name: string;
  abstract: string;
  topic: string;
};

type LoaderData = {
  articles: Promise<Article[]>;
  totalCount: number;
  perPage: number;
  currentPage: number;
  error?: string;
};

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const url = new URL(request.url);
  const currentPage = parseInt(url.searchParams.get("page") || "1", 10);
  url.searchParams.set("page", currentPage.toString());

  const paramsString = url.searchParams.toString();

  // Wenn wir immer noch keine Parameter haben, können wir nichts laden.
  if (!url.searchParams.has("journal_ids")) {
    return {
      articles: Promise.resolve([]),
      totalCount: 0,
      perPage: 0,
      currentPage: 1,
      error:
        "Keine Suchparameter gefunden. Bitte führen Sie zuerst eine Suche durch.",
    };
  }

  // Caching-Logik
  const cachedArticlesData = sessionStorage.getItem(
    `cachedArticles_${paramsString}`,
  );
  if (cachedArticlesData) {
    try {
      const cachedData = JSON.parse(cachedArticlesData);
      const cacheTimestamp = cachedData.timestamp || 0;
      const oneDay = 24 * 60 * 60 * 1000; // 24 Stunden in Millisekunden

      // Prüfe, ob der Cache noch gültig ist (weniger als 24h alt)
      if (Date.now() - cacheTimestamp < oneDay) {
        return {
          articles: Promise.resolve(cachedData.articles),
          totalCount: cachedData.totalCount,
          perPage: cachedData.perPage,
          currentPage: cachedData.currentPage,
        };
      }
    } catch (e) {
      console.error("Fehler beim Parsen des Caches, lade neu...", e);
    }
  }

  // Cache-Miss. Wir fetchen die Daten von der API.
  const articles = fetch(`http://localhost:8000/api/articles?${paramsString}`)
    .then((res) => res.json())
    .then((data) => {
      const meta = data.meta || {};
      console.log(meta.count);
      const results = (data.results as Article[]) || [];
      const responseData = {
        articles: results,
        totalCount: meta.count || 0,
        perPage: meta.per_page || 25,
        currentPage: meta.page || 1,
      };
      // Speichere die neuen Ergebnisse zusammen mit einem Zeitstempel im Cache.
      const dataToCache = { ...responseData, timestamp: Date.now() };
      sessionStorage.setItem(
        `cachedArticles_${paramsString}`,
        JSON.stringify(dataToCache),
      );
      return responseData;
    });

  return articles;
}

export default function Results() {
  const { articles, totalCount, perPage, currentPage, error } =
    useLoaderData<LoaderData>();
  const navigate = useNavigate();
  const location = useLocation();

  const totalPages = useMemo(() => {
    // OpenAlex erlaubt maximal 10.000 Ergebnisse über die Paginierung.
    // Wir begrenzen die Gesamtanzahl, um keine unerreichbaren Seiten anzuzeigen.
    const cappedTotalCount = Math.min(totalCount, 10000);
    if (!totalCount || !perPage) return 0;
    return Math.ceil(cappedTotalCount / perPage);
  }, [totalCount, perPage]);

  const handlePageChange = (page: number) => {
    const params = new URLSearchParams(location.search);
    params.set("page", page.toString());
    navigate(`${location.pathname}?${params.toString()}`);
  };

  if (error) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
        {error}
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="mb-6 flex">
        <h1 className="text-2xl font-bold">Suchergebnisse</h1>
      </div>
      <Suspense fallback={<SkeletonList />}>
        <Await resolve={articles}>
          {(resolvedArticles: Article[]) => (
            <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-2">
              {resolvedArticles.length > 0 ? (
                resolvedArticles.map((article) => (
                  <div
                    key={article.id}
                    className="rounded-lg border bg-card p-6 shadow-sm"
                  >
                    <div className="mb-2 text-sm text-muted-foreground">
                      {article.journal_name} | {article.publication_date} |
                      topic: {article.topic}
                    </div>
                    <h2 className="mb-3 text-xl font-semibold leading-tight">
                      {article.title}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {article.abstract}
                    </p>
                  </div>
                ))
              ) : (
                <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
                  Keine Artikel gefunden.
                </div>
              )}
            </div>
          )}
        </Await>
      </Suspense>
      {totalPages > 1 && (
        <Pagination className="mt-6">
          <PaginationContent className="w-full justify-between">
            <PaginationItem>
              <PaginationPrevious
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage <= 1}
              />
            </PaginationItem>

            <div className="flex items-center justify-center gap-0.5">
              {[...Array(totalPages)].map((_, i) => {
                const page = i + 1;
                // Logik zur Anzeige der Seiten (vereinfacht)
                if (
                  page === currentPage ||
                  page <= 2 ||
                  page >= totalPages - 1 ||
                  Math.abs(currentPage - page) <= 1
                ) {
                  return (
                    <PaginationItem key={page}>
                      <PaginationLink
                        onClick={() => handlePageChange(page)}
                        isActive={currentPage === page}
                      >
                        {page}
                      </PaginationLink>
                    </PaginationItem>
                  );
                }
                if (page === currentPage - 2 || page === currentPage + 2) {
                  return <PaginationEllipsis key={page} />;
                }
                return null;
              })}
            </div>

            <PaginationItem>
              <PaginationNext
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage >= totalPages}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}
    </div>
  );
}
