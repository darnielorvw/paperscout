import { endOfMonth, startOfMonth } from "date-fns";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useNavigate } from "react-router";
import { apiFetch } from "~/lib/api";
import { areFiltersEqual, buildResultsUrl } from "~/lib/search-utils";
import { useSearch } from "./search-context";

export interface SearchProfile {
  id: number;
  name: string;
  rowSelection: Record<string, boolean>;
  searchTerm: string;
  emailNotifications: boolean;
}

interface ProfileContextState {
  profiles: SearchProfile[];
  activeProfileId: number | null;
  isLoading: boolean;
  error: string | null;
  applyProfile: (profileId: number) => void;
  clearActiveProfile: () => void;
  updateProfile: (profileId: number) => Promise<void>;
  saveProfile: (name: string) => Promise<void>;
  deleteProfile: (profileId: number) => Promise<void>;
  toggleProfileNotifications: (
    profileId: number,
    emailNotifications: boolean,
  ) => Promise<void>;
  setActiveProfileId: (profileId: number | null) => void;
  reloadProfiles: () => void;
}

const ProfileContext = createContext<ProfileContextState | undefined>(
  undefined,
);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const {
    rowSelection,
    date,
    searchTerm,
    setRowSelection,
    setDate,
    setSearchTerm,
  } = useSearch();
  const navigate = useNavigate();

  const fetchProfiles = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiFetch<{ results: SearchProfile[] }>(
        "/api/profiles",
      );
      setProfiles(data.results || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch profiles.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  // Effect to sync the active profile with the current search state
  useEffect(() => {
    const currentSearchState = { rowSelection, searchTerm };
    // Find a profile that matches the current search settings.
    const matchingProfile = profiles.find((profile) =>
      areFiltersEqual(profile, currentSearchState)
    );

    setActiveProfileId(matchingProfile ? matchingProfile.id : null);
  }, [rowSelection, searchTerm, profiles]);

  const applyProfile = useCallback(
    (profileId: number) => {
      const profile = profiles.find((p) => p.id === profileId);
      if (profile) {
        const newRowSelection = profile.rowSelection;
        const newSearchTerm = profile.searchTerm;

        // Update the global state with the new values. Profiles no longer store
        // a date range, so the currently selected date is left untouched.
        setRowSelection(newRowSelection);
        setSearchTerm(newSearchTerm);
        setActiveProfileId(profile.id);

        // Build the URL with the new values, not the old ones from the hook state.
        const resultsURL = buildResultsUrl({
          rowSelection: newRowSelection,
          date,
          searchTerm: newSearchTerm,
        });
        navigate(resultsURL, { replace: true });
      }
    },
    [profiles, date, setRowSelection, setSearchTerm, navigate],
  );

  const clearActiveProfile = useCallback(() => {
    setActiveProfileId(null);
    // Reset the search parameters to their default values
    setRowSelection({});
    const now = new Date();
    setDate({ from: startOfMonth(now), to: endOfMonth(now) });
    setSearchTerm("");
    navigate("/", { replace: true });
  }, [setRowSelection, setDate, setSearchTerm, navigate]);

  const updateProfile = useCallback(
    async (profileId: number) => {
      const updatedProfile = await apiFetch<SearchProfile>(
        `/api/profiles/${profileId}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rowSelection,
            searchTerm,
          }),
        },
      );
      // Replace only the one, updated profile in the state.
      setProfiles((prevProfiles) =>
        prevProfiles.map((p) => (p.id === profileId ? updatedProfile : p)),
      );
    },
    [rowSelection, searchTerm],
  );

  const saveProfile = useCallback(
    async (name: string) => {
      const newProfile = await apiFetch<SearchProfile>("/api/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          settings: {
            rowSelection,
            searchTerm,
          },
        }),
      });

      setProfiles((prevProfiles) => [...prevProfiles, newProfile]);
    },

    [rowSelection, searchTerm],
  );

  const toggleProfileNotifications = useCallback(
    async (profileId: number, emailNotifications: boolean) => {
      const updatedProfile = await apiFetch<SearchProfile>(
        `/api/profiles/${profileId}/notifications`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ emailNotifications }),
        },
      );
      setProfiles((prevProfiles) =>
        prevProfiles.map((p) => (p.id === profileId ? updatedProfile : p)),
      );
    },
    [],
  );

  const deleteProfile = useCallback(
    async (profileId: number) => {
      await apiFetch(`/api/profiles/${profileId}`, { method: "DELETE" });
      // Remove the deleted profile from the state to avoid a reload.
      setProfiles((prevProfiles) =>
        prevProfiles.filter((p) => p.id !== profileId),
      );
    },
    [],
  );

  const value = useMemo(
    () => ({
      profiles,
      activeProfileId,
      isLoading,
      error,
      applyProfile,
      updateProfile,
      clearActiveProfile,
      saveProfile,
      deleteProfile,
      toggleProfileNotifications,
      setActiveProfileId,
      reloadProfiles: fetchProfiles,
    }),
    [
      profiles,
      activeProfileId,
      isLoading,
      error,
      applyProfile,
      updateProfile,
      clearActiveProfile,
      saveProfile,
      deleteProfile,
      toggleProfileNotifications,
      fetchProfiles,
    ],
  );

  return (
    <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
  );
}

export function useProfiles() {
  const context = useContext(ProfileContext);
  if (context === undefined) {
    throw new Error("useProfiles must be used within a ProfileProvider");
  }
  return context;
}
