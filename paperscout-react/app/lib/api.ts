
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

  // Prüfen, ob die Anfrage generell fehlgeschlagen ist (z.B. 400, 404, 500)
  if (!response.ok) {
    // Wir versuchen, die Fehlerdetails aus dem Body zu lesen,
    // da die API oft eine JSON-Antwort mit einer 'detail'-Eigenschaft sendet.
    const errorData = await response.json().catch(() => ({})); // Leeres Objekt, falls Body kein JSON ist
    const errorMessage = errorData.detail || `API-Fehler: ${response.status} ${response.statusText}`;
    // Wir werfen einen generischen Fehler, der dann in der aufrufenden Komponente gefangen wird.
    throw new Error(errorMessage);
  }

  // Eine HEAD-Anfrage hat keinen Body, also können wir .json() nicht aufrufen.
  if (options.method?.toUpperCase() === 'HEAD') {
    return; // Einfach erfolgreich zurückkehren
  }

  // Wenn die Antwort einen 204 No Content Status hat, gibt es keinen Body zum Parsen.
  if (response.status === 204) {
    return; // Einfach erfolgreich zurückkehren
  }

  return response.json();
}