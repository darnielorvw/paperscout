import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();
const navigate = vi.fn();

vi.mock("~/lib/api", () => ({ apiFetch: (...args: unknown[]) => apiFetch(...args) }));
vi.mock("react-router", async (orig) => {
  const actual = await orig<typeof import("react-router")>();
  return { ...actual, useNavigate: () => navigate };
});

import { SearchProvider, useSearch } from "./search-context";
import { ProfileProvider, useProfiles } from "./profile-context";

const wrapper = ({ children }: { children: ReactNode }) => (
  <SearchProvider>
    <ProfileProvider>{children}</ProfileProvider>
  </SearchProvider>
);

const PROFILE = {
  id: 1,
  name: "Cancer",
  rowSelection: { J1: true },
  searchTerm: "tumor",
  emailNotifications: true,
};

/** Renders both hooks so a test can drive the search state and read profiles. */
function renderProfiles() {
  return renderHook(
    () => ({ profiles: useProfiles(), search: useSearch() }),
    { wrapper },
  );
}

beforeEach(() => {
  apiFetch.mockReset();
  navigate.mockReset();
});

describe("useProfiles", () => {
  it("throws when used outside of a ProfileProvider", () => {
    apiFetch.mockResolvedValue({ results: [] });
    expect(() => renderHook(() => useProfiles())).toThrow(/ProfileProvider/);
  });

  it("loads the user's profiles on mount", async () => {
    apiFetch.mockResolvedValueOnce({ results: [PROFILE] });

    const { result } = renderProfiles();

    await waitFor(() => expect(result.current.profiles.isLoading).toBe(false));
    expect(apiFetch).toHaveBeenCalledWith("/api/profiles");
    expect(result.current.profiles.profiles).toEqual([PROFILE]);
  });

  it("saveProfile POSTs the current search state and appends the new profile", async () => {
    apiFetch.mockResolvedValueOnce({ results: [] });
    const { result } = renderProfiles();
    await waitFor(() => expect(result.current.profiles.isLoading).toBe(false));

    act(() => result.current.search.setRowSelection({ J9: true }));
    act(() => result.current.search.setSearchTerm("genome"));

    apiFetch.mockResolvedValueOnce({ ...PROFILE, id: 5, name: "New" });
    await act(async () => {
      await result.current.profiles.saveProfile("New");
    });

    const [route, options] = apiFetch.mock.calls.at(-1)!;
    expect(route).toBe("/api/profiles");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      name: "New",
      settings: { rowSelection: { J9: true }, searchTerm: "genome" },
    });
    expect(result.current.profiles.profiles.map((p) => p.id)).toContain(5);
  });

  it("updateProfile PUTs to the id and replaces that profile in place", async () => {
    apiFetch.mockResolvedValueOnce({ results: [PROFILE] });
    const { result } = renderProfiles();
    await waitFor(() => expect(result.current.profiles.profiles).toHaveLength(1));

    apiFetch.mockResolvedValueOnce({ ...PROFILE, searchTerm: "changed" });
    await act(async () => {
      await result.current.profiles.updateProfile(1);
    });

    const [route, options] = apiFetch.mock.calls.at(-1)!;
    expect(route).toBe("/api/profiles/1");
    expect(options.method).toBe("PUT");
    expect(result.current.profiles.profiles[0].searchTerm).toBe("changed");
  });

  it("deleteProfile DELETEs the id and drops it from the list", async () => {
    apiFetch.mockResolvedValueOnce({ results: [PROFILE] });
    const { result } = renderProfiles();
    await waitFor(() => expect(result.current.profiles.profiles).toHaveLength(1));

    apiFetch.mockResolvedValueOnce(undefined);
    await act(async () => {
      await result.current.profiles.deleteProfile(1);
    });

    expect(apiFetch).toHaveBeenLastCalledWith("/api/profiles/1", { method: "DELETE" });
    expect(result.current.profiles.profiles).toEqual([]);
  });

  it("toggleProfileNotifications PATCHes the notifications endpoint", async () => {
    apiFetch.mockResolvedValueOnce({ results: [PROFILE] });
    const { result } = renderProfiles();
    await waitFor(() => expect(result.current.profiles.profiles).toHaveLength(1));

    apiFetch.mockResolvedValueOnce({ ...PROFILE, emailNotifications: false });
    await act(async () => {
      await result.current.profiles.toggleProfileNotifications(1, false);
    });

    const [route, options] = apiFetch.mock.calls.at(-1)!;
    expect(route).toBe("/api/profiles/1/notifications");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ emailNotifications: false });
    expect(result.current.profiles.profiles[0].emailNotifications).toBe(false);
  });

  it("applyProfile copies the profile filters into the search state and navigates to /results", async () => {
    apiFetch.mockResolvedValueOnce({ results: [PROFILE] });
    const { result } = renderProfiles();
    await waitFor(() => expect(result.current.profiles.profiles).toHaveLength(1));

    act(() => result.current.profiles.applyProfile(1));

    expect(result.current.search.rowSelection).toEqual({ J1: true });
    expect(result.current.search.searchTerm).toBe("tumor");
    expect(navigate).toHaveBeenCalledWith(
      expect.stringContaining("/results?"),
      { replace: true },
    );
  });

  it("marks the profile active once the search state matches it", async () => {
    apiFetch.mockResolvedValueOnce({ results: [PROFILE] });
    const { result } = renderProfiles();
    await waitFor(() => expect(result.current.profiles.profiles).toHaveLength(1));

    act(() => result.current.profiles.applyProfile(1));

    await waitFor(() =>
      expect(result.current.profiles.activeProfileId).toBe(1),
    );
  });
});
