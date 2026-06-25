import { format } from "date-fns";
import { Suspense, useTransition } from "react";
import { Await, useLoaderData, useLocation, useNavigate } from "react-router";
import { SkeletonList } from "~/components/skeletons";

import { Badge } from "~/components/ui/badge";
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
  author: string;
};

type LoaderData = {
  articlePromise: Promise<{
    articles: Article[];
    totalCount: number;
    perPage: number;
    currentPage: number;
  }>;
  totalCount: number;
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
      articlePromise: Promise.resolve({
        articles: [],
        totalCount: 0,
        perPage: 0,
        currentPage: 1,
      }),
      totalCount: 0,
      error:
        "Keine Suchparameter gefunden. Bitte führen Sie zuerst eine Suche durch.",
    };
  }

  const articlePromise = fetch(
    `http://localhost:8000/api/articles?${paramsString}`,
  )
    .then((res) => res.json())
    .then((data) => {
      const meta = data.meta || {};
      const results = (data.results as Article[]) || [];
      return {
        articles: results,
        totalCount: meta.count || 0,
        perPage: meta.per_page || 25,
        currentPage: meta.page || 1,
      };
    });

  return { articlePromise };
}

export default function Results() {
  const { articlePromise, error } = useLoaderData<LoaderData>();
  const navigate = useNavigate();
  const location = useLocation();
  const [isPending, startTransition] = useTransition();

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
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="mb-6 flex">
        <h1 className="text-2xl font-bold">Search Results</h1>
      </div>
      <div
        className="flex flex-col flex-1 min-h-0 overflow-hidden"
        style={{ opacity: isPending ? 0.3 : 1, transition: "opacity 1s" }}
      >
        <Suspense fallback={<SkeletonList />}>
          <Await resolve={articlePromise}>
            {(resolvedData) => {
              const { articles, totalCount, perPage, currentPage } =
                resolvedData;
              const totalPages = Math.ceil(
                Math.min(totalCount, 10000) / perPage,
              );

              return (
                <>
                  <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-2">
                    {articles.length > 0 ? (
                      articles.map((article) => (
                        <div
                          key={article.id}
                          className="rounded-lg border bg-card p-6 shadow-sm"
                        >
                          <div className="[&>*]:text-muted-foreground [&>*]:text-sm flex space-x-2 mb-2">
                            <Badge variant="outline">
                              {article.journal_name}
                            </Badge>
                            <Badge variant="outline">
                              {article.author} (
                              {format(article.publication_date, "yyyy-MM")})
                            </Badge>
                            <Badge variant="outline">{article.topic}</Badge>
                          </div>

                          <h2 className="mb-2 text-xl font-semibold leading-tight">
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
                            if (
                              page === currentPage - 2 ||
                              page === currentPage + 2
                            ) {
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
                </>
              );
            }}
          </Await>
        </Suspense>
      </div>
    </div>
  );
}
