import os
import re
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from lib.cache import LRUCache

load_dotenv()

# --- Best of both worlds -----------------------------------------------------
# Crossref is only used for one thing: finding which papers appeared in a set of
# journals within a date range, filtered by the *journal issue* date. Every other
# field (title, authors, abstract, topic, OA PDF, has_fulltext, the paper's own
# publication date) comes from OpenAlex, looked up by DOI.
#
# Crossref date filters:
#   - "from-pub-date"       -> `published`       (in this journal, print OR online)
#   - "from-print-pub-date" -> `published-print` (the printed issue date only)
#   - "from-online-pub-date"-> `published-online`
# We filter on the printed issue date. Note: online-only journals (PLOS, eLife,
# Nature Communications, ...) have no `published-print` and therefore return
# nothing here - switch to "from-pub-date"/"until-pub-date" to include them.
DATE_FILTER_FROM = "from-pub-date"
DATE_FILTER_UNTIL = "until-pub-date"

# Crossref: we only need the DOI, the journal issue date and the issue label.
_CROSSREF_SELECT = "DOI,title,container-title,published-print,published,issued,volume,issue"

# OpenAlex: the full metadata for a work.
_OPENALEX_SELECT = (
    "id,title,doi,publication_date,primary_location,abstract_inverted_index,"
    "primary_topic,authorships,best_oa_location,has_fulltext"
)


def format_authors_apa(authorships: list) -> str:
    """Short APA-style author string from an OpenAlex `authorships` list."""
    names = [
        (a.get("author") or {}).get("display_name", "").split()[-1]
        for a in (authorships or [])
        if (a.get("author") or {}).get("display_name")
    ]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]} et al."


def _date_parts_to_iso(container: Dict[str, Any] | None) -> str | None:
    """Turns a Crossref `{"date-parts": [[YYYY, MM, DD]]}` object into 'YYYY-MM-DD'.

    Month and day are padded with '01' when Crossref only provides a coarser date.
    """
    if not container:
        return None
    parts = (container.get("date-parts") or [[]])[0]
    if not parts:
        return None
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except (TypeError, ValueError):
        return None


def _issue_label(volume: str | None, issue: str | None) -> str | None:
    """Builds a human-readable issue label, e.g. 'Vol. 12, Issue 3'."""
    parts = []
    if volume:
        parts.append(f"Vol. {volume}")
    if issue:
        parts.append(f"Issue {issue}")
    return ", ".join(parts) or None


