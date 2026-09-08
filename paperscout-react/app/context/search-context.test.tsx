import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { SearchProvider, useSearch } from "./search-context";

const wrapper = ({ children }: { children: ReactNode }) => (
  <SearchProvider>{children}</SearchProvider>
);

describe("useSearch", () => {
  it("throws when used outside of a SearchProvider", () => {
    expect(() => renderHook(() => useSearch())).toThrow(/SearchProvider/);
  });

  it("initializes with the current month as the default range", async () => {
    const { result } = renderHook(() => useSearch(), { wrapper });
    await waitFor(() => expect(result.current.isInitialized).toBe(true));
    expect(result.current.date?.from).toBeInstanceOf(Date);
    expect(result.current.date?.to).toBeInstanceOf(Date);
  });

  it("normalizes the time component when setting a date range", async () => {
    const { result } = renderHook(() => useSearch(), { wrapper });
    await waitFor(() => expect(result.current.isInitialized).toBe(true));

    act(() => {
      result.current.setDate({
        from: new Date(2024, 2, 7, 15, 30),
        to: new Date(2024, 2, 20, 23, 59),
      });
    });

    expect(result.current.date?.from?.getHours()).toBe(0);
    expect(result.current.date?.to?.getHours()).toBe(0);
  });

  it("persists the search term to sessionStorage", async () => {
    const { result } = renderHook(() => useSearch(), { wrapper });
    await waitFor(() => expect(result.current.isInitialized).toBe(true));

    act(() => result.current.setSearchTerm("neurons"));

    await waitFor(() =>
      expect(sessionStorage.getItem("ps_search_term")).toBe("neurons"),
    );
  });

  it("restores the row selection from sessionStorage on mount", async () => {
    sessionStorage.setItem("ps_row_selection", JSON.stringify({ J1: true }));

    const { result } = renderHook(() => useSearch(), { wrapper });
    await waitFor(() => expect(result.current.isInitialized).toBe(true));

    expect(result.current.rowSelection).toEqual({ J1: true });
  });
});
