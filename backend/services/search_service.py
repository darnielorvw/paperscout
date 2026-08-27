import os
import re
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from lib.cache import LRUCache

load_dotenv()

def format_authors_apa(authorships: list) -> str:
    if not authorships:
        return ""
    
    first = authorships[0]["author"]["display_name"].split()[-1]
    
    if len(authorships) == 1:
        return first
    if len(authorships) == 2:
        second = authorships[1]["author"]["display_name"].split()[-1]
        return f"{first} & {second}"
    
    return f"{first} et al."


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
        """Sucht extern bei OpenAlex nach Journals (Sources) für den Import."""
        params = {"filter": "type:journal", "per_page": 50}
        data = await self._fetch_from_api("/sources", params)
        return data.get("results", [])

    async def fetch_titles_by_ids(self, work_ids: List[str]) -> Dict[str, str]:
        """Schlägt die Titel zu einer Liste kurzer OpenAlex-Work-IDs (z.B. 'W123') nach."""
        if not work_ids:
            return {}

        clean_ids = [wid.split("/")[-1] for wid in work_ids]
        params = {
            "filter": f"openalex_id:{'|'.join(clean_ids)}",
            "per_page": len(clean_ids),
            "select": "id,title",
        }
        data = await self._fetch_from_api("/works", params)
        return {
            work.get("id", "").split("/")[-1]: work.get("title")
            for work in data.get("results", [])
            if work.get("id") and work.get("title")
        }

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
            return cached_data

        # Bereinige die IDs (wir brauchen nur den Teil nach dem letzten Slash, z.B. S123)
        # OpenAlex erlaubt mehrere IDs getrennt durch ein Pipe-Symbol |
        clean_ids = "|".join([jid.split("/")[-1] for jid in journal_ids])

        # OpenAlex Filter: Quelle(n), Startdatum und Enddatum
        filter_str = f"primary_location.source.id:{clean_ids},from_publication_date:{from_date},to_publication_date:{to_date},is_oa:true,has_fulltext:true"
        select = "id,title,doi,publication_date,primary_location,abstract_inverted_index,primary_topic,authorships,best_oa_location"

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
            # Sichere Extraktion von verschachtelten Objekten.
            # 'or {}' fängt sowohl fehlende Schlüssel als auch 'None'-Werte ab.
            primary_loc = work.get("primary_location") or {}
            source = primary_loc.get("source") or {}
            best_oa = work.get("best_oa_location") or {}
            primary_topic = work.get("primary_topic") or {}

            results.append(
                {
                    "id": work.get("id"),
                    "title": work.get("title"),
                    "doi": work.get("doi"),
                    "publication_date": work.get("publication_date"),
                    "journal_name": source.get("display_name"),
                    "pdf_url": best_oa.get("pdf_url"),
                    "pdf_landing_page": best_oa.get("landing_page_url"),
                    "abstract": self._extract_abstract(work.get("abstract_inverted_index")),
                    "topic": primary_topic.get("display_name"),
                    "author": format_authors_apa(work.get("authorships", [])),
                    
                }
            )
        data = {"meta": meta, "results": results}

        if results:
            self.cache.set(cache_key, data)
        return data

    def _extract_abstract(self, inverted_index: Dict[str, List[int]]) -> str:
        """OpenAlex liefert Abstracts aus Urheberrechtsgründen 'invertiert'. Das baut es wieder zusammen."""
        if not inverted_index:  # Fängt None oder leeres Dictionary ab
            return "Kein Abstract verfügbar."

        # Rekonstruiere den Text aus dem Positions-Index
        word_positions = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions[pos] = word

        sorted_words = [word_positions[p] for p in sorted(word_positions.keys())]
        abstract = " ".join(sorted_words)
        return re.sub(r"^(Abstract|ABSTRACT)\s*", "", abstract)
