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

        # Initialize our extracted cache class
        self.cache = LRUCache(max_size=100, ttl=3600)

    async def _fetch_from_api(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Central method for API requests, to avoid redundant code."""
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
                print(f"Error during OpenAlex request ({endpoint}): {e}")
                return {}

    async def fetch_journal_by_name(self, name: str) -> Dict[str, Any] | None:
        """Looks up a single journal on OpenAlex by (approximate) name.

        Returns the best-matching source, preferring an exact (case-insensitive)
        name match over OpenAlex's plain relevance ranking, or None if nothing
        was found.
        """
        params = {"search": name, "filter": "type:journal", "per_page": 5}
        data = await self._fetch_from_api("/sources", params)
        results = data.get("results", [])
        if not results:
            return None

        for result in results:
            if (result.get("display_name") or "").strip().lower() == name.strip().lower():
                return result
        return results[0]

    async def fetch_titles_by_ids(self, work_ids: List[str]) -> Dict[str, str]:
        """Looks up the titles for a list of short OpenAlex work IDs (e.g. 'W123')."""
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
        """Searches for scientific articles (works) within specific journals in a date range."""
        # 1. Build a unique and stable cache key from the parameters
        # We sort the journal_ids so that order doesn't matter.
        key_parts = (
            tuple(sorted(journal_ids)),
            keywords,
            from_date,
            to_date,
            limit,
            page,
        )
        cache_key = str(key_parts)

        # 2. Look for a valid entry in the cache
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        # Clean up the IDs (we only need the part after the last slash, e.g. S123)
        # OpenAlex allows multiple IDs separated by a pipe symbol |
        clean_ids = "|".join([jid.split("/")[-1] for jid in journal_ids])

        # OpenAlex filter: source(s), start date and end date
        filter_str = f"primary_location.source.id:{clean_ids},from_publication_date:{from_date},to_publication_date:{to_date},is_oa:true,has_fulltext:true"
        select = "id,title,doi,publication_date,primary_location,abstract_inverted_index,primary_topic,authorships,best_oa_location"

        params = {
            "search": keywords,
            "filter": filter_str,
            "per_page": limit,
            "page": page,
            "select": select,
        }

        # Query the /works endpoint for articles instead of /sources for journals
        data = await self._fetch_from_api("/works", params)

        meta = data.get("meta", {})
        results = []
        for work in data.get("results", []):
            # Safe extraction of nested objects.
            # 'or {}' catches both missing keys and 'None' values.
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
        """OpenAlex delivers abstracts 'inverted' for copyright reasons. This reconstructs them."""
        if not inverted_index:  # Catches None or an empty dict
            return "No abstract available."

        # Reconstruct the text from the position index
        word_positions = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions[pos] = word

        sorted_words = [word_positions[p] for p in sorted(word_positions.keys())]
        abstract = " ".join(sorted_words)
        return re.sub(r"^(Abstract|ABSTRACT)\s*", "", abstract)
