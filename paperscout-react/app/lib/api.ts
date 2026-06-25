
/**
 * Ein globaler Wrapper für die `fetch`-API, der automatisch
 * bei einem 401-Fehler (Unauthorized) zur Login-Seite weiterleitet.
 *
 * @param url Die URL, die aufgerufen werden soll.
 * @param options Die `fetch`-Optionen.
 * @returns Eine Promise, die mit den JSON-Daten der API-Antwort aufgelöst wird.
 */
export async function apiFetch(url: string, options: RequestInit = {}) {
  const response = await fetch(url, options);
  
  return response.json();
}