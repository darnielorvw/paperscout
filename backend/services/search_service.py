import os
import re
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from lib.cache import LRUCache

load_dotenv()


class SearchService:
    def __init__(self):
        self.base_url = "https://api.openalex.org"
        
        # Initialisiere unsere neue, ausgelagerte Cache-Klasse
        self.cache = LRUCache(max_size=100, ttl=3600)

    async def _fetch_from_api(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Zentrale Methode für API-Anfragen, um redundanten Code zu vermeiden."""
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=10.0
        ) as client:
            try:
                api_key = os.environ.get("API_KEY")
                params = {"api_key": api_key, **params}
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
        return data.get("results", [])

    async def search(
        self,
        journal_ids: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
        limit: int,
        page: int,
    ) -> Dict[str, Any]:
        """Sucht nach wissenschaftlichen Artikeln (Works) innerhalb spezifischer Journals in einem Zeitraum."""
        # 1. Eindeutigen und stabilen Cache-Schlüssel aus den Parametern erstellen
        # Wir sortieren die journal_ids, damit die Reihenfolge keine Rolle spielt.
        key_parts = (
            tuple(sorted(journal_ids)),
            keywords,
            from_date,
            to_date,
            limit,
            page,
        )
        cache_key = str(key_parts)

        # 2. Im Cache nach einem gültigen Eintrag suchen
        cached_data = self.cache.get(cache_key)
        if cached_data:
            print(f"✅ Treffer im Backend-Cache für Schlüssel: {cache_key[:50]}...")
            return cached_data

        # Bereinige die IDs (wir brauchen nur den Teil nach dem letzten Slash, z.B. S123)
        # OpenAlex erlaubt mehrere IDs getrennt durch ein Pipe-Symbol |
        clean_ids = "|".join([jid.split("/")[-1] for jid in journal_ids])

        # OpenAlex Filter: Quelle(n), Startdatum und Enddatum
        filter_str = f"primary_location.source.id:{clean_ids},from_publication_date:{from_date},to_publication_date:{to_date}"
        select = "id,title,doi,publication_date,primary_location,abstract_inverted_index,primary_topic"

        params = {
            "search": keywords,
            "filter": filter_str,
            "per_page": limit,
            "page": page,
            "select": select,
        }

        # Abfrage des /works Endpunkts für Artikel statt /sources für Journals
        data = await self._fetch_from_api("/works", params)
        


        meta = data.get("meta", {})
        results = []
        for work in data.get("results", []):
            results.append(
                {
                    "id": work.get("id"),
                    "title": work.get("title"),
                    "doi": work.get("doi"),
                    "publication_date": work.get("publication_date"),
                    "journal_name": work.get("primary_location", {})
                    .get("source", {})
                    .get("display_name"),
                    "abstract": self._extract_abstract(
                        work.get("abstract_inverted_index", {})
                    ),
                    "topic": (work.get("primary_topic") or {}).get("display_name"),
                    
                }
            )
        data = {"meta": meta, "results": results}

        if results:
            self.cache.set(cache_key, data)
        return data

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
        abstract = " ".join(sorted_words)
        return re.sub(r"^(Abstract|ABSTRACT)\s*", "", abstract)
