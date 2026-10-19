import asyncio
import html
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Tuple

import httpx
from dotenv import load_dotenv

from lib.cache import LRUCache
from services.external_api_service import apply_external_apis

load_dotenv()

logger = logging.getLogger(__name__)

# --- Best of both worlds -----------------------------------------------------
# Crossref always finds the papers that appeared in a set of journals within a
# date range, filtered by the *journal issue* date. OpenAlex, looked up by DOI,
# fills the fields Crossref left empty and tells papers apart from editorials,
# errata etc.
#
# With keywords, OpenAlex searches the journals for papers published from the
# selected from_month two years ago (there can be a large gap between online and
# print publication) to the end of the to_month (its keyword search
# is far better than Crossref's). Crossref then looks those DOIs up and keeps only
# the ones whose journal issue (`issued`) falls in the selected date range. The
# values come from Crossref and the external APIs. Pagination happens locally on
# that list, so it is cached.
#
# Crossref date filters:
#   - "from-pub-date"       -> `published`       (in this journal, print OR online)
#   - "from-print-pub-date" -> `published-print` (the printed issue date only)
#   - "from-online-pub-date"-> `published-online`
#   - "from-issued-date"    -> `issued`          (earliest of print and online)
DATE_FILTER_FROM = "from-issued-date"
DATE_FILTER_UNTIL = "until-issued-date"

# Crossref: the issue date and label, plus the other metadata it has.
# ISSN tells which journal a work belongs to, for the journal-specific external APIs.
_CROSSREF_SELECT = (
    "DOI,ISSN,title,container-title,published-print,published-online,published,issued,"
    "volume,issue,abstract,author"
)

# OpenAlex: only what Crossref doesn't have - topic, full-text flag and PDF link.
_OPENALEX_SELECT = "doi,primary_topic,best_oa_location,has_fulltext,abstract_inverted_index"

# OpenAlex leaves its "xpac" works (an expansion of its index, recent journal
# papers among them) out of list queries unless asked; single lookups return them.
_OPENALEX_INCLUDE_XPAC = {"include_xpac": "true"}

# Crossref files editorials, errata, book reviews etc. as plain "journal-article",
# so only OpenAlex's own `type` can tell them apart from actual papers.
_PAPER_TYPES = ("article", "review")

# OpenAlex pages are at most 200 works. Crossref gets the DOIs in batches, three
# requests at a time, as its polite pool asks (x-concurrency-limit).
_OPENALEX_PAGE_SIZE = 200
_OPENALEX_CONCURRENCY = 6
_CROSSREF_DOI_BATCH = 100  # keeps the URL well below Crossref's length limit
_CROSSREF_CONCURRENCY = 3
# OpenAlex's page numbers reach only this many results; past that only its cursor does.
_OPENALEX_PAGED_MAX = 10_000

# One OpenAlex page checked on Crossref: the Crossref works in the date range and
# the page's OpenAlex works by DOI, or None if a request failed.
_PageHits = Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]] | None

# How far back the keyword search on OpenAlex reaches, counted from the current month.
_KEYWORD_WINDOW_YEARS = 2

# Retries on Crossref rate limits (429) and server errors.
_CROSSREF_RETRIES = 4


@dataclass
class _OpenAlexCost:
    """OpenAlex cost summed up over the requests of one search."""

    requests: int = 0
    usd: float = 0.0
    remaining_usd: str | None = None


# The cost tracker of the running search; tasks started by asyncio.gather copy the
# context, so they all add to the same object.
_openalex_cost: ContextVar[_OpenAlexCost | None] = ContextVar("openalex_cost", default=None)


@contextmanager
def _track_openalex_cost(label: str):
    """Sums up the OpenAlex cost of every request made inside and logs the total."""
    cost = _OpenAlexCost()
    token = _openalex_cost.set(cost)
    try:
        yield cost
    finally:
        _openalex_cost.reset(token)
        if cost.requests:
            logger.info(
                "OpenAlex cost for %s: $%.4f in %d request(s), $%s left today",
                label,
                cost.usd,
                cost.requests,
                cost.remaining_usd or "?",
            )


