import { format } from "date-fns";
import { Download, ExternalLinkIcon } from "lucide-react";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "~/components/ui/tooltip";
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
              onCheckedChange={(checked) =>
                onToggleSelect(article.id, checked === true)
              }
            />
            <FieldLabel htmlFor={`select-${article.id}`} className="sr-only">
              Artikel „{article.title}" auswählen
            </FieldLabel>
          </Field>
          <Badge variant="outline">{article.journal_name}</Badge>
          <Badge variant="outline">
            {article.author} ({format(article.publication_date, "yyyy-MM")})
          </Badge>
          <Badge variant="outline">{article.topic}</Badge>
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
              <p>Zur Verlagsseite</p>
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
