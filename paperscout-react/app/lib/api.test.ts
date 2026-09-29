import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, UnauthorizedError } from "./api";

function mockResponse(
  body: unknown,
  { status = 200, json = true }: { status?: number; json?: boolean } = {},
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: json
      ? () => Promise.resolve(body)
      : () => Promise.reject(new Error("not json")),
    text: () => Promise.resolve(String(body)),
    blob: () => Promise.resolve(new Blob([String(body)])),
  } as unknown as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;
let location: { href: string };

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  location = { href: "" };
  Object.defineProperty(window, "location", {
    value: location,
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("sends the bearer token from localStorage", async () => {
    localStorage.setItem("auth_token", "tok123");
    fetchMock.mockResolvedValue(mockResponse({ ok: true }));

    await apiFetch("/api/x");

    const headers = (fetchMock.mock.calls[0][1] as RequestInit).headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok123");
  });

  it("omits the Authorization header when no token is stored", async () => {
    fetchMock.mockResolvedValue(mockResponse({}));

    await apiFetch("/api/x");

    const headers = (fetchMock.mock.calls[0][1] as RequestInit).headers as Headers;
    expect(headers.has("Authorization")).toBe(false);
  });

  it("on 401 with handleUnauthorized clears the token and redirects to /login", async () => {
    localStorage.setItem("auth_token", "tok");
    fetchMock.mockResolvedValue(mockResponse({}, { status: 401 }));

    await expect(apiFetch("/api/x")).rejects.toBeInstanceOf(UnauthorizedError);
    expect(localStorage.getItem("auth_token")).toBeNull();
    expect(location.href).toBe("/login");
  });

  it("on 401 without handleUnauthorized throws but does not redirect", async () => {
    localStorage.setItem("auth_token", "tok");
    fetchMock.mockResolvedValue(mockResponse({}, { status: 401 }));

    await expect(apiFetch("/api/x", {}, false)).rejects.toBeInstanceOf(UnauthorizedError);
    expect(localStorage.getItem("auth_token")).toBe("tok");
    expect(location.href).toBe("");
  });

  it("throws the API's `detail` message on a non-ok response", async () => {
    fetchMock.mockResolvedValue(mockResponse({ detail: "Nope" }, { status: 400 }));

    await expect(apiFetch("/api/x")).rejects.toThrow("Nope");
  });

  it("falls back to a generic message when the error body is not JSON", async () => {
    fetchMock.mockResolvedValue(mockResponse("boom", { status: 500, json: false }));

    await expect(apiFetch("/api/x")).rejects.toThrow(/API error: 500/);
  });

  it("returns undefined for a 204 response without parsing a body", async () => {
    fetchMock.mockResolvedValue(mockResponse(null, { status: 204, json: false }));

    await expect(apiFetch("/api/x")).resolves.toBeUndefined();
  });

  it("returns undefined for a HEAD request", async () => {
    fetchMock.mockResolvedValue(mockResponse({ a: 1 }));

    await expect(apiFetch("/api/x", { method: "HEAD" })).resolves.toBeUndefined();
  });

  it("returns text when responseType is 'text'", async () => {
    fetchMock.mockResolvedValue(mockResponse("hello"));

    await expect(apiFetch("/api/x", { responseType: "text" })).resolves.toBe("hello");
  });

  it("returns a blob when responseType is 'blob'", async () => {
    fetchMock.mockResolvedValue(mockResponse("bytes"));

    await expect(apiFetch("/api/x", { responseType: "blob" })).resolves.toBeInstanceOf(Blob);
  });
});
