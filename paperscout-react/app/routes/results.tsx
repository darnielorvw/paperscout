import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { SkeletonList } from "~/components/skeletons";
import { Button } from "~/components/ui/button";

// Definiere den Artikel-Typ basierend auf der Rückgabe der search_service.py
export type Article = {
  id: string;
  title: string;
  doi: string | null;
  publication_date: string;
  journal_name: string;
  abstract: string;
};

export default function Results() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    let paramsString = searchParams.toString();

    if (!paramsString) {
      const storedParams = sessionStorage.getItem("lastSearchParams");
      if (storedParams) {
        paramsString = storedParams;
      }
    } else {
      sessionStorage.setItem("lastSearchParams", paramsString);
    }

    if (!paramsString) {
      setArticles([]);
      setError(
        "Keine Suchparameter gefunden. Bitte führen Sie zuerst eine Suche durch.",
      );
      setIsLoading(false);
      return;
    }

    async function fetchArticles() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `http://localhost:8000/api/articles?${paramsString}`,
        );

        if (!response.ok) {
          throw new Error("Fehler beim Laden der Artikel");
        }

        const data = await response.json();
        setArticles((data.results as Article[]) || []);
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setArticles([]);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    }

    fetchArticles();
  }, [searchParams]);

  return (
    <div className="flex h-full w-full flex-col p-4 md:p-8 overflow-hidden">
      <div className="mb-6 flex items-center gap-4">
        <Button variant="ghost" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Zurück
        </Button>
        <h1 className="text-2xl font-bold">Suchergebnisse</h1>
      </div>
      {error && <div className="text-destructive mb-4">{error}</div>}
      {isLoading ? (
        <SkeletonList />
      ) : (
        <div className="flex-1 overflow-y-auto space-y-4 pr-2">
          {articles.length > 0 ? (
            articles.map((article) => (
              <div
                key={article.id}
                className="rounded-lg border bg-card p-6 shadow-sm"
              >
                <div className="mb-2 text-sm text-muted-foreground">
                  {article.journal_name} • {article.publication_date}
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
    </div>
  );
}
