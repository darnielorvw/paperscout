import { endOfMonth, startOfMonth } from "date-fns";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { DateRange } from "react-day-picker";
import { useNavigate } from "react-router";
import { apiFetch } from "~/lib/api";
import { formatDateForApi } from "~/lib/date-utils";
import { areFiltersEqual, buildResultsUrl } from "~/lib/search-utils";
import { useSearch } from "./search-context";

export interface SearchProfile {
  id: number;
  name: string;
  rowSelection: Record<string, boolean>;
  date: DateRange;
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
      const data = await apiFetch("/api/profiles");
      setProfiles(data.results || []);
    } catch (err: any) {
      setError(err.message || "Failed to fetch profiles.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  // Effekt zur Synchronisierung des aktiven Profils mit dem aktuellen Suchstatus
  useEffect(() => {
    const currentSearchState = { rowSelection, date, searchTerm };
    // Finde ein Profil, das den aktuellen Sucheinstellungen entspricht.
    const matchingProfile = profiles.find((profile) =>
      areFiltersEqual(profile, currentSearchState)
    );

    setActiveProfileId(matchingProfile ? matchingProfile.id : null);
  }, [rowSelection, date, searchTerm, profiles]);

  const applyProfile = useCallback(
    (profileId: number) => {
      const profile = profiles.find((p) => p.id === profileId);
      if (profile) {
        const newRowSelection = profile.rowSelection;
        const newDate = {
          from: profile.date.from ? new Date(profile.date.from) : undefined,
          to: profile.date.to ? new Date(profile.date.to) : undefined,
        };
        const newSearchTerm = profile.searchTerm;

        // Den globalen State mit den neuen Werten aktualisieren.
        setRowSelection(newRowSelection);
        setDate(newDate);
        setSearchTerm(newSearchTerm);
        setActiveProfileId(profile.id);

        // Die URL mit den neuen Werten bauen, nicht mit den alten aus dem Hook-State.
        const resultsURL = buildResultsUrl({
          rowSelection: newRowSelection,
          date: newDate,
          searchTerm: newSearchTerm,
        });
        navigate(resultsURL, { replace: true });
      }
    },
    [profiles, setRowSelection, setDate, setSearchTerm, navigate],
  );

  const clearActiveProfile = useCallback(() => {
    setActiveProfileId(null);
    // Setze die Suchparameter auf ihre Standardwerte zurück
    setRowSelection({});
    const now = new Date();
    setDate({ from: startOfMonth(now), to: endOfMonth(now) });
    setSearchTerm("");
    navigate("/", { replace: true });
  }, [setRowSelection, setDate, setSearchTerm, navigate]);

  const updateProfile = useCallback(
    async (profileId: number) => {
      const updatedProfile = await apiFetch(`/api/profiles/${profileId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rowSelection,
          startDate: formatDateForApi(date?.from),
          endDate: formatDateForApi(date?.to),
          searchTerm,
        }),
      });
      // Ersetze nur das eine, aktualisierte Profil im State.
      setProfiles((prevProfiles) =>
        prevProfiles.map((p) => (p.id === profileId ? updatedProfile : p)),
      );
    },
    [rowSelection, date, searchTerm],
  );

  const saveProfile = useCallback(
    async (name: string) => {
      const newProfile = await apiFetch("/api/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          settings: {
            rowSelection,
            startDate: formatDateForApi(date?.from),
            endDate: formatDateForApi(date?.to),
            searchTerm,
          },
        }),
      });

      setProfiles((prevProfiles) => [...prevProfiles, newProfile]);
    },

    [rowSelection, date, searchTerm],
  );

  const toggleProfileNotifications = useCallback(
    async (profileId: number, emailNotifications: boolean) => {
      const updatedProfile = await apiFetch(
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
      // Entferne das gelöschte Profil aus dem State, um ein Neuladen zu vermeiden.
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
