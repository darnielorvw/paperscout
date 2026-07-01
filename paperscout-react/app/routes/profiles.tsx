import { format } from "date-fns";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { Suspense, useState } from "react";
import type { DateRange } from "react-day-picker";
import { Await, useLoaderData, useNavigate } from "react-router";
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
import { Input } from "~/components/ui/input";
import { Skeleton } from "~/components/ui/skeleton";
import { useSearch } from "~/context/search-context";
import { apiFetch } from "~/lib/api";
import { protectPage } from "~/lib/auth";

export interface SearchProfile {
  id: number;
  name: string;
  rowSelection: Record<string, boolean>;
  date: DateRange;
  searchTerm: string;
}

export function clientLoader() {
  protectPage();
  const profilesPromise = apiFetch("/api/profiles").then(
    (data) => (data.results as SearchProfile[]) || [],
  );
  return { profilesPromise };
}

export default function Profiles() {
  const [error, setError] = useState<string | null>(null);

  const { profilesPromise } = useLoaderData<typeof clientLoader>();
  const {
    rowSelection,
    date,
    searchTerm,
    setRowSelection,
    setDate,
    setSearchTerm,
  } = useSearch();
  const [newProfileName, setNewProfileName] = useState("");
  const navigate = useNavigate();

  const handleSaveProfile = async () => {
    if (!newProfileName.trim()) {
      setError("Bitte geben Sie einen Namen für das Profil ein.");
      return;
    }
    try {
      console.log(rowSelection, date, searchTerm);
      await apiFetch("/api/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newProfileName,
          settings: { rowSelection, date, searchTerm },
        }),
      });
      setNewProfileName("");
      navigate(".", { replace: true }); // Lädt die Seite neu, um die Profilliste zu aktualisieren
    } catch (err: any) {
      setError(err.message || "Ein unbekannter Fehler ist aufgetreten.");
    }
  };

  const handleApplyProfile = (profile: SearchProfile) => {
    setRowSelection(profile.rowSelection);
    setDate(profile.date);
    setSearchTerm(profile.searchTerm);
    navigate("/"); // Zurück zur Haupt-Suchseite
  };

  const handleDeleteProfile = async (profileId: number) => {
    if (window.confirm("Möchten Sie dieses Profil wirklich löschen?")) {
      try {
        await apiFetch(`/api/profiles/${profileId}`, { method: "DELETE" });
        navigate(".", { replace: true });
      } catch (error) {
        console.error("Fehler beim Löschen des Profils:", error);
        alert("Das Profil konnte nicht gelöscht werden.");
      }
    }
  };

  return (
    <div className="flex h-full w-full flex-col gap-8 p-4">
      <div>
        <h1 className="text-2xl font-bold">Such-Profile</h1>
        <p className="text-muted-foreground">
          Speichere deine aktuellen Sucheinstellungen als Profil oder wähle ein
          bestehendes Profil aus, um es anzuwenden.
        </p>
      </div>

      {/* Neues Profil erstellen */}
      <Card>
        <CardHeader>
          <CardTitle>Neues Profil erstellen</CardTitle>
          <CardDescription>
            Speichere deine aktuelle Auswahl an Journals, den Zeitraum und den
            Suchbegriff für die spätere Wiederverwendung.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex w-full max-w-sm items-center space-x-2">
            <Input
              type="text"
              placeholder="Name des Profils (z.B. 'KI-Forschung 2024')"
              value={newProfileName}
              onChange={(e) => setNewProfileName(e.target.value)}
            />
            <Button onClick={handleSaveProfile}>
              <PlusIcon className="mr-2 h-4 w-4" /> Speichern
            </Button>
          </div>
          <AlertDialogBasic open={!!error} />
        </CardContent>
      </Card>

      {/* Gespeicherte Profile */}
      <div>
        <h2 className="mb-4 text-xl font-semibold">Gespeicherte Profile</h2>
        <Suspense fallback={<Skeleton className="h-40 w-full" />}>
          <Await resolve={profilesPromise}>
            {(profiles: SearchProfile[]) => (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {profiles.length > 0 ? (
                  profiles.map((profile) => (
                    <Card key={profile.id}>
                      <CardHeader>
                        <CardTitle>{profile.name}</CardTitle>
                        <CardDescription className="text-xs pt-2">
                          {Object.keys(profile.rowSelection).length} Journals |{" "}
                          {profile.date?.from &&
                            format(
                              new Date(profile.date.from),
                              "MMM yyyy",
                            )}{" "}
                          -{" "}
                          {profile.date?.to &&
                            format(new Date(profile.date.to), "MMM yyyy")}{" "}
                          | "{profile.searchTerm}"
                        </CardDescription>
                      </CardHeader>
                      <CardFooter className="flex justify-between">
                        <Button onClick={() => handleApplyProfile(profile)}>
                          Anwenden
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteProfile(profile.id)}
                        >
                          <Trash2Icon className="h-4 w-4 text-destructive" />
                        </Button>
                      </CardFooter>
                    </Card>
                  ))
                ) : (
                  <p className="text-muted-foreground col-span-full">
                    Noch keine Profile gespeichert.
                  </p>
                )}
              </div>
            )}
          </Await>
        </Suspense>
      </div>
    </div>
  );
}
