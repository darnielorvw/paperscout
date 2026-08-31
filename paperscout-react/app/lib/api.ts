
// Configurable via `VITE_API_BASE_URL` (e.g. the backend's Cloudflare tunnel URL).
// Falls back to localhost for plain local development.
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class UnauthorizedError extends Error {
  constructor(message = "Unauthorized") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

interface ApiFetchOptions extends RequestInit {
  // Allows the caller to specify the expected response type.
  responseType?: 'json' | 'blob' | 'text';
}

/**
 * A global wrapper for the `fetch` API that automatically
 * redirects to the login page on a 401 error (Unauthorized).
 *
 * @param route The API endpoint to call (e.g. /api/login).
 * @param options The `fetch` options.
 * @param handleUnauthorized Whether to automatically redirect on a 401 error.
 * @returns A promise that resolves with the JSON data of the API response.
 */
export async function apiFetch<T = any>(
  route: string,
  options: ApiFetchOptions = {},
  handleUnauthorized = true,
): Promise<T> {
  const token = localStorage.getItem("auth_token");
  const url = `${API_BASE_URL}${route}`;

  // Extract our custom option before passing the rest to `fetch`.
  const { responseType = 'json', ...fetchOptions } = options;

  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...fetchOptions, headers });

  // If the server returns a 401 error (token invalid/expired),
  // we redirect the user to the login page.
  if (response.status === 401) {
    if (handleUnauthorized) {
      // Remove the token to avoid infinite loops
      localStorage.removeItem("auth_token");
      // Navigate to the login page. window.location since we're outside of React here.
      window.location.href = "/login";
      // Throw an error to stop further execution.
      throw new UnauthorizedError("Session expired. Please log in again.");
    } else {
      throw new UnauthorizedError("Token is invalid.");
    }
  }

  // Check whether the request failed in general (e.g. 400, 404, 500)
  if (!response.ok) {
    // Try to read the error details from the body,
    // since the API often sends a JSON response with a 'detail' property.
    const errorData = await response.json().catch(() => ({})); // Empty object if the body isn't JSON
    const errorMessage = errorData.detail || `API error: ${response.status} ${response.statusText}`;
    // Throw a generic error, which is then caught in the calling component.
    throw new Error(errorMessage);
  }

  if (options.method?.toUpperCase() === 'HEAD') {
    return undefined as T;
  }

  // If the response has a 204 No Content status, there's no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }

  // Process the response body based on the requested type.
  switch (responseType) {
    case 'blob':
      return response.blob() as Promise<T>;
    case 'text':
      return response.text() as Promise<T>;
    default: // 'json'
      return response.json() as Promise<T>;
  }
}