import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();
vi.mock("~/lib/api", () => ({ apiFetch: (...args: unknown[]) => apiFetch(...args) }));

import { JournalsProvider, useJournals } from "./journals-context";

const wrapper = ({ children }: { children: ReactNode }) => (
  <JournalsProvider>{children}</JournalsProvider>
);

beforeEach(() => {
  apiFetch.mockReset();
});

describe("useJournals", () => {
  it("throws when used outside of a JournalsProvider", () => {
    expect(() => renderHook(() => useJournals())).toThrow(/JournalsProvider/);
  });

  it("loads the journal list once on mount", async () => {
    apiFetch.mockResolvedValue({ results: [{ id: "J1", name: "Journal One" }] });

    const { result } = renderHook(() => useJournals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(apiFetch).toHaveBeenCalledWith("/api/journals");
    expect(result.current.journals).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it("exposes the error message when the request fails", async () => {
    apiFetch.mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => useJournals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).toBe("boom");
    expect(result.current.journals).toEqual([]);
  });

  it("refetches when reloadJournals is called", async () => {
    apiFetch.mockResolvedValue({ results: [] });
    const { result } = renderHook(() => useJournals(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    apiFetch.mockResolvedValue({ results: [{ id: "J2", name: "New" }] });
    await result.current.reloadJournals();

    await waitFor(() => expect(result.current.journals).toHaveLength(1));
  });
});
