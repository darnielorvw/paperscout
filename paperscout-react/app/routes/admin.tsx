import { Trash2Icon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { AlertDialogBasic } from "~/components/alert-dialog";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Label } from "~/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "~/components/ui/table";
import { Textarea } from "~/components/ui/textarea";
import { useAuth } from "~/context/auth-context";
import { useJournals } from "~/context/journals-context";
import { apiFetch } from "~/lib/api";
import { protectPage } from "~/lib/auth";

export function clientLoader() {
  // Only checks that the user is logged in at all - whether they're an
  // admin can only be known once the user object has loaded (see below),
  // and the API enforces admin-only access regardless of the UI.
  // The journal list itself comes from JournalsProvider.
  protectPage();
  return null;
}

interface ImportResult {
  message: string;
  results: { id: string; name: string }[];
  not_found: string[];
}

export default function AdminPage() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const { journals, reloadJournals } = useJournals();
  const [namesInput, setNamesInput] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDeleteJournal = async (journalId: string) => {
    setDeletingId(journalId);
    try {
      await apiFetch(`/api/journals/${journalId}`, { method: "DELETE" });
      await reloadJournals();
    } catch (err: any) {
      setError(err.message || "Could not delete journal.");
    } finally {
      setDeletingId(null);
    }
  };

  const names = namesInput
    .split("\n")
    .map((name) => name.trim())
    .filter(Boolean);

  const handleImport = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (names.length === 0) {
      setError("Please enter at least one journal name.");
      return;
    }

    setIsImporting(true);
    try {
      const response = await apiFetch<ImportResult>(
        "/api/journals/import-by-name",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ names }),
        },
      );
      setResult(response);
      setNamesInput("");
      await reloadJournals();
    } catch (err: any) {
      setError(err.message || "Could not import journals.");
    } finally {
      setIsImporting(false);
    }
  };

  // Wait for the auth check to finish before deciding what to show, so we
  // don't briefly flash the "access denied" message for actual admins.
  if (isAuthLoading) {
    return null;
  }

  if (!user?.is_admin) {
    return (
      <div className="flex h-full w-full flex-col gap-4 p-4">
        <Card>
          <CardHeader>
            <CardTitle>Access denied</CardTitle>
            <CardDescription>
              This page is only available to administrators.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col gap-8 p-4">
      <div>
        <h1 className="text-2xl font-bold">Import Journals</h1>
        <p className="text-muted-foreground">
          Look up journals on OpenAlex by name and add them to the database.
        </p>
      </div>
      <form onSubmit={handleImport}>
        <Card>
          <CardHeader>
            <CardTitle>Journal Names</CardTitle>
            <CardDescription>
              Enter one journal name per line. Each name is looked up on
              OpenAlex; all other fields (ID, ISSN, publisher, homepage) are
              filled in automatically.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Label htmlFor="journal-names">Journal names</Label>
            <Textarea
              id="journal-names"
              placeholder={"Nature\nScience\nThe Lancet"}
              value={namesInput}
              onChange={(e) => setNamesInput(e.target.value)}
              rows={8}
            />
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={isImporting || names.length === 0}>
              {isImporting
                ? "Importing..."
                : `Import ${names.length || ""} Journal${names.length === 1 ? "" : "s"}`}
            </Button>
          </CardFooter>
        </Card>
        <AlertDialogBasic
          open={!!error}
          title="Error"
          description={error || ""}
          onClose={() => setError(null)}
        />
      </form>

      {result && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">{result.message}</p>
          {result.results.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Imported</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc text-sm">
                  {result.results.map((journal) => (
                    <li key={journal.id}>{journal.name}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {result.not_found.length > 0 && (
            <Card className="border-destructive/50">
              <CardHeader>
                <CardTitle>Not Found</CardTitle>
                <CardDescription>
                  No matching journal was found on OpenAlex for these names.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc text-sm text-destructive">
                  {result.not_found.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-xl font-bold">Manage Journals</h2>
          <p className="text-muted-foreground">
            {journals.length} journal{journals.length === 1 ? "" : "s"} in the
            database.
          </p>
        </div>
        <Card>
          <CardContent>
            {journals.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No journals in the database yet.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Publisher</TableHead>
                    <TableHead className="w-0 text-right">Delete</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {journals.map((journal) => (
                    <TableRow key={journal.id}>
                      <TableCell className="font-medium">
                        {journal.name}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {journal.publisher}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={deletingId === journal.id}
                          onClick={() => handleDeleteJournal(journal.id)}
                          aria-label={`Delete ${journal.name}`}
                        >
                          <Trash2Icon className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
