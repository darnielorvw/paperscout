import { format } from "date-fns";
import { PlusIcon, RefreshCwIcon, Trash2Icon } from "lucide-react";
import { useEffect, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router";
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
import { useProfiles } from "~/context/profile-context";
import { protectPage } from "~/lib/auth";

export function clientLoader() { // protectPage bleibt hier wichtig
  protectPage();
  return null;
}

export default function Profiles() {
  const [error, setError] = useState<string | null>(null);
  const { profiles, isLoading, saveProfile, deleteProfile, applyProfile, updateProfile, reloadProfiles } = useProfiles();
  const [newProfileName, setNewProfileName] = useState("");
  const navigate = useNavigate();

  const handleSaveProfile = async () => {
    if (!newProfileName.trim()) {
      setError("Name required");
      return;
    }
    try {
      await saveProfile(newProfileName);
      setNewProfileName("");
    } catch (err: any) {
      setError(err.message || "Could not save profile.");
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      handleSaveProfile();
    }
  };

  const handleDeleteProfile = async (profileId: number) => {
    try {
      await deleteProfile(profileId);
    } catch (error: any) {
      setError(error.message || "Error deleting profile.");
    }
  };

  const handleUpdateProfile = async (profileId: number) => {
    try {
      await updateProfile(profileId);
    } catch (error: any) {
      setError(error.message || "Error updating profile.");
    }
  };

  // Wenn die Seite geladen wird, stellen wir sicher, dass die Profilliste aktuell ist.
  useEffect(() => {
    reloadProfiles();
  }, [reloadProfiles]);

  return (
    <div className="flex h-full w-full flex-col gap-8 p-4">
      <div>
        <h1 className="text-2xl font-bold">Search Profiles</h1>
        <p className="text-muted-foreground">
          Save your current search settings as a profile or select an existing
          one to apply it.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Create New Profile</CardTitle>
          <CardDescription>
            Save your current selection of journals, the date range, and the
            search term for later use.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex w-full max-w-sm items-center space-x-2">
            <Input
              type="text"
              placeholder="Name of the profile"
              value={newProfileName}
              onChange={(e) => setNewProfileName(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <Button onClick={handleSaveProfile}>
              <PlusIcon className="h-4 w-4" /> Save
            </Button>
          </div>
          <AlertDialogBasic
            open={!!error}
            title="Error Saving Profile"
            description={error || ""}
            onClose={() => setError(null)} />
        </CardContent>
      </Card>

      {/* Gespeicherte Profile */}
      <div>
        <h2 className="mb-4 text-xl font-semibold">Saved Profiles</h2>
        {isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {profiles.length > 0 ? (
              profiles.map((profile) => (
                <Card key={profile.id}>
                  <CardHeader>
                    <CardTitle>{profile.name}</CardTitle>
                    <CardDescription className="text-xs pt-2">
                      {Object.keys(profile.rowSelection).length} Journals |{" "}
                      {profile.date?.from &&
                        format(new Date(profile.date.from), "MMM yyyy")}{" "}
                      -{" "}
                      {profile.date?.to &&
                        format(new Date(profile.date.to), "MMM yyyy")}{" "}
                      {profile.searchTerm && "| "}
                      {profile.searchTerm}
                    </CardDescription>
                  </CardHeader>
                  <CardFooter className="flex justify-between gap-2">
                    <Button className="flex-1" onClick={() => applyProfile(profile.id)}>
                      Apply 
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => handleUpdateProfile(profile.id)}
                    >
                      <RefreshCwIcon className="h-4 w-4" />
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
                No profiles saved yet.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
