"use client";

import { InfoIcon, SearchIcon, SparklesIcon } from "lucide-react";
import {
  useLayoutEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
} from "react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Input } from "~/components/ui/input";
import { Textarea } from "~/components/ui/textarea";
import type { SearchMode } from "~/context/search-context";
import { SEMANTIC_MAX_CHARS } from "~/lib/search-utils";
import { cn } from "~/lib/utils";

// Each field sits in a card with its hints; the active one stands out. The
// card draws its edge as a ring, so the highlight doesn't shift the content.
const cardClass = (active: boolean) =>
  cn(
    "transition-[opacity,box-shadow,background-color] duration-300",
    active ? "ring-3 ring-primary" : "bg-muted/30 opacity-90",
  );

interface SearchPageProps {
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  semanticQuery: string;
  onSemanticQueryChange: (value: string) => void;
  // Only one of the two fields is searched with; the other keeps its value.
  searchMode: SearchMode;
  onSearchModeChange: (mode: SearchMode) => void;
  // Names of the journals the semantic search can't search.
  unsupportedJournals: string[];
  onSearch: () => void;
}

export default function SearchPage({
  searchTerm,
  onSearchTermChange,
  semanticQuery,
  onSemanticQueryChange,
  searchMode,
  onSearchModeChange,
  unsupportedJournals,
  onSearch,
}: SearchPageProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const keywordsRef = useRef<HTMLInputElement>(null);
  const semanticRef = useRef<HTMLTextAreaElement>(null);
  // Vertical centres of the two fields, where the knob stops on the rail.
  const [stops, setStops] = useState({ keywords: 24, semantic: 120 });

  // The textarea fills the height that is left, so the stops are measured again on resize.
  useLayoutEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    const measure = () => {
      const top = wrapper.getBoundingClientRect().top;
      const centre = (el: HTMLElement | null) => {
        const rect = el?.getBoundingClientRect();
        return rect ? rect.top - top + rect.height / 2 : 0;
      };
      setStops({
        keywords: centre(keywordsRef.current),
        semantic: centre(semanticRef.current),
      });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(wrapper);
    return () => observer.disconnect();
  }, []);

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      onSearch();
    }
  };
  // Enter searches here too; Shift+Enter still adds a new line.
  const handleSemanticKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      onSearch();
    }
  };
  // The browser cuts pasted text at maxLength without a word, so say so.
  const handleSemanticPaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const { selectionStart, selectionEnd } = event.currentTarget;
    const pasted = event.clipboardData.getData("text");
    const length = semanticQuery.length - (selectionEnd - selectionStart) + pasted.length;
    if (length > SEMANTIC_MAX_CHARS) {
      toast.info(
        `The text was cut to ${SEMANTIC_MAX_CHARS.toLocaleString("en-US")} characters, the most the semantic search takes.`,
      );
    }
  };
  const toggleMode = () => {
    const next = searchMode === "keywords" ? "semantic" : "keywords";
    onSearchModeChange(next);
    (next === "keywords" ? keywordsRef : semanticRef).current?.focus();
  };
  const isSemantic = searchMode === "semantic";

  return (
    <div className="flex h-full min-h-0 w-full flex-col items-center md:p-1">
      <div
        ref={wrapperRef}
        className="grid min-h-0 w-full max-w-2xl flex-1 grid-cols-[52px_minmax(0,1fr)] grid-rows-[minmax(0,1fr)] gap-2"
      >
        <div className="relative">
          <span
            className="absolute left-1/2 w-0.5 -translate-x-1/2 bg-border"
            style={{
              top: stops.keywords,
              height: stops.semantic - stops.keywords,
            }}
          />
          {[stops.keywords, stops.semantic].map((top, i) => (
            <span
              key={i}
              className="absolute left-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-border"
              style={{ top }}
            />
          ))}
          <button
            type="button"
            aria-label={
              isSemantic ? "Switch to search term" : "Switch to semantic search"
            }
            onClick={toggleMode}
            className="absolute left-1/2 grid size-10 -translate-x-1/2 -translate-y-1/2 cursor-pointer place-items-center rounded-full bg-primary text-primary-foreground ring-[5px] ring-ring/30 transition-[top] duration-350 ease-[cubic-bezier(.3,1.3,.5,1)] outline-none focus-visible:ring-ring/60 motion-reduce:transition-none"
            style={{ top: isSemantic ? stops.semantic : stops.keywords }}
          >
            <SearchIcon
              className={cn(
                "col-start-1 row-start-1 size-5 transition-opacity",
                isSemantic && "opacity-0",
              )}
            />
            <SparklesIcon
              className={cn(
                "col-start-1 row-start-1 size-5 transition-opacity",
                !isSemantic && "opacity-0",
              )}
            />
          </button>
        </div>

        <div className="flex min-h-0 flex-col gap-4">
          <Card
            className={cardClass(!isSemantic)}
            onFocus={() => onSearchModeChange("keywords")}
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SearchIcon className="size-4" />
                Keyword Search
              </CardTitle>
              <CardDescription>
                Finds papers containing these words.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Input
                ref={keywordsRef}
                placeholder="Keyword Search"
                className="px-4 h-12 w-full rounded-full text-2xl"
                value={searchTerm}
                onChange={(e) => onSearchTermChange(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </CardContent>
            <CardFooter className="text-sm text-muted-foreground">
              The keyword search looks at the title and abstract. Papers without
              an abstract, often those behind a paywall, are harder to find.
            </CardFooter>
          </Card>
          <Card
            className={cn(cardClass(isSemantic), "min-h-0 flex-1")}
            onFocus={() => onSearchModeChange("semantic")}
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SparklesIcon className="size-4" />
                Semantic Search
              </CardTitle>
              <CardDescription>
                Finds up to 50 papers by meaning rather than exact words.
                Semantic search shines when you have a longer description — an
                abstract, a grant aim, or a paragraph from a paper you’re
                writing. The richer the input, the better the matches. The date
                range only counts by year, so there is no monthly email for
                semantic searches.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex min-h-0 flex-1 flex-col">
              <Textarea
                ref={semanticRef}
                placeholder="Semantic Search"
                // Styled like the search term field; takes all the height the card has left.
                className="p-4 min-h-32 flex-1 w-full rounded-3xl text-2xl resize-none"
                maxLength={SEMANTIC_MAX_CHARS}
                value={semanticQuery}
                onChange={(e) => onSemanticQueryChange(e.target.value)}
                onKeyDown={handleSemanticKeyDown}
                onPaste={handleSemanticPaste}
                aria-describedby="semantic-query-length"
              />
              <p
                id="semantic-query-length"
                className={cn(
                  "mt-2 text-right text-xs tabular-nums text-muted-foreground",
                  semanticQuery.length >= SEMANTIC_MAX_CHARS && "text-destructive",
                )}
              >
                {semanticQuery.length.toLocaleString("en-US")} /{" "}
                {SEMANTIC_MAX_CHARS.toLocaleString("en-US")}
              </p>
            </CardContent>
            {unsupportedJournals.length > 0 && (
              <CardFooter className="text-sm text-muted-foreground">
                Not available for {unsupportedJournals.join(", ")}: these
                journals are left out of semantic searches.
              </CardFooter>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
