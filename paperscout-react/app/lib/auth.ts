import { redirect } from "react-router";

/**
 * A client-side helper function that checks whether an authentication token
 * is present in `localStorage`. If not, it triggers an immediate redirect
 * to the login page.
 *
 * This function should be called at the start of every `clientLoader` for
 * protected routes.
 *
 * @returns {void} Throws a `Response` (redirect) if no token is present.
 */
export function protectPage(): void {
  // This code only runs in the browser, so accessing localStorage is safe.
  const token = localStorage.getItem("auth_token");

  if (!token) throw redirect("/login");
}