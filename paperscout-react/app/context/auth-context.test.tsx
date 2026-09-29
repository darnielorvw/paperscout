import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UnauthorizedError } from "~/lib/api";

const apiFetch = vi.fn();
const navigate = vi.fn();

vi.mock("~/lib/api", async (orig) => {
  const actual = await orig<typeof import("~/lib/api")>();
  return { ...actual, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});

vi.mock("react-router", async (orig) => {
  const actual = await orig<typeof import("react-router")>();
  return { ...actual, useNavigate: () => navigate };
});

import { AuthProvider, useAuth } from "./auth-context";

const wrapper = ({ children }: { children: ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

const USER = { id: 1, name: "Ada", email: "a@b.de", institution: "b.de", is_admin: false };

beforeEach(() => {
  apiFetch.mockReset();
  navigate.mockReset();
});

describe("useAuth", () => {
  it("throws when used outside of an AuthProvider", () => {
    expect(() => renderHook(() => useAuth())).toThrow(/AuthProvider/);
  });

  it("starts unauthenticated when no token is stored", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("loads the current user on mount when a token exists", async () => {
    localStorage.setItem("auth_token", "tok");
    apiFetch.mockResolvedValue(USER);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.email).toBe("a@b.de");
    expect(apiFetch).toHaveBeenCalledWith("/api/users/me", { method: "GET" }, false);
  });

  it("drops an invalid token during the initial check", async () => {
    localStorage.setItem("auth_token", "bad");
    apiFetch.mockRejectedValue(new UnauthorizedError());

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(localStorage.getItem("auth_token")).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("login stores the token, loads the user and navigates home", async () => {
    apiFetch.mockResolvedValue(USER);
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login("new-token");
    });

    expect(localStorage.getItem("auth_token")).toBe("new-token");
    expect(result.current.user?.email).toBe("a@b.de");
    expect(navigate).toHaveBeenCalledWith("/");
  });

  it("refreshSession replaces the token without navigating", async () => {
    apiFetch.mockResolvedValue(USER);
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.refreshSession("refreshed");
    });

    expect(localStorage.getItem("auth_token")).toBe("refreshed");
    expect(navigate).not.toHaveBeenCalled();
  });

  it("logout clears the token and redirects to /login", async () => {
    localStorage.setItem("auth_token", "tok");
    apiFetch.mockResolvedValue(USER);
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

    act(() => result.current.logout());

    expect(localStorage.getItem("auth_token")).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(navigate).toHaveBeenCalledWith("/login");
  });
});
