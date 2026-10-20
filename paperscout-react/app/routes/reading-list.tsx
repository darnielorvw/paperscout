import { format } from "date-fns";
import { Trash2Icon } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { ArticleCard, MetaItem } from "~/components/article-card";
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
import { Checkbox } from "~/components/ui/checkbox";
import { Field, FieldLabel } from "~/components/ui/field";
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

function showError(error: unknown, fallback: string) {
  toast.error(error instanceof Error ? error.message : fallback, {
    position: "top-center",
  });
}

function ReadingListEntry({
  saved,
  isSelected,
  onToggleSelect,
}: {
  saved: SavedArticle;
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
        </>
      }
      leftBottom={
        <>
          <Field orientation="horizontal" className="mt-1 w-auto">
            <Checkbox
              id={`select-${saved.id}`}
              checked={isSelected}
              onCheckedChange={(checked) =>
                onToggleSelect(saved.id, checked === true)
              }
            />
            <FieldLabel
              htmlFor={`select-${saved.id}`}
              className="font-normal text-muted-foreground hover:text-destructive"
            >
              Mark for removal
            </FieldLabel>
          </Field>
        </>
      }
    ></ArticleCard>
  );
}

export default function ReadingList() {
  const { savedArticles, isLoading, error, removeSavedArticles } =
    useReadingList();
  const [filter, setFilter] = useState<Filter>("unread");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);

  const shown = savedArticles.filter(
    (saved) => filter === "all" || (filter === "read") === saved.isRead,
  );
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
          <div className="sticky top-2 z-10 flex items-center justify-between rounded-lg border bg-background/80 px-4 py-3 shadow-sm backdrop-blur">
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
              <div className="flex gap-2 mr-4" role="group" aria-label="Filter">
                {filterItems.map((item) => (
                  <Button
                    key={item.value}
                    size="sm"
                    variant={filter === item.value ? "default" : "outline"}
                    aria-pressed={filter === item.value}
                    onClick={() => handleFilterChange(item.value)}
                  >
                    {item.title}
                  </Button>
                ))}
              </div>
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

          {shown.length === 0 ? (
            <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
              {filter === "read"
                ? "No papers marked as read yet."
                : "All papers read."}
            </div>
          ) : (
            shown.map((saved) => (
              <ReadingListEntry
                key={saved.id}
                saved={saved}
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
