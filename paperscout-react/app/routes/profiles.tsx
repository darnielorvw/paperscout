import { PlusIcon, Trash2Icon } from "lucide-react";
import { useEffect, useState, type KeyboardEvent } from "react";
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
import { Label } from "~/components/ui/label";
import { Skeleton } from "~/components/ui/skeleton";
import { Switch } from "~/components/ui/switch";
import { useProfiles } from "~/context/profile-context";
import { useSearch } from "~/context/search-context";
import { protectPage } from "~/lib/auth";
import { formatDateForDisplay } from "~/lib/date-utils";
import { areFiltersEqual } from "~/lib/search-utils";

export function clientLoader() { // protectPage bleibt hier wichtig
  protectPage();
  return null;
}

export default function Profiles() {
  const [error, setError] = useState<string | null>(null);
  const {
    rowSelection,
    date,
    searchTerm: currentSearchTerm,
  } = useSearch();
  const {
    profiles,
    isLoading,
    saveProfile,
    deleteProfile,
    applyProfile,
    updateProfile,
    toggleProfileNotifications,
    reloadProfiles,
    activeProfileId,
  } = useProfiles();
  const [newProfileName, setNewProfileName] = useState("");
  const currentSearchState = { rowSelection, date, searchTerm: currentSearchTerm };

  // A profile can only be saved or updated if at least one journal is selected.
  const canSaveOrUpdate = Object.keys(rowSelection).length > 0;

  const handleSaveProfile = async () => {
    if (!newProfileName.trim()) {
      setError("Name required");
      return;
    } else if (!canSaveOrUpdate) {
      setError("Please select at least one journal to save a profile.");

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
    if (!canSaveOrUpdate) {
      setError("Please select at least one journal to save a profile.");
      return;
    }
    try {
      await updateProfile(profileId);
    } catch (error: any) {
      setError(error.message || "Error updating profile.");
    }
  };

  const handleToggleNotifications = async (
    profileId: number,
    emailNotifications: boolean,
  ) => {
    try {
      await toggleProfileNotifications(profileId, emailNotifications);
    } catch (error: any) {
      setError(error.message || "Error updating notification setting.");
    }
  };

  // When the page loads, make sure the profile list is up to date.
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
              profiles.map((profile) => {
                const isApplied = areFiltersEqual(profile, currentSearchState);
                // The update button is disabled if:
                // 1. The current filters already match the profile (isApplied).
                // 2. Another profile is active (activeProfileId is not null and not this profile's ID) OR no journals are selected.
                const isUpdateDisabled = isApplied || (activeProfileId !== null && activeProfileId !== profile.id);
                return (
                  <Card key={profile.id}>
                    <CardHeader>
                      <CardTitle>{profile.name}</CardTitle>
                      <CardDescription className="text-xs pt-2">
                        {Object.keys(profile.rowSelection).length} Journals | {formatDateForDisplay(profile.date?.from)}
                        {" "}-{" "}
                        {formatDateForDisplay(profile.date?.to)}{" "}
                        {profile.searchTerm && "| "}
                        {profile.searchTerm}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center gap-2">
                        <Switch
                          id={`notify-${profile.id}`}
                          checked={profile.emailNotifications}
                          onCheckedChange={(checked) =>
                            handleToggleNotifications(profile.id, checked)
                          }
                        />
                        <Label htmlFor={`notify-${profile.id}`}>
                          Email notifications
                        </Label>
                      </div>
                    </CardContent>
                    <CardFooter className="flex justify-between gap-2">
                      <Button className="flex-1" onClick={() => applyProfile(profile.id)} disabled={isApplied}>
                        Apply
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => handleUpdateProfile(profile.id)} disabled={isUpdateDisabled}
                      >
                        Save to Profile
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
                );
              })
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
