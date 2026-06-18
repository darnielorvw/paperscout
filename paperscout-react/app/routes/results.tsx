import { ArrowLeft } from "lucide-react";
import { Suspense } from "react";
import { Await, useLoaderData, useNavigate } from "react-router";
import { SkeletonList } from "~/components/skeletons";
import { Button } from "~/components/ui/button";
import type { Route } from "../+types/root";

// Definiere den Artikel-Typ basierend auf der Rückgabe der search_service.py
export type Article = {
  id: string;
  title: string;
  doi: string | null;
  publication_date: string;
  journal_name: string;
  abstract: string;
  cited_by_count: number;
};
export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const url = new URL(request.url);
  let params = url.searchParams;

  let paramsString = params.toString();

  if (!paramsString) {
    const storedParams = sessionStorage.getItem("lastSearchParams");
    if (storedParams) {
      params = new URLSearchParams(storedParams);

      paramsString = storedParams;
    }
  } else {
    sessionStorage.setItem("lastSearchParams", paramsString);
  }

  if (!paramsString) {
    return {
      articles: [],
      error:
        "Keine Suchparameter gefunden. Bitte führen Sie zuerst eine Suche durch.",
    };
  }

  const articles = fetch(`http://localhost:8000/api/articles?${paramsString}`)
    .then((response) => {
      if (!response.ok) throw new Error("Fehler beim Laden der Artikel");
      return response.json();
    })
    .then((data) => {
      console.log(data);
      return (data.results as Article[]) || [];
    });

  return { articles };
}

export default function Results() {
  const { articles } = useLoaderData();
  const navigate = useNavigate();

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="mb-6 flex items-center gap-4">
        <Button variant="ghost" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Zurück
        </Button>
        <h1 className="text-2xl font-bold">Suchergebnisse</h1>
      </div>
      <Suspense fallback={<SkeletonList />}>
        <Await resolve={articles}>
          {(resolvedArticles: Article[]) => (
            <div className="flex-1 overflow-y-auto space-y-4 pr-2">
              {resolvedArticles.length > 0 ? (
                resolvedArticles.map((article) => (
                  <div
                    key={article.id}
                    className="rounded-lg border bg-card p-6 shadow-sm"
                  >
                    <div className="mb-2 text-sm text-muted-foreground">
                      {article.journal_name} | {article.publication_date} | cited by: {article.cited_by_count}
                    </div>
                    <h2 className="mb-3 text-xl font-semibold leading-tight">
                      {article.title}
                    </h2>
                    <p className="text-sm text-muted-foreground line-clamp-4">
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
    </div>
  );
}
