import { Download, ExternalLinkIcon } from "lucide-react";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "~/components/ui/tooltip";
import { formatDateForDisplay } from "~/lib/date-utils";
import type { Article } from "~/routes/results";
import { Checkbox } from "./ui/checkbox";
import { Field, FieldLabel } from "./ui/field";

type ArticleCardProps = {
  article: Article;
  openingPdf: boolean;
  isSelected: boolean;
  onToggleSelect: (articleId: string, checked: boolean) => void;
  onOpenPdf: (article: Article) => void;
  onOpenLandingPage: (url: string) => void;
};

export function ArticleCard({
  article,
  openingPdf,
  isSelected,
  onToggleSelect,
  onOpenPdf,
  onOpenLandingPage,
}: ArticleCardProps) {
  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="mb-2 flex space-x-2 [&>*]:text-sm [&>*]:text-muted-foreground">
          <Field orientation="horizontal" className="w-auto">
            <Checkbox
              id={`select-${article.id}`}
              checked={isSelected}
              disabled={!article.has_fulltext}
              onCheckedChange={(checked) =>
                onToggleSelect(article.id, checked === true)
              }
            />
            <FieldLabel htmlFor={`select-${article.id}`} className="sr-only">
              Select article "{article.title}"
            </FieldLabel>
          </Field>
          <Badge variant="outline">{article.journal_name}</Badge>
          {(formatDateForDisplay(article.journal_publication_date) || article.issue) && (
            <Badge variant="outline">
              {[
                article.issue,
                formatDateForDisplay(article.journal_publication_date) &&
                  formatDateForDisplay(article.journal_publication_date),
              ]
                .filter(Boolean)
                .join(" · ")}
            </Badge>
          )}
          {article.author && (
            <Badge variant="outline">
              {article.author}
              {formatDateForDisplay(article.publication_date) &&
                ` · ${formatDateForDisplay(article.publication_date)}`}
            </Badge>
          )}

          {article.topic && <Badge variant="outline">{article.topic}</Badge>}
        </div>
        <div>
          <Tooltip>
            <TooltipTrigger asChild className="mr-2">
              <Button
                onClick={() => onOpenPdf(article)}
                size="icon"
                disabled={openingPdf || !article.pdf_url}
              >
                <Download className={openingPdf ? "animate-pulse" : ""} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Download PDF</p>
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={() => onOpenLandingPage(article.pdf_landing_page)}
                size="icon"
              >
                <ExternalLinkIcon />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Go to publisher page</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
      <h2 className="mb-2 text-xl font-semibold leading-tight">
        {article.title}
      </h2>
      <p className="text-sm text-muted-foreground">{article.abstract}</p>
    </div>
  );
}
