import { ChevronDown, Download, ExternalLinkIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { formatDateForDisplay } from "~/lib/date-utils";
import { cn } from "~/lib/utils";
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

// Fallback when the meta column is not beside the abstract (stacked layout).
const DEFAULT_CLAMP_LINES = 6;

const actionLinkClass =
  "inline-flex items-center gap-1.5 text-muted-foreground underline-offset-2 hover:text-foreground hover:underline disabled:pointer-events-none disabled:opacity-50";

type MetaField = {
  label: string;
  description: string;
  value: React.ReactNode;
};

function MetaItem({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="font-medium text-foreground" title={description}>
        {label}
      </dt>
      <dd className="text-muted-foreground">{children}</dd>
    </div>
  );
}

function buildMetaFields(article: Article): MetaField[] {
  const fields: MetaField[] = [
    {
      label: "Journal",
      description: "The journal the article was published in",
      value: article.journal_name,
    },
    {
      label: "Issue",
      description: "Issue or volume of the journal",
      value: article.issue,
    },
    {
      label: "Published (journal)",
      description: "Date the article was published in the journal",
      value: formatDateForDisplay(article.journal_publication_date),
    },
    {
      label: "Author",
      description: "First author of the article",
      value: article.author,
    },
    {
      label: "Indexed",
      description: "Date the article was added to the index",
      value: formatDateForDisplay(article.publication_date),
    },
    {
      label: "Topic",
      description: "Automatically assigned subject area",
      value: article.topic,
    },
    {
      label: "DOI",
      description: "Digital Object Identifier",
      value: article.doi,
    },
  ];

  return fields.filter((field) => field.value);
}

export function ArticleCard({
  article,
  openingPdf,
  isSelected,
  onToggleSelect,
  onOpenPdf,
  onOpenLandingPage,
}: ArticleCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const abstractRef = useRef<HTMLParagraphElement>(null);
  const metaRef = useRef<HTMLDListElement>(null);

  // Collapsed abstract is as tall as the meta column (side by side on lg+),
  // rounded down to whole lines. Only measured while collapsed.
  useEffect(() => {
    const el = abstractRef.current;
    const meta = metaRef.current;
    if (!el || expanded) return;
    const measure = () => {
      const sideBySide = window.matchMedia("(min-width: 1024px)").matches;
      const lineHeight = Number.parseFloat(getComputedStyle(el).lineHeight);
      const lines =
        meta && sideBySide && lineHeight
          ? Math.max(1, Math.floor(meta.offsetHeight / lineHeight))
          : DEFAULT_CLAMP_LINES;
      el.style.setProperty("-webkit-line-clamp", String(lines));
      setIsOverflowing(el.scrollHeight > el.clientHeight);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    if (meta) observer.observe(meta);
    return () => observer.disconnect();
  }, [expanded, article.abstract]);

  const metaFields = buildMetaFields(article);
  const hasMeta = metaFields.length > 0;

  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      <div className="flex flex-col gap-6 lg:flex-row">
        <dl className="shrink-0 space-y-3 border-b pb-4 text-sm lg:w-64 lg:border-0 lg:pb-0">
          <MetaItem label="Select">
            <Field orientation="horizontal" className="w-auto">
              <Checkbox
                id={`select-${article.id}`}
                checked={isSelected}
                disabled={!article.has_fulltext}
                onCheckedChange={(checked) =>
                  onToggleSelect(article.id, checked === true)
                }
              />
              <FieldLabel
                htmlFor={`select-${article.id}`}
                className={cn(
                  "font-normal text-muted-foreground",
                  !article.has_fulltext && "opacity-50",
                )}
                title="Full text is required to select an article"
              >
                Mark for bulk download
              </FieldLabel>
            </Field>
          </MetaItem>
          <MetaItem label="PDF">
            <button
              type="button"
              onClick={() => onOpenPdf(article)}
              disabled={openingPdf || !article.pdf_url}
              className={cn(actionLinkClass, openingPdf && "animate-pulse")}
            >
              <Download className="size-4" />
              Download PDF
            </button>
          </MetaItem>
          <MetaItem label="Publisher">
            <button
              type="button"
              onClick={() => onOpenLandingPage(article.pdf_landing_page)}
              className={actionLinkClass}
            >
              <ExternalLinkIcon className="size-4" />
              Open publisher page
            </button>
          </MetaItem>
        </dl>

        <div
          className={cn(
            "min-w-0 flex-1 lg:border-l lg:pl-6",
            hasMeta && "lg:border-r lg:pr-6",
          )}
        >
          <h2 className="mb-2 text-xl font-semibold text-content-muted leading-tight">
            {article.title}
          </h2>
          <p
            ref={abstractRef}
            className={cn(
              "max-w-prose font-serif text-base leading-relaxed",
              !expanded && "line-clamp-6",
            )}
          >
            {article.abstract}
          </p>
          {(isOverflowing || expanded) && (
            <button
              type="button"
              onClick={() => setExpanded((prev) => !prev)}
              aria-expanded={expanded}
              className="mt-3 flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              {expanded ? "Show less" : "Show more"}
              <ChevronDown
                className={cn(
                  "size-4 transition-transform",
                  expanded && "rotate-180",
                )}
              />
            </button>
          )}
        </div>
        {hasMeta && (
          <dl
            ref={metaRef}
            className="shrink-0 space-y-3 border-t pt-4 text-sm lg:w-64 lg:self-start lg:border-0 lg:pt-0"
          >
            {metaFields.map((field) => (
              <MetaItem key={field.label} {...field}>
                {field.value}
              </MetaItem>
            ))}
          </dl>
        )}
      </div>
    </div>
  );
}
