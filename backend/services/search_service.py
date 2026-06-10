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

    async def search_open_access_papers(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        params = {
            "search": query,
            "filter": "is_oa:true",  # STRIKTE FILTERUNG: Nur Open Access!
            "per_page": limit,
            "sort": "publication_year:desc" # Neueste zuerst
        }
        
        data = await self._fetch_from_api("/works", params)
        
        results = []
        for work in data.get("results", []):
            # Relevante Daten für dein React-Frontend extrahieren
            results.append({
                "id": work.get("id"),
                "doi": work.get("doi"),
                "title": work.get("title"),
                "publication_year": work.get("publication_year"),
                "authors": [auth.get("author", {}).get("display_name") for auth in work.get("authorships", [])],
                "abstract": self._extract_abstract(work.get("abstract_inverted_index")),
                "oa_url": work.get("open_access", {}).get("oa_url") # Direkt-Link zum PDF/Volltext
            })
        return results

    async def search_journals(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Sucht nach Journals (in OpenAlex als 'Sources' bezeichnet)."""
        params = {
            "search": query,
            "per_page": limit,
            "filter": "type:journal"
        }
        
        data = await self._fetch_from_api("/sources", params)
        
        results = []
        for source in data.get("results", []):
            # Relevante Daten für Journals extrahieren
            results.append({
                "id": source.get("id"),
                "display_name": source.get("display_name"),
                "issn": source.get("issn_l"),
                "publisher": source.get("host_organization_name"),
                "is_oa": source.get("is_oa", False),
                "works_count": source.get("works_count", 0),
                "homepage_url": source.get("homepage_url")
            })
        return data.get("results", [])


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