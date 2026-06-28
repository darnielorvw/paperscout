
const API_BASE_URL = "http://localhost:8000";

export class UnauthorizedError extends Error {
  constructor(message = "Unauthorized") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

/**
 * Ein globaler Wrapper für die `fetch`-API, der automatisch
 * bei einem 401-Fehler (Unauthorized) zur Login-Seite weiterleitet.
 *
 * @param route Der API-Endpunkt, der aufgerufen werden soll (z.B. /api/login).
 * @param options Die `fetch`-Optionen.
 * @param handleUnauthorized Ob bei einem 401-Fehler automatisch umgeleitet werden soll.
 * @returns Eine Promise, die mit den JSON-Daten der API-Antwort aufgelöst wird.
 */
export async function apiFetch(route: string, options: RequestInit = {}, handleUnauthorized = true): Promise<any> {
  const token = localStorage.getItem("auth_token");
  const url = `${API_BASE_URL}${route}`;

  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });

  // Wenn der Server einen 401-Fehler zurückgibt (Token ungültig/abgelaufen),
  // leiten wir den Benutzer zur Login-Seite weiter.
  if (response.status === 401) {    
    if (handleUnauthorized) {
      // Token entfernen, um Endlosschleifen zu vermeiden
      localStorage.removeItem("auth_token");
      // Zur Login-Seite navigieren. window.location, da wir außerhalb von React sind.
      window.location.href = "/login";
      // Wir werfen einen Fehler, um die weitere Ausführung zu stoppen.
      throw new UnauthorizedError("Session abgelaufen. Bitte neu einloggen.");
    } else {
      throw new UnauthorizedError("Token ist ungültig.");
    }
  }

  // Eine HEAD-Anfrage hat keinen Body, also können wir .json() nicht aufrufen.
  if (options.method?.toUpperCase() === 'HEAD') {
    return; // Einfach erfolgreich zurückkehren
  }

  return response.json();
}