import { format } from "date-fns";
import {
  ArrowDownWideNarrowIcon,
  ArrowUpNarrowWideIcon,
  CheckIcon,
  ChevronDownIcon,
  FileTextIcon,
  MailIcon,
  SearchIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import {
  ActionButton,
  ActionLink,
  ArticleCard,
  MetaItem,
} from "~/components/article-card";
import { SkeletonList } from "~/components/skeletons";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "~/components/ui/alert-dialog";
import { Button } from "~/components/ui/button";
import { ButtonGroup } from "~/components/ui/button-group";
import { Checkbox } from "~/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "~/components/ui/dropdown-menu";
import { Field, FieldLabel } from "~/components/ui/field";
import { Input } from "~/components/ui/input";
import { Spinner } from "~/components/ui/spinner";
import {
  useReadingList,
  type SavedArticle,
} from "~/context/reading-list-context";
import { protectPage } from "~/lib/auth";

export function clientLoader() {
  // The list itself lives in ReadingListProvider (loaded once per session and
  // kept in sync on every change), so this route only needs the auth gate.
  protectPage();
  return null;
}

type Filter = "all" | "unread" | "read";

const filterItems: { value: Filter; title: string }[] = [
  { value: "unread", title: "Unread" },
  { value: "read", title: "Read" },
  { value: "all", title: "All" },
];

type SortField = "saved" | "published";
type SortDirection = "asc" | "desc";

const sortFieldItems: { value: SortField; title: string }[] = [
  { value: "saved", title: "Saved" },
  { value: "published", title: "Published" },
];

// Value for the journal/year dropdowns that disables that filter.
const ANY = "";

// The journal publication date, falling back to the index date for papers
// that don't have one (same two dates the article card shows).
function publishedDate(saved: SavedArticle): string | null {
  return (
    saved.article.journal_publication_date ||
    saved.article.publication_date ||
    null
  );
}

function publishedYear(saved: SavedArticle): string | null {
  return publishedDate(saved)?.slice(0, 4) || null;
}

function matchesSearch(saved: SavedArticle, words: string[]): boolean {
  const { title, author, journal_name, abstract, doi, topic } = saved.article;
  const haystack = [title, author, journal_name, abstract, doi, topic]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return words.every((word) => haystack.includes(word));
}

function compareSaved(
  a: SavedArticle,
  b: SavedArticle,
  field: SortField,
  direction: SortDirection,
): number {
  const dateA = field === "saved" ? a.savedAt : publishedDate(a);
  const dateB = field === "saved" ? b.savedAt : publishedDate(b);
  // Papers without a date go last, whichever direction.
  if (!dateA || !dateB) {
    return dateA ? -1 : dateB ? 1 : 0;
  }
  return direction === "desc"
    ? dateB.localeCompare(dateA)
    : dateA.localeCompare(dateB);
}

function FilterDropdown({
  label,
  value,
  onChange,
  items,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  items: { value: string; title: string }[];
}) {
  const current = items.find((item) => item.value === value);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="max-w-56">
          <span className="text-muted-foreground">{label}:</span>
          <span className="truncate">{current?.title}</span>
          <ChevronDownIcon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 overflow-y-auto">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {items.map((item) => (
            <DropdownMenuRadioItem key={item.value} value={item.value}>
              {item.title}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function showError(error: unknown, fallback: string) {
  toast.error(error instanceof Error ? error.message : fallback, {
    position: "top-center",
  });
}

// Lets the user ask the admins for a PDF when the library has no access to
// the paper, and links the PDF once an admin has uploaded it.
function PdfStatus({ saved }: { saved: SavedArticle }) {
  const { requestPdf, cancelPdfRequest } = useReadingList();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isBusy, setIsBusy] = useState(false);

  const run = async (action: () => Promise<void>, fallback: string) => {
    setIsBusy(true);
    try {
      await action();
    } catch (error) {
      showError(error, fallback);
    } finally {
      setIsBusy(false);
    }
  };

  if (saved.pdfUrl) {
    return (
      <ActionLink href={saved.pdfUrl} className="text-success">
        <FileTextIcon />
        Open PDF
      </ActionLink>
    );
  }

  if (saved.pdfRequested) {
    return (
      <ActionButton
        className="text-destructive"
        disabled={isBusy}
        onClick={() =>
          run(
            () => cancelPdfRequest(saved.id),
            "Could not withdraw the request.",
          )
        }
      >
        <XIcon />
        Withdraw request
      </ActionButton>
    );
  }

  return (
    <>
      <ActionButton disabled={isBusy} onClick={() => setConfirmOpen(true)}>
        <MailIcon />
        Request PDF
      </ActionButton>
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent size="sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Request this PDF?</AlertDialogTitle>
            <AlertDialogDescription>
              Only if the library gives you no access to this paper. An admin is
              notified and looks for the PDF; once it is uploaded, it shows up
              here.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                run(() => requestPdf(saved.id), "Could not request the PDF.")
              }
            >
              Request PDF
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function ReadingListEntry({
  saved,
  isRemoveMode,
  isSelected,
  onToggleSelect,
}: {
  saved: SavedArticle;
  // The "Mark for removal" checkbox only shows in remove mode.
  isRemoveMode: boolean;
  isSelected: boolean;
  onToggleSelect: (savedId: number, checked: boolean) => void;
}) {
  const { updateSavedArticle } = useReadingList();
  const handleToggleRead = (isRead: boolean) =>
    updateSavedArticle(saved.id, { isRead }).catch((error) =>
      showError(error, "Could not update the paper."),
    );

  return (
    <ArticleCard
      article={saved.article}
      leftTop={
        <>
          <MetaItem label="Status">
            <Field orientation="horizontal" className="mt-1 w-auto">
              <Checkbox
                id={`read-${saved.id}`}
                checked={saved.isRead}
                onCheckedChange={(checked) =>
                  handleToggleRead(checked === true)
                }
              />
              <FieldLabel
                htmlFor={`read-${saved.id}`}
                className="font-normal text-muted-foreground"
              >
                Read
              </FieldLabel>
            </Field>
          </MetaItem>
          <MetaItem label="Saved">
            {format(new Date(saved.savedAt), "d MMM yyyy")}
          </MetaItem>
          <MetaItem label="PDF">
            <PdfStatus saved={saved} />
          </MetaItem>
        </>
      }
      leftBottom={
        isRemoveMode && (
          <Field orientation="horizontal" className="mt-1 w-auto">
            <Checkbox
              id={`select-${saved.id}`}
              className="data-checked:border-destructive data-checked:bg-destructive data-checked:text-white dark:data-checked:bg-destructive"
              checked={isSelected}
              onCheckedChange={(checked) =>
                onToggleSelect(saved.id, checked === true)
              }
            />
            <FieldLabel
              htmlFor={`select-${saved.id}`}
              className="font-normal text-destructive"
            >
              Mark for removal
            </FieldLabel>
          </Field>
        )
      }
    ></ArticleCard>
  );
}

export default function ReadingList() {
  const {
    savedArticles,
    isLoading,
    error,
    reloadSavedArticles,
    removeSavedArticles,
  } = useReadingList();

  // The provider keeps the list for the whole session, so changes made
  // elsewhere (e.g. a PDF an admin uploaded) are fetched whenever the page is
  // opened or its tab becomes visible again.
  useEffect(() => {
    reloadSavedArticles();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") reloadSavedArticles();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibility);
  }, [reloadSavedArticles]);
  const [filter, setFilter] = useState<Filter>("unread");
  const [isRemoveMode, setIsRemoveMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);
  const [search, setSearch] = useState("");
  const [journal, setJournal] = useState(ANY);
  const [year, setYear] = useState(ANY);
  const [sortField, setSortField] = useState<SortField>("saved");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const toggleSortDirection = () =>
    setSortDirection((prev) => (prev === "desc" ? "asc" : "desc"));

  // Clicking the active field flips the direction, like a table header;
  // switching fields starts with the newest first.
  const handleSortFieldClick = (field: SortField) => {
    if (field === sortField) {
      toggleSortDirection();
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  // Dropdown options come from the papers on the list, so every option
  // matches at least one entry.
  const journalItems = useMemo(() => {
    const names = new Set(
      savedArticles
        .map((saved) => saved.article.journal_name)
        .filter((name): name is string => Boolean(name)),
    );
    return [
      { value: ANY, title: "All journals" },
      ...[...names]
        .sort((a, b) => a.localeCompare(b))
        .map((name) => ({ value: name, title: name })),
    ];
  }, [savedArticles]);

  const yearItems = useMemo(() => {
    const years = new Set(
      savedArticles.map(publishedYear).filter((y): y is string => Boolean(y)),
    );
    return [
      { value: ANY, title: "All years" },
      ...[...years]
        .sort((a, b) => b.localeCompare(a))
        .map((y) => ({ value: y, title: y })),
    ];
  }, [savedArticles]);

  const searchWords = search.toLowerCase().split(/\s+/).filter(Boolean);
  const isNarrowed = searchWords.length > 0 || journal !== ANY || year !== ANY;

  const shown = savedArticles
    .filter(
      (saved) =>
        (filter === "all" || (filter === "read") === saved.isRead) &&
        (journal === ANY || saved.article.journal_name === journal) &&
        (year === ANY || publishedYear(saved) === year) &&
        matchesSearch(saved, searchWords),
    )
    .sort((a, b) => compareSaved(a, b, sortField, sortDirection));

  const resetNarrowing = () => {
    setSearch("");
    setJournal(ANY);
    setYear(ANY);
  };
  // Only what is visible counts as selected: an entry that left the current
  // filter (e.g. just marked as read under "Unread") isn't removed unseen.
  const selectedShown = shown.filter((saved) => selectedIds.has(saved.id));

  const toggleSelected = (savedId: number, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(savedId);
      } else {
        next.delete(savedId);
      }
      return next;
    });
  };

  // Leaving remove mode drops the selection, so nothing stays marked unseen.
  const toggleRemoveMode = () => {
    setIsRemoveMode((prev) => !prev);
    setSelectedIds(new Set());
  };

  const handleFilterChange = (value: Filter) => {
    setFilter(value);
    setSelectedIds(new Set());
  };

  const handleRemoveSelected = async () => {
    const ids = selectedShown.map((saved) => saved.id);
    setIsRemoving(true);
    try {
      await removeSavedArticles(ids);
      setSelectedIds(new Set());
      toast.success(
        `${ids.length} ${ids.length === 1 ? "paper" : "papers"} removed from your reading list.`,
        { position: "top-center" },
      );
    } catch (error) {
      showError(error, "Could not remove the papers.");
    } finally {
      setIsRemoving(false);
      setConfirmOpen(false);
    }
  };

  return (
    <div className="flex w-full flex-col gap-4 py-4 pr-2">
      {isLoading ? (
        <SkeletonList />
      ) : error ? (
        <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
          {error}
        </div>
      ) : savedArticles.length === 0 ? (
        <div className="flex h-40 flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-center text-muted-foreground">
          <p>Your reading list is empty.</p>
          <p className="text-sm">
            Mark papers on the{" "}
            <Link to="/results" className="underline hover:text-foreground">
              results page
            </Link>{" "}
            and click “Save to reading list”.
          </p>
        </div>
      ) : (
        <>
          {/* Stays visible when the current filter shows nothing, so the
              filter can be switched back. */}
          <div className="sticky top-2 z-10 flex flex-col gap-3 rounded-lg border bg-background/80 px-4 py-3 shadow-sm backdrop-blur">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative min-w-48 flex-1">
                <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="Search title, author, abstract..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="h-8 pl-8"
                  aria-label="Search reading list"
                />
              </div>
              <ButtonGroup aria-label="Filter">
                {filterItems.map((item) => (
                  <Button
                    key={item.value}
                    size="sm"
                    variant={filter === item.value ? "default" : "outline"}
                    aria-pressed={filter === item.value}
                    // Fill the transparent border too, so the active button
                    // is as large as the outlined ones next to it.
                    className="aria-pressed:border-primary"
                    onClick={() => handleFilterChange(item.value)}
                  >
                    {item.title}
                  </Button>
                ))}
              </ButtonGroup>
              <FilterDropdown
                label="Journal"
                value={journal}
                onChange={setJournal}
                items={journalItems}
              />
              <FilterDropdown
                label="Published"
                value={year}
                onChange={setYear}
                items={yearItems}
              />
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Sort by</span>
                <ButtonGroup aria-label="Sort by">
                  {sortFieldItems.map((item) => (
                    <Button
                      key={item.value}
                      size="sm"
                      variant={sortField === item.value ? "default" : "outline"}
                      aria-pressed={sortField === item.value}
                      // Fill the transparent border too, so the active button
                      // is as large as the outlined ones next to it.
                      className="aria-pressed:border-primary"
                      onClick={() => handleSortFieldClick(item.value)}
                    >
                      {item.title}
                    </Button>
                  ))}
                </ButtonGroup>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={toggleSortDirection}
                  aria-label={
                    sortDirection === "desc"
                      ? "Sorted newest first, switch to oldest first"
                      : "Sorted oldest first, switch to newest first"
                  }
                  title={
                    sortDirection === "desc" ? "Newest first" : "Oldest first"
                  }
                >
                  {sortDirection === "desc" ? (
                    <ArrowDownWideNarrowIcon />
                  ) : (
                    <ArrowUpNarrowWideIcon />
                  )}
                  {sortDirection === "desc" ? "Newest" : "Oldest"}
                </Button>
              </div>
              <Button
                size="sm"
                variant={isRemoveMode ? "default" : "outline"}
                aria-pressed={isRemoveMode}
                className="ml-auto aria-pressed:border-primary"
                onClick={toggleRemoveMode}
              >
                {isRemoveMode ? <CheckIcon /> : <Trash2Icon />}
                {isRemoveMode ? "Done" : "Remove papers"}
              </Button>
            </div>
            {isRemoveMode && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <p className="text-sm text-muted-foreground">
                    {selectedShown.length > 0
                      ? `${selectedShown.length} selected`
                      : "Nothing selected"}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setSelectedIds(new Set(shown.map((saved) => saved.id)))
                    }
                    disabled={selectedShown.length === shown.length}
                  >
                    Select all
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedIds(new Set())}
                    disabled={selectedShown.length === 0}
                  >
                    Clear selection
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setConfirmOpen(true)}
                    disabled={selectedShown.length === 0 || isRemoving}
                  >
                    <Trash2Icon />
                    Remove selected
                  </Button>
                </div>
              </div>
            )}
          </div>

          {shown.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-muted-foreground">
              {isNarrowed ? (
                <>
                  <p>No papers match your search or filters.</p>
                  <Button variant="outline" size="sm" onClick={resetNarrowing}>
                    Reset search &amp; filters
                  </Button>
                </>
              ) : filter === "read" ? (
                "No papers marked as read yet."
              ) : (
                "All papers read."
              )}
            </div>
          ) : (
            shown.map((saved) => (
              <ReadingListEntry
                key={saved.id}
                saved={saved}
                isRemoveMode={isRemoveMode}
                isSelected={selectedIds.has(saved.id)}
                onToggleSelect={toggleSelected}
              />
            ))
          )}
        </>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent size="sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove selected papers?</AlertDialogTitle>
            <AlertDialogDescription>
              {selectedShown.length}{" "}
              {selectedShown.length === 1 ? "paper" : "papers"} will be removed
              from your reading list.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRemoving}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isRemoving}
              onClick={(event) => {
                // Keep the dialog open until the request has finished.
                event.preventDefault();
                handleRemoveSelected();
              }}
            >
              {isRemoving && <Spinner data-icon="inline-start" />}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
