from typing import Any, Dict, List

import httpx


class SearchService:
    def __init__(self):
        # OpenAlex bittet um eine E-Mail im Header für den "Polite Pool" (schnellere Antwortzeiten)
        self.headers = {"User-Agent": "PaperScoutBot/1.0 (mailto:ihre-mail@fh-swf.de)"}
        self.base_url = "https://api.openalex.org"

    async def _fetch_from_api(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Zentrale Methode für API-Anfragen, um redundanten Code zu vermeiden."""
        async with httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=10.0) as client:
            try:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Fehler bei OpenAlex-Abfrage ({endpoint}): {e}")
                return {}
            
    async def fetch_external_journals(self) -> List[Dict[str, Any]]:
        """Sucht extern bei OpenAlex nach Journals (Sources)."""
        params = {"filter": "type:journal", "per_page": 50}
        data = await self._fetch_from_api("/sources", params)
        print(data)
        return data.get("results", [])


    async def search(self, journal_ids: List[str], keywords: str, from_date: str, to_date: str, limit: int) -> List[Dict[str, Any]]:
        """Sucht nach wissenschaftlichen Artikeln (Works) innerhalb spezifischer Journals in einem Zeitraum."""
        # Bereinige die IDs (wir brauchen nur den Teil nach dem letzten Slash, z.B. S123)
        # OpenAlex erlaubt mehrere IDs getrennt durch ein Pipe-Symbol |
        clean_ids = "|".join([jid.split("/")[-1] for jid in journal_ids])

        # OpenAlex Filter: Quelle(n), Startdatum und Enddatum
        filter_str = f"primary_location.source.id:{clean_ids},from_publication_date:{from_date},to_publication_date:{to_date}"

        params = {
            "search": keywords,
            "filter": filter_str,
            "per_page": limit
        }

        # Abfrage des /works Endpunkts für Artikel statt /sources für Journals
        data = await self._fetch_from_api("/works", params)

        results = []
        for work in data.get("results", []):
            results.append({
                "id": work.get("id"),
                "title": work.get("title"),
                "doi": work.get("doi"),
                "publication_date": work.get("publication_date"),
                "journal_name": work.get("primary_location", {}).get("source", {}).get("display_name"),
                "abstract": self._extract_abstract(work.get("abstract_inverted_index", {}))
            })
        return results


    def _extract_abstract(self, inverted_index: Dict[str, List[int]]) -> str:
        """OpenAlex liefert Abstracts aus Urheberrechtsgründen 'invertiert'. Das baut es wieder zusammen."""
        if not inverted_index:
            return "Kein Abstract verfügbar."
        
        # Rekonstruiere den Text aus dem Positions-Index
        word_positions = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions[pos] = word
                
        sorted_words = [word_positions[p] for p in sorted(word_positions.keys())]
        return " ".join(sorted_words)