def _add_openalex_cost(headers: httpx.Headers) -> None:
    """Adds what an OpenAlex request cost, as reported in its response headers, to
    the running search's total."""
    cost = _openalex_cost.get()
    if cost is None:
        return
    try:
        usd = float(headers.get("x-ratelimit-cost-usd") or 0)
    except ValueError:
        usd = 0.0
    cost.requests += 1
    cost.usd += usd
    cost.remaining_usd = headers.get("x-ratelimit-remaining-usd") or cost.remaining_usd


def _keyword_window(from_date: str, to_date: str) -> Tuple[str, str]:
    """The publication-date window of the keyword search: from the first day of
    the month `_KEYWORD_WINDOW_YEARS` years before `from_date` up to `to_date`."""
    start = date.fromisoformat(from_date)  # "2026-10-01" -> date(2026, 10, 1)
    start = date(start.year - _KEYWORD_WINDOW_YEARS, start.month, 1)
    return start.isoformat(), to_date


def _is_paper(oa_work: Dict[str, Any] | None) -> bool:
    """False for OpenAlex works that aren't papers (editorial, erratum, letter, ...).

    DOIs OpenAlex doesn't know are kept, since there's nothing to judge them by.
    """
    return oa_work is None or oa_work.get("type") in _PAPER_TYPES


def _empty_record(record_id: str, doi: str | None) -> Dict[str, Any]:
    """A result with every field the frontend knows, before any API has filled it."""
    return {
        "id": record_id,
        "doi": f"https://doi.org/{doi}" if doi else None,
        "title": None,
        "journal_name": None,
        "publication_date": None,
        "journal_publication_date": None,
        "issue": None,
        "pdf_url": None,
        "pdf_landing_page": None,
        "abstract": None,
        "topic": None,
        "author": None,
        "has_fulltext": False,
    }


def _merge(record: Dict[str, Any], fields: Dict[str, Any]) -> None:
    """Fills the record's empty fields from `fields`. Empty values are skipped."""
    for key, value in fields.items():
        if value in (None, "", []):
            continue
        if not record.get(key):
            record[key] = value


def _apa_from_last_names(names: List[str]) -> str:
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]} et al."


def format_authors_apa(authorships: list) -> str:
    """Short APA-style author string from an OpenAlex `authorships` list."""
    return _apa_from_last_names(
        [
            (a.get("author") or {}).get("display_name", "").split()[-1]
            for a in (authorships or [])
            if (a.get("author") or {}).get("display_name")
        ]
    )


def format_authors_apa_crossref(authors: list) -> str:
    """Short APA-style author string from a Crossref `author` list."""
    return _apa_from_last_names(
        [(a.get("family") or a.get("name") or "").strip() for a in (authors or [])]
    )


def _strip_jats(abstract: str | None) -> str | None:
    """Crossref abstracts are JATS-XML snippets; strip the tags to plain text."""
    if not abstract:
        return None
    text = re.sub(r"<[^>]+>", " ", abstract)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(Abstract|ABSTRACT)\s*", "", text)
    return text or None


def _clean_title(title: str | None) -> str | None:
    """Titles may contain inline markup (<scp>, <i>, <sub>, ...) and HTML entities;
    reduce them to plain text. Tags are removed without a space so 'CO<sub>2</sub>'
    stays 'CO2'."""
    if not title:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", "", title))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


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
            doi = doi[len(prefix) :]
            break
    return doi


