import { ChevronDown, ExternalLinkIcon, Library } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "~/components/ui/button";
import type { SavedArticleData } from "~/context/reading-list-context";
import { formatDateForDisplay } from "~/lib/date-utils";
import { cn } from "~/lib/utils";

type ArticleCardProps = {
  article: SavedArticleData;
  // Page-specific entries at the top of the left column (e.g. selection).
  leftTop?: React.ReactNode;
  // Page-specific entries at the bottom of the left column.
  leftBottom?: React.ReactNode;
};

// Fallback when the meta column is not beside the abstract (stacked layout).
const DEFAULT_CLAMP_LINES = 6;
// "Show more" button: mt-3 (12px) + text-sm line height (20px).
const TOGGLE_BUTTON_HEIGHT = 32;

type MetaField = {
  label: string;
  description: string;
  value: React.ReactNode;
};

// A small outlined button, as wide as its column, for actions next to plain
// meta data, so clickable entries stand out from the ones that are only text.
export function ActionButton({
  className,
  ...props
}: React.ComponentProps<typeof Button>) {
  return (
    <Button
      variant="outline"
      size="sm"
      className={cn("mt-1 w-full justify-start font-normal", className)}
      {...props}
    />
  );
}

// Opens `href` in a new tab; without one the button is disabled.
export function ActionLink({
  href,
  className,
  children,
}: {
  href: string | null;
  className?: string;
  children: React.ReactNode;
}) {
  if (!href) {
    return (
      <ActionButton className={className} disabled>
        {children}
      </ActionButton>
    );
  }
  return (
    <ActionButton className={className} asChild>
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    </ActionButton>
  );
}

export function MetaItem({
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

function buildMetaFields(article: SavedArticleData): MetaField[] {
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
      value: article.doi?.replace(/^https?:\/\/(dx\.)?doi\.org\//, ""),
    },
  ];

  return fields.filter((field) => field.value);
}

export function ArticleCard({
  article,
  leftTop,
  leftBottom,
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
      // Space from the abstract's top (below the title, whose height varies)
      // to the meta column's bottom, minus room for the toggle button.
      const available = meta
        ? meta.getBoundingClientRect().bottom -
          el.getBoundingClientRect().top -
          TOGGLE_BUTTON_HEIGHT
        : 0;
      const lines =
        meta && sideBySide && lineHeight
          ? Math.max(1, Math.floor(available / lineHeight))
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
        {/* Stretches to the card's height, so leftBottom sits at its bottom. */}
        <div className="flex shrink-0 flex-col gap-3 border-b pb-4 text-sm lg:w-46 lg:border-0 lg:pb-0">
          <dl className="space-y-3">
            {leftTop}
            <MetaItem label="Library">
              <ActionLink href={article.library_url}>
                <Library />
                Find at library
              </ActionLink>
            </MetaItem>
            <MetaItem label="Publisher">
              {/* The DOI link resolves to the publisher's page. */}
              <ActionLink href={article.doi}>
                <ExternalLinkIcon />
                Open publisher page
              </ActionLink>
            </MetaItem>
          </dl>
          {leftBottom && (
            <div className="flex flex-col gap-3 lg:mt-auto">{leftBottom}</div>
          )}
        </div>

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