def _clean_doi(value: str) -> str:
    """Normalises any DOI form (URL, `doi:` prefix, bare) to a lowercase bare DOI."""
    doi = (value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi


class SearchService:
    """Crossref finds journal-issue-dated papers; OpenAlex supplies the metadata."""

    def __init__(self):
        self.crossref_base = "https://api.crossref.org"
        self.openalex_base = "https://api.openalex.org"

        # Crossref's "polite pool" wants a contact address on every request.
        self.mailto = (
            os.environ.get("CROSSREF_MAILTO")
            or os.environ.get("SMTP_FROM")
            or ""
        )

        self.cache = LRUCache(max_size=100, ttl=3600)

    async def _fetch_crossref(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        headers = {"User-Agent": f"PaperScout/1.0 (mailto:{self.mailto})"}
        async with httpx.AsyncClient(
            base_url=self.crossref_base, timeout=15.0, headers=headers
        ) as client:
            try:
                if self.mailto:
                    params = {"mailto": self.mailto, **params}
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Error during Crossref request ({endpoint}): {e}")
                return {}

    async def _fetch_openalex(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.openalex_base, timeout=10.0
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
        data = await self._fetch_openalex("/sources", params)
        results = data.get("results", [])
        if not results:
            return None

        for result in results:
            if (result.get("display_name") or "").strip().lower() == name.strip().lower():
                return result
        return results[0]

    async def fetch_titles_by_ids(self, work_ids: List[str]) -> Dict[str, str]:
        """Looks up titles for a list of DOIs on OpenAlex. Keys are bare, lowercase DOIs."""
        if not work_ids:
            return {}

        dois = [d for d in (_clean_doi(w) for w in work_ids) if d]
        if not dois:
            return {}

        params = {
            "filter": f"doi:{'|'.join(dois)}",
            "per_page": len(dois),
            "select": "doi,title",
        }
        data = await self._fetch_openalex("/works", params)
        return {
            _clean_doi(work.get("doi") or ""): work.get("title")
            for work in data.get("results", [])
            if work.get("doi") and work.get("title")
        }

    async def search(
        self,
        issns: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
        limit: int,
        page: int,
    ) -> Dict[str, Any]:
        """Finds articles in the given journals (by ISSN) whose journal issue falls
        in the date range (Crossref), then enriches them with OpenAlex metadata."""
        key_parts = (
            tuple(sorted(issns)),
            keywords,
            from_date,
            to_date,
            limit,
            page,
        )
        cache_key = str(key_parts)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        # Repeated same-name filters are ORed by Crossref, so this matches any of
        # the given journals.
        issn_filters = [f"issn:{issn.strip()}" for issn in issns if issn and issn.strip()]
        if not issn_filters:
            # No journal filter would return the entire Crossref corpus.
            return {"meta": {"count": 0, "page": page, "per_page": limit}, "results": []}

        filter_str = ",".join(
            issn_filters
            + [
                f"{DATE_FILTER_FROM}:{from_date}",
                f"{DATE_FILTER_UNTIL}:{to_date}",
            ]
        )

        # Crossref paginates by offset, not page number.
        params: Dict[str, Any] = {
            "filter": filter_str,
            "rows": limit,
            "offset": max(page - 1, 0) * limit,
            "select": _CROSSREF_SELECT,
            "sort": "published-print",
            "order": "desc",
        }
        if keywords:
            params["query.bibliographic"] = keywords

        crossref_data = await self._fetch_crossref("/works", params)
        message = crossref_data.get("message") or {}
        items = message.get("items", [])

        # Base record per DOI from Crossref (issue date + issue label + fallbacks),
        # keeping Crossref's sort order.
        records: List[Dict[str, Any]] = []
        for work in items:
            doi = _clean_doi(work.get("DOI") or "")
            if not doi:
                continue
            records.append(self._base_record(doi, work))

        # Enrich with OpenAlex metadata, matched by DOI.
        oa_by_doi = await self._openalex_by_dois([r["id"] for r in records])
        for record in records:
            oa_work = oa_by_doi.get(record["id"])
            if oa_work:
                record.update(self._openalex_fields(oa_work))

        data = {
            "meta": {
                "count": message.get("total-results", 0),
                "page": page,
                "per_page": limit,
            },
            "results": records,
        }
        if records:
            self.cache.set(cache_key, data)
        return data

    async def _openalex_by_dois(self, dois: List[str]) -> Dict[str, Dict[str, Any]]:
        """Batch-looks up OpenAlex works for a list of bare DOIs, keyed by bare DOI."""
        dois = [d for d in dois if d]
        if not dois:
            return {}
        params = {
            "filter": f"doi:{'|'.join(dois)}",
            "per_page": len(dois),
            "select": _OPENALEX_SELECT,
        }
        data = await self._fetch_openalex("/works", params)
        return {
            _clean_doi(work.get("doi") or ""): work
            for work in data.get("results", [])
            if work.get("doi")
        }

    def _base_record(self, doi: str, cr_work: Dict[str, Any]) -> Dict[str, Any]:
        """The Crossref-derived part of a result: the journal issue date and issue
        label, plus a full fallback in case OpenAlex doesn't know the DOI."""
        journal_publication_date = _date_parts_to_iso(cr_work.get("published-print"))
        paper_date_fallback = (
            _date_parts_to_iso(cr_work.get("published"))
            or _date_parts_to_iso(cr_work.get("issued"))
            or journal_publication_date
        )
        return {
            "id": doi,
            "doi": f"https://doi.org/{doi}",
            "title": (cr_work.get("title") or [None])[0],
            "journal_name": (cr_work.get("container-title") or [None])[0],
            "publication_date": paper_date_fallback,
            "journal_publication_date": journal_publication_date,
            "issue": _issue_label(cr_work.get("volume"), cr_work.get("issue")),
            "pdf_url": None,
            "pdf_landing_page": f"https://doi.org/{doi}",
            "abstract": "No abstract available.",
            "topic": None,
            "author": "",
            "has_fulltext": False,
        }

    def _openalex_fields(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """The OpenAlex-derived part of a result: everything except the journal
        issue date and issue label."""
        primary_loc = work.get("primary_location") or {}
        source = primary_loc.get("source") or {}
        best_oa = work.get("best_oa_location") or {}
        primary_topic = work.get("primary_topic") or {}

        fields = {
            "title": work.get("title"),
            "publication_date": work.get("publication_date"),
            "pdf_url": best_oa.get("pdf_url"),
            "pdf_landing_page": best_oa.get("landing_page_url"),
            "abstract": self._extract_abstract(work.get("abstract_inverted_index")),
            "topic": primary_topic.get("display_name"),
            "author": format_authors_apa(work.get("authorships", [])),
            "has_fulltext": bool(work.get("has_fulltext")),
        }
        if source.get("display_name"):
            fields["journal_name"] = source.get("display_name")
        # Don't overwrite good fallbacks with None.
        return {k: v for k, v in fields.items() if v is not None or k == "pdf_url"}

    def _extract_abstract(self, inverted_index: Dict[str, List[int]] | None) -> str:
        """OpenAlex delivers abstracts 'inverted' for copyright reasons. This reconstructs them."""
        if not inverted_index:
            return "No abstract available."

        word_positions: Dict[int, str] = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions[pos] = word

        abstract = " ".join(word_positions[p] for p in sorted(word_positions))
        return re.sub(r"^(Abstract|ABSTRACT)\s*", "", abstract)