class SearchService:
    """Crossref finds journal-issue-dated papers, OpenAlex adds its metadata. With
    keywords, OpenAlex finds the papers and Crossref narrows them to the issue dates."""

    def __init__(self):
        self.crossref_base = "https://api.crossref.org"
        self.openalex_base = "https://api.openalex.org"

        # Crossref's "polite pool" wants a contact address on every request.
        self.mailto = os.environ.get("CROSSREF_MAILTO") or os.environ.get("SMTP_FROM") or ""

        # Finished result pages.
        self.cache = LRUCache(max_size=100, ttl=3600)
        # The full hit lists of keyword searches, which every page is cut from. Kept
        # apart so the many small pages can't push them out, and for a day, since
        # rebuilding one costs OpenAlex requests.
        self.keyword_cache = LRUCache(max_size=20, ttl=86400)

    async def _fetch_crossref(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"User-Agent": f"PaperScout/1.0 (mailto:{self.mailto})"}
        if self.mailto:
            params = {"mailto": self.mailto, **params}
        async with httpx.AsyncClient(
            base_url=self.crossref_base, timeout=30.0, headers=headers
        ) as client:
            for attempt in range(_CROSSREF_RETRIES):
                try:
                    response = await client.get(endpoint, params=params)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < _CROSSREF_RETRIES - 1:
                            wait = float(response.headers.get("Retry-After") or 2**attempt)
                            await asyncio.sleep(wait)
                            continue
                    response.raise_for_status()
                    return response.json()
                except Exception as e:
                    print(f"Error during Crossref request ({endpoint}): {e}")
                    return {}
        return {}

    async def _fetch_openalex(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.openalex_base, timeout=10.0) as client:
            try:
                api_key = os.environ.get("API_KEY")
                params = {"api_key": api_key, **params}
                response = await client.get(endpoint, params=params)
                _add_openalex_cost(response.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Its message would contain the request URL, API key included.
                print(f"Error during OpenAlex request ({endpoint}): HTTP {e.response.status_code}")
                return {}
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

    async def search(
        self,
        issns: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
        limit: int,
        page: int,
        external_apis: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        """Finds papers in the given journals (by ISSN) whose journal issue falls in
        the date range (Crossref). Without keywords they are enriched with OpenAlex
        metadata; with keywords OpenAlex finds them first (see top of module).

        `external_apis` maps an ISSN to an external API whose handler gets that
        journal's records for individual processing (see external_api_service).
        """
        external_apis = external_apis or {}
        key_parts = (
            tuple(sorted(issns)),
            tuple(sorted(external_apis.items())),
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

        issns = sorted({issn.strip() for issn in issns if issn and issn.strip()})
        if not issns:
            # No journal filter would return the entire Crossref corpus.
            return {
                "meta": {"count": 0, "page": page, "per_page": limit},
                "results": [],
            }

        label = f"search in {len(issns)} journal(s), page {page}"
        if keywords:
            label += f", keywords {keywords!r}"
        with _track_openalex_cost(label):
            if keywords:
                items, count, oa_by_doi = await self._search_keywords(
                    issns, keywords, from_date, to_date, limit, page
                )
                records, api_by_doi = self._crossref_records(items, external_apis)
                # The keyword search already returned the OpenAlex values.
                self._fill_openalex(records, oa_by_doi)
            else:
                items, count = await self._search_crossref(issns, from_date, to_date, limit, page)
                records, api_by_doi = self._crossref_records(items, external_apis)
                records = await self._add_openalex(records)

            await apply_external_apis(records, api_by_doi)

            # Guarantee the shapes the frontend expects.
            for record in records:
                record["abstract"] = record.get("abstract") or "No abstract available."
                record["author"] = record.get("author") or ""
                record["pdf_landing_page"] = record.get("pdf_landing_page") or record["doi"]

            data = {
                "meta": {"count": count, "page": page, "per_page": limit},
                "results": records,
            }
            if records:
                self.cache.set(cache_key, data)
            return data

    def _crossref_filter(self, issns: List[str], from_date: str, to_date: str) -> str:
        # Repeated same-name filters are ORed by Crossref, so this matches any of
        # the given journals.
        return ",".join(
            [f"issn:{issn}" for issn in issns]
            + [
                "type:journal-article",
                f"{DATE_FILTER_FROM}:{from_date}",
                f"{DATE_FILTER_UNTIL}:{to_date}",
            ]
        )

    async def _search_crossref(
        self, issns: List[str], from_date: str, to_date: str, limit: int, page: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """One page of Crossref works, newest journal issue first, and the total count."""
        # Crossref paginates by offset, not page number.
        params: Dict[str, Any] = {
            "filter": self._crossref_filter(issns, from_date, to_date),
            "rows": limit,
            "offset": max(page - 1, 0) * limit,
            "select": _CROSSREF_SELECT,
        }
        message = (await self._fetch_crossref("/works", params)).get("message") or {}
        return message.get("items", []), message.get("total-results", 0)

    async def _search_keywords(
        self,
        issns: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
        limit: int,
        page: int,
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Dict[str, Any]]]:
        """One page of the papers OpenAlex finds for the keywords whose journal
        issue (Crossref) falls in the date range, in OpenAlex's relevance order, the
        total count, and the OpenAlex works keyed by bare DOI."""
        cache_key = str(("keyword_hits", tuple(issns), keywords, from_date, to_date))
        cached = self.keyword_cache.get(cache_key)
        if cached is None:
            hits, oa_by_doi, complete = await self._keyword_hits(
                issns, keywords, from_date, to_date
            )
            cached = (hits, oa_by_doi)
            if complete:
                self.keyword_cache.set(cache_key, cached)
        hits, oa_by_doi = cached

        offset = max(page - 1, 0) * limit
        return hits[offset : offset + limit], len(hits), oa_by_doi

    async def _keyword_hits(
        self, issns: List[str], keywords: str, from_date: str, to_date: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], bool]:
        """Every paper in the journals that OpenAlex matches with the keywords
        (published from two years before `from_date` up to `to_date`) and whose
        journal issue (Crossref) falls in the date range, in relevance order; the
        OpenAlex works of those papers, keyed by bare DOI; and whether every request
        succeeded.

        The OpenAlex pages are fetched in parallel, and each is checked on Crossref
        as soon as it arrives, so both APIs work at the same time.
        """
        from_pub, to_pub = _keyword_window(from_date, to_date)
        params = {
            "filter": ",".join(
                [
                    f"primary_location.source.issn:{'|'.join(issns)}",
                    f"type:{'|'.join(_PAPER_TYPES)}",
                    f"from_publication_date:{from_pub}",
                    f"to_publication_date:{to_pub}",
                    "has_doi:true",
                ]
            ),
            "search": keywords,
            # The order of the results; Crossref only filters this list.
            "sort": "relevance_score:desc",
            "per_page": _OPENALEX_PAGE_SIZE,
            "select": _OPENALEX_SELECT,
            **_OPENALEX_INCLUDE_XPAC,
        }
        openalex_slots = asyncio.Semaphore(_OPENALEX_CONCURRENCY)
        crossref_slots = asyncio.Semaphore(_CROSSREF_CONCURRENCY)

        async def fetch_page(page_params: Dict[str, Any]) -> Dict[str, Any] | None:
            async with openalex_slots:
                data = await self._fetch_openalex("/works", {**params, **page_params})
            return data if "results" in data else None

        async def check(data: Dict[str, Any]) -> _PageHits:
            """The Crossref works of one OpenAlex page that are in the date range,
            and that page's OpenAlex works."""
            oa_by_doi: Dict[str, Dict[str, Any]] = {}
            for work in data["results"]:
                doi = _clean_doi(work.get("doi") or "")
                if doi:
                    oa_by_doi.setdefault(doi, work)
            cr_works = await self._crossref_issued_in_range(
                list(oa_by_doi), from_date, to_date, crossref_slots
            )
            return None if cr_works is None else (cr_works, oa_by_doi)

        async def fetch_and_check(page: int) -> _PageHits:
            data = await fetch_page({"page": page})
            return None if data is None else await check(data)

        first = await fetch_page({"page": 1})
        if first is None:
            return [], {}, False
        count = (first.get("meta") or {}).get("count") or 0

        tasks: List[asyncio.Task] = []
        complete = True
        if count <= _OPENALEX_PAGED_MAX:
            tasks.append(asyncio.create_task(check(first)))
            pages = -(-count // _OPENALEX_PAGE_SIZE)
            tasks += [asyncio.create_task(fetch_and_check(n)) for n in range(2, pages + 1)]
        else:
            # Page numbers only reach the first 10,000 results; beyond that only the
            # cursor does, one page after the other.
            cursor = "*"
            while cursor:
                data = await fetch_page({"cursor": cursor})
                if data is None:
                    complete = False  # request failed; keep what we have
                    break
                tasks.append(asyncio.create_task(check(data)))
                results = data["results"]
                cursor = (data.get("meta") or {}).get("next_cursor") if results else None

        hits: List[Dict[str, Any]] = []
        oa_by_doi: Dict[str, Dict[str, Any]] = {}
        # Pages come back in order, so the relevance ranking is kept.
        for page_hits in await asyncio.gather(*tasks):
            if page_hits is None:
                complete = False
                continue
            cr_works, page_oa = page_hits
            for work in cr_works:
                doi = _clean_doi(work.get("DOI") or "")
                # Only the OpenAlex works Crossref kept are ever shown.
                if doi in page_oa and doi not in oa_by_doi:
                    hits.append(work)
                    oa_by_doi[doi] = page_oa[doi]
        return hits, oa_by_doi, complete

    async def _crossref_issued_in_range(
        self,
        dois: List[str],
        from_date: str,
        to_date: str,
        slots: asyncio.Semaphore,
    ) -> List[Dict[str, Any]] | None:
        """The Crossref works among `dois` whose journal issue falls in the date
        range, with all their data, in the order of `dois`. None if a request failed.

        No ISSN filter: OpenAlex already picked the journals, and the ISSNs would
        make the URL too long."""

        async def lookup(batch: List[str]) -> List[Dict[str, Any]] | None:
            # Repeated same-name filters are ORed by Crossref, different ones ANDed.
            params = {
                "filter": ",".join(
                    [f"doi:{doi}" for doi in batch]
                    + [self._crossref_filter([], from_date, to_date)]
                ),
                "rows": len(batch),
                "select": _CROSSREF_SELECT,
            }
            async with slots:
                message = (await self._fetch_crossref("/works", params)).get("message")
            return None if message is None else message.get("items", [])

        batches = [
            dois[i : i + _CROSSREF_DOI_BATCH] for i in range(0, len(dois), _CROSSREF_DOI_BATCH)
        ]
        results = await asyncio.gather(*(lookup(b) for b in batches))
        if any(r is None for r in results):
            return None
        by_doi: Dict[str, Dict[str, Any]] = {}
        for work in (w for batch in results for w in batch):
            doi = _clean_doi(work.get("DOI") or "")
            if doi:
                by_doi.setdefault(doi, work)
        # Keep the order of `dois`, i.e. OpenAlex's relevance ranking.
        return [by_doi[doi] for doi in dois if doi in by_doi]

    def _crossref_records(
        self, items: List[Dict[str, Any]], external_apis: Dict[str, str]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """A base record per Crossref work, in the given order, and the external
        API per DOI."""
        records: List[Dict[str, Any]] = []
        api_by_doi: Dict[str, str] = {}
        for work in items:
            doi = _clean_doi(work.get("DOI") or "")
            if not doi:
                continue
            record = _empty_record(doi, doi)
            _merge(record, self._crossref_fields(work))
            records.append(record)
            # Crossref lists print and electronic ISSN; ours is the ISSN-L, one of them.
            for issn in work.get("ISSN") or []:
                if issn in external_apis:
                    api_by_doi[doi] = external_apis[issn]
                    break
        return records, api_by_doi

    async def _add_openalex(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drops non-papers and fills gaps with OpenAlex metadata, matched by DOI."""
        oa_by_doi = await self._openalex_by_dois([r["id"] for r in records])
        # Dropping non-papers means a page can come back with fewer than `limit` results.
        records = [r for r in records if _is_paper(oa_by_doi.get(r["id"]))]
        self._fill_openalex(records, oa_by_doi)
        return records

    def _fill_openalex(
        self, records: List[Dict[str, Any]], oa_by_doi: Dict[str, Dict[str, Any]]
    ) -> None:
        """Fills the records' gaps with the OpenAlex values, matched by DOI. Only the
        abstract replaces Crossref's, since OpenAlex' is usually the better one."""
        for record in records:
            oa_work = oa_by_doi.get(record["id"])
            if oa_work:
                fields = self._openalex_fields(oa_work)
                abstract = fields.pop("abstract")
                _merge(record, fields)
                record["abstract"] = abstract or record.get("abstract")

    async def fetch_openalex_works(self, dois: List[str]) -> Dict[str, Dict[str, Any]]:
        """OpenAlex ID and title per bare DOI. The PDF download needs the OpenAlex ID,
        while the results only carry the DOI."""
        works: Dict[str, Dict[str, Any]] = {}
        # OpenAlex takes at most 100 values in one OR filter.
        for i in range(0, len(dois), 100):
            works.update(await self._openalex_by_dois(dois[i : i + 100], select="id,doi,title"))
        return works

    async def _openalex_by_dois(
        self,
        dois: List[str],
        # `type` only tells papers from editorials, errata etc.
        select: str = f"{_OPENALEX_SELECT},type",
    ) -> Dict[str, Dict[str, Any]]:
        """Batch-looks up OpenAlex works for a list of bare DOIs, keyed by bare DOI."""
        dois = [d for d in dois if d]
        if not dois:
            return {}
        params = {
            "filter": f"doi:{'|'.join(dois)}",
            "per_page": len(dois),
            "select": select,
            **_OPENALEX_INCLUDE_XPAC,
        }
        data = await self._fetch_openalex("/works", params)
        return {
            _clean_doi(work.get("doi") or ""): work
            for work in data.get("results", [])
            if work.get("doi")
        }

    def _crossref_fields(self, cr_work: Dict[str, Any]) -> Dict[str, Any]:
        """Values from Crossref, including the journal issue date and issue label,
        which only Crossref knows."""
        # Online-only journals have no printed issue; their online date stands in.
        journal_publication_date = _date_parts_to_iso(
            cr_work.get("published-print")
        ) or _date_parts_to_iso(cr_work.get("published-online"))
        return {
            "title": _clean_title((cr_work.get("title") or [None])[0]),
            "journal_name": (cr_work.get("container-title") or [None])[0],
            "publication_date": (
                _date_parts_to_iso(cr_work.get("published"))
                or _date_parts_to_iso(cr_work.get("issued"))
                or journal_publication_date
            ),
            "journal_publication_date": journal_publication_date,
            "issue": _issue_label(cr_work.get("volume"), cr_work.get("issue")),
            "abstract": _strip_jats(cr_work.get("abstract")),
            "author": format_authors_apa_crossref(cr_work.get("author")) or None,
        }

    def _openalex_fields(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """The values only OpenAlex has: topic, full-text flag and PDF link."""
        best_oa = work.get("best_oa_location") or {}
        primary_topic = work.get("primary_topic") or {}

        return {
            "pdf_url": best_oa.get("pdf_url"),
            "topic": primary_topic.get("display_name"),
            "has_fulltext": bool(work.get("has_fulltext")),
            "abstract": self._extract_abstract(work.get("abstract_inverted_index")),
        }

    def _extract_abstract(self, inverted_index: Dict[str, List[int]] | None) -> str | None:
        """OpenAlex delivers abstracts 'inverted' for copyright reasons. This reconstructs them."""
        if not inverted_index:
            return None

        word_positions: Dict[int, str] = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions[pos] = word

        abstract = " ".join(word_positions[p] for p in sorted(word_positions))
        return re.sub(r"^(Abstract|ABSTRACT)\s*", "", abstract) or None
