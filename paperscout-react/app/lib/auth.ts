import { redirect } from "react-router";

/**
 * Eine client-seitige Hilfsfunktion, die prüft, ob ein Authentifizierungs-Token
 * im `localStorage` vorhanden ist. Wenn nicht, wird eine sofortige Umleitung
 * zur Login-Seite ausgelöst.
 *
 * Diese Funktion sollte am Anfang jedes `clientLoader` für geschützte
 * Routen aufgerufen werden.
 *
 * @returns {void} Wirft eine `Response` (Umleitung), wenn kein Token vorhanden ist.
 */
export function protectPage(): void {
  // Dieser Code läuft nur im Browser, daher ist der Zugriff auf localStorage sicher.
  const token = localStorage.getItem("auth_token");

  if (!token) throw redirect("/login");
}