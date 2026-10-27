import { put } from "@vercel/blob/client";
import { format } from "date-fns";
import {
  FileTextIcon,
  Library,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ActionLink, ExternalIcon } from "~/components/article-card";
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
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Spinner } from "~/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "~/components/ui/table";
import { useAuth } from "~/context/auth-context";
import { apiFetch } from "~/lib/api";
import { protectPage } from "~/lib/auth";

export function clientLoader() {
  // Like the admin page: whether the user is an admin is only known once the
  // user object has loaded, and the API enforces it regardless of the UI.
  protectPage();
  return null;
}

interface RequestedPaper {
  articleId: string;
  title: string | null;
  journalName: string | null;
  doi: string | null;
  libraryUrl: string | null;
  // Null for an uploaded PDF nobody asks for anymore.
  requestedAt: string | null;
  requesters: string[];
  pdfUrl: string | null;
}

interface PdfRequestsResponse {
  results: RequestedPaper[];
  uploadsEnabled: boolean;
}

// Uploads the PDF from the browser straight to Vercel Blob (a Vercel function
// only accepts 4.5 MB), with a token the API issues for this paper only, and
// then tells the API where it ended up.
async function uploadPdf(articleId: string, file: File) {
  const { pathname, clientToken } = await apiFetch<{
    pathname: string;
    clientToken: string;
  }>("/api/admin/pdf-upload-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ article_id: articleId }),
  });
  const blob = await put(pathname, file, {
    access: "public",
    token: clientToken,
    contentType: "application/pdf",
  });
  await apiFetch("/api/admin/pdfs", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ article_id: articleId, url: blob.url }),
  });
}

function UploadButton({
  paper,
  disabled,
  onUploaded,
}: {
  paper: RequestedPaper;
  disabled: boolean;
  onUploaded: () => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setIsUploading(true);
    try {
      await uploadPdf(paper.articleId, file);
      await onUploaded();
      toast.success("PDF uploaded. It now shows up on the reading lists.", {
        position: "top-center",
      });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not upload the PDF.",
        { position: "top-center" },
      );
    } finally {
      setIsUploading(false);
      // Lets the same file be picked again after a failed upload.
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      <Button
        size="sm"
        variant={paper.pdfUrl ? "outline" : "default"}
        disabled={disabled || isUploading}
        onClick={() => inputRef.current?.click()}
      >
        {isUploading ? <Spinner data-icon="inline-start" /> : <UploadIcon />}
        {paper.pdfUrl ? "Replace PDF" : "Upload PDF"}
      </Button>
    </>
  );
}

function DeleteButton({
  paper,
  onDeleted,
}: {
  paper: RequestedPaper;
  onDeleted: () => Promise<void>;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      const params = new URLSearchParams({ article_id: paper.articleId });
      await apiFetch(`/api/admin/pdfs?${params}`, { method: "DELETE" });
      await onDeleted();
      toast.success("PDF deleted. The request is open again.", {
        position: "top-center",
      });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not delete the PDF.",
        { position: "top-center" },
      );
    } finally {
      setIsDeleting(false);
      setConfirmOpen(false);
    }
  };

  return (
    <>
      <Button
        variant="ghost"
        size="icon-sm"
        disabled={isDeleting}
        onClick={() => setConfirmOpen(true)}
        aria-label={`Delete PDF of ${paper.title || paper.articleId}`}
      >
        <Trash2Icon className="text-destructive" />
      </Button>
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent size="sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this PDF?</AlertDialogTitle>
            <AlertDialogDescription>
              It disappears from every reading list and the file is removed from
              storage. The request becomes open again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isDeleting}
              onClick={(event) => {
                // Keep the dialog open until the request has finished.
                event.preventDefault();
                handleDelete();
              }}
            >
              {isDeleting && <Spinner data-icon="inline-start" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function PaperTable({
  papers,
  uploadsEnabled,
  onUploaded,
}: {
  papers: RequestedPaper[];
  uploadsEnabled: boolean;
  onUploaded: () => Promise<void>;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Paper</TableHead>
          <TableHead>Requested by</TableHead>
          <TableHead>Since</TableHead>
          <TableHead className="w-0 text-right">PDF</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {papers.map((paper) => (
          <TableRow key={paper.articleId}>
            <TableCell className="max-w-md whitespace-normal">
              <p className="font-medium">{paper.title || paper.articleId}</p>
              <p className="text-muted-foreground">{paper.journalName}</p>
              <div className="flex flex-wrap gap-x-4 text-sm">
                <ActionLink href={paper.libraryUrl} className="w-auto">
                  <Library />
                  Library
                </ActionLink>
                <ActionLink href={paper.doi} className="w-auto">
                  <ExternalIcon />
                  Publisher
                </ActionLink>
                {paper.pdfUrl && (
                  <ActionLink href={paper.pdfUrl} className="w-auto">
                    <FileTextIcon />
                    Current PDF
                  </ActionLink>
                )}
              </div>
            </TableCell>
            <TableCell className="align-top whitespace-normal text-muted-foreground">
              {paper.requesters.length === 0
                ? "Nobody anymore"
                : paper.requesters.map((email) => <p key={email}>{email}</p>)}
            </TableCell>
            <TableCell className="align-top text-muted-foreground">
              {paper.requestedAt
                ? format(new Date(paper.requestedAt), "d MMM yyyy")
                : "–"}
            </TableCell>
            <TableCell className="align-top text-right">
              <div className="flex justify-end gap-1">
                <UploadButton
                  paper={paper}
                  disabled={!uploadsEnabled}
                  onUploaded={onUploaded}
                />
                {paper.pdfUrl && (
                  <DeleteButton paper={paper} onDeleted={onUploaded} />
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function PdfRequestsPage() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const [papers, setPapers] = useState<RequestedPaper[]>([]);
  const [uploadsEnabled, setUploadsEnabled] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<PdfRequestsResponse>(
        "/api/admin/pdf-requests",
      );
      setPapers(data.results);
      setUploadsEnabled(data.uploadsEnabled);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load the requests.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.is_admin) load();
  }, [user?.is_admin, load]);

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

  const open = papers.filter((paper) => !paper.pdfUrl);
  const fulfilled = papers.filter((paper) => paper.pdfUrl);

  return (
    <div className="flex h-full w-full flex-col gap-8 p-4">
      <div>
        <h1 className="text-2xl font-bold">PDF Requests</h1>
        <p className="text-muted-foreground">
          Papers users have no library access to. Upload a PDF and it shows up
          for everyone with the paper on their reading list.
        </p>
      </div>

      {!uploadsEnabled && (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle>Uploads disabled</CardTitle>
            <CardDescription>
              No Vercel Blob store is connected (BLOB_READ_WRITE_TOKEN is
              missing on the server).
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <Spinner />
        </div>
      ) : error ? (
        <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
          {error}
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-4">
            <h2 className="text-xl font-bold">Open ({open.length})</h2>
            <Card>
              <CardContent>
                {open.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No open requests.
                  </p>
                ) : (
                  <PaperTable
                    papers={open}
                    uploadsEnabled={uploadsEnabled}
                    onUploaded={load}
                  />
                )}
              </CardContent>
            </Card>
          </div>

          {fulfilled.length > 0 && (
            <div className="flex flex-col gap-4">
              <h2 className="text-xl font-bold">
                Uploaded ({fulfilled.length})
              </h2>
              <Card>
                <CardContent>
                  <PaperTable
                    papers={fulfilled}
                    uploadsEnabled={uploadsEnabled}
                    onUploaded={load}
                  />
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
