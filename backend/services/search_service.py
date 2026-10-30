import asyncio
import html
import logging
import math
import os
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Tuple
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from sqlmodel import Session

from config import settings
from lib.cache import LRUCache
from services.external_api_service import apply_external_apis
from services.quota_alert_service import check_quota
from services.site_import_service import IMPORTERS, search_site_articles, sync_site_articles

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
    "volume,issue,abstract,author,issn-type,page,references-count"
)

# OpenAlex: only what Crossref doesn't have - topic, abstract and the free version.
_OPENALEX_SELECT = "doi,primary_topic,abstract_inverted_index,open_access,best_oa_location"

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
_SEARCH_WINDOW_YEARS = 2

# Semantic search: OpenAlex embeds title and abstract of every work and returns
# the works closest in meaning to the query. Of our filters it only takes the
# source id, type and publication year, and it returns at most 50 works (one
# page, no cursor) at one request per second. Unlike the other searches it
# doesn't ask Crossref: the date range only counts by its years, and the values
# come from OpenAlex. So there is no monthly email for it either. It replaces
# the keyword search; the two don't go together.
_SEMANTIC_MAX_RESULTS = 50
# What the results need from OpenAlex when Crossref isn't asked.
_SEMANTIC_SELECT = (
    f"{_OPENALEX_SELECT},title,publication_date,primary_location,authorships,biblio,"
    "referenced_works_count,relevance_score"
)
_SEMANTIC_INTERVAL_SECONDS = 1.0

# The order of searches without keywords: by the date the date range filters on.
_CROSSREF_NEWEST_FIRST = {"sort": "issued", "order": "desc"}

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


def _search_window(from_date: str, to_date: str) -> Tuple[str, str]:
    """The publication-date window of the keyword search: from the first day of
    the month `_SEARCH_WINDOW_YEARS` years before `from_date` up to `to_date`."""
    start = date.fromisoformat(from_date)  # "2026-10-01" -> date(2026, 10, 1)
    start = date(start.year - _SEARCH_WINDOW_YEARS, start.month, 1)
    return start.isoformat(), to_date


def _is_paper(oa_work: Dict[str, Any] | None) -> bool:
    """False for OpenAlex works that aren't papers (editorial, erratum, letter, ...).

    DOIs OpenAlex doesn't know are kept, since there's nothing to judge them by.
    """
    return oa_work is None or oa_work.get("type") in _PAPER_TYPES


# --- Commentaries, editorials etc. typed as papers ----------------------------
# OpenAlex types many commentaries, replies and editorials as "article" too. A
# score from title, page count, abstract and reference count flags them; flagged
# papers stay in the results (marked `low_value`) but the digest leaves them out.

# Strong: the title says what it is. Words that real papers use too only count
# where they start the title or a subtitle ("Reply to ...", "...: A commentary
# on ...", "Editorial: ..."), so that e.g. "Neural responses to threat" or
# "Editorial board diversity" isn't caught.
_LOW_VALUE_TITLE = re.compile(
    r"(?:^|[:.?!]\s*)(?:an?\s+)?"
    r"(?:(?:commentary|comment|response|reply|rejoinder)(?:\s+(?:on|to)\b|\s*:)"
    r"|(?:editorial|erratum|corrigendum|retraction)(?:\s*[:–-]|\s+(?:notice|to|for|on)\b|\s*$))"
    r"|\bcorrection\s+to\b|\bintroduction\s+to\s+the\s+special\s+(?:issue|section)\b"
    r"|\bfrom\s+the\s+editors?\b|\beditors?'?s?\s+(?:note|introduction)\b"
    r"|call\s+for\s+(?:papers|proposals|submissions)\b|\bpublication\s+notice\b"
    r"|\bin\s+memoriam\b|\bobituary\b|\bbook\s+review\b",
    re.IGNORECASE,
)
# Medium: the title quotes another paper and names its authors ('... "X" by Y et al.').
_QUOTED_TITLE = re.compile(r"[\"“„«‘'][^\"“”„«»‘’']{10,}[\"”“»’']")
_BY_AUTHORS = re.compile(r"\bby\s+\S+.*\bet\s+al\b|\bby\s+[A-Z]\w+\s+(?:and|&)\s+[A-Z]")
# Pages like "123-126" or "S12–S14"; article numbers ("e12345") don't count.
_PAGE_RANGE = re.compile(r"^([A-Za-z]*)(\d+)\s*[-–]\s*\1?(\d+)$")

_LOW_VALUE_MAX_PAGES = 4
_LOW_VALUE_MAX_REFERENCES = 15
_LOW_VALUE_THRESHOLD = 3


def _page_count(page: str | None) -> int | None:
    """The number of pages of a Crossref page range, None if it isn't one."""
    match = _PAGE_RANGE.match((page or "").strip())
    if not match:
        return None
    count = int(match.group(3)) - int(match.group(2)) + 1
    return count if count > 0 else None


def _low_value_score(
    title: str | None, page: str | None, has_abstract: bool, reference_count: int | None
) -> int:
    """How much a paper looks like a commentary, editorial, erratum etc.; from
    `_LOW_VALUE_THRESHOLD` on it counts as one."""
    title = title or ""
    score = 0
    if _LOW_VALUE_TITLE.search(title):
        score += 3
    pages = _page_count(page)
    if pages is not None and pages <= _LOW_VALUE_MAX_PAGES:
        score += 2
    if _QUOTED_TITLE.search(title) and _BY_AUTHORS.search(title):
        score += 2
    if not has_abstract:
        score += 1
    # Many publishers deposit no references at all, so 0 says nothing.
    if reference_count and reference_count < _LOW_VALUE_MAX_REFERENCES:
        score += 1
    return score


# --- Ranking website papers among the keyword hits ---------------------------
# Website papers (see site_import_service) aren't on OpenAlex, so OpenAlex can't
# rank them, and its relevance score can't be computed for them either (it rests
# on OpenAlex' own index and the citation counts). Instead, the OpenAlex hits and
# the website papers are scored with the same plain BM25 over title and
# abstract, and every website paper goes where the OpenAlex hits stop scoring
# higher than it does. OpenAlex' own order stays as it is.

_BM25_K1 = 1.2
_BM25_B = 0.75


def _tokens(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def _bm25_scorer(corpus: List[List[str]], query: str) -> Callable[[List[str]], float]:
    """A BM25 scoring function for the query, with term statistics from `corpus`."""
    terms = set(_tokens(query))
    avg_length = sum(map(len, corpus)) / len(corpus) if corpus else 0
    idf = {
        term: math.log(
            1 + (len(corpus) - (n := sum(term in set(doc) for doc in corpus)) + 0.5) / (n + 0.5)
        )
        for term in terms
    }

    def score(doc: List[str]) -> float:
        norm = _BM25_K1 * (1 - _BM25_B + _BM25_B * len(doc) / avg_length) if avg_length else 0
        total = 0.0
        for term in terms:
            frequency = doc.count(term)
            if frequency:
                total += idf[term] * frequency * (_BM25_K1 + 1) / (frequency + norm)
        return total

    return score


def _ranking_text(title: str | None, abstract: str | None) -> List[str]:
    """The tokens a paper is ranked by; the title counts twice."""
    return _tokens(f"{title or ''} {title or ''} {abstract or ''}")


def _insertion_points(api_scores: List[float], site_scores: List[float]) -> List[int]:
    """Where each website paper goes: in front of the first API hit (in OpenAlex
    order) after which no API hit scores higher than the paper. Hits that score
    the same stay in front."""
    points = []
    for site_score in site_scores:
        point = len(api_scores)
        while point > 0 and api_scores[point - 1] < site_score:
            point -= 1
        points.append(point)
    return points


def _open_access(oa_work: Dict[str, Any]) -> Dict[str, Any] | None:
    """Where the free version of an OpenAlex work is, or None if it has none.

    That needn't be the publisher's page the DOI leads to: for "green" papers it
    is a copy in a repository, while the publisher's version stays paywalled.
    """
    open_access = oa_work.get("open_access") or {}
    location = oa_work.get("best_oa_location") or {}
    url = open_access.get("oa_url") or location.get("landing_page_url")
    if not open_access.get("is_oa") or not url:
        return None
    return {
        "url": url,
        # gold, diamond, hybrid, bronze or green (see OpenAlex' oa_status).
        "status": open_access.get("oa_status"),
        "host": (location.get("source") or {}).get("display_name"),
    }


def _empty_record(record_id: str, doi: str | None) -> Dict[str, Any]:
    """A result with every field the frontend knows, before any API has filled it."""
    return {
        "id": record_id,
        "doi": f"https://doi.org/{doi}" if doi else None,
        # The paper's page at the publisher, for papers without a DOI.
        "url": None,
        "title": None,
        "journal_name": None,
        "publication_date": None,
        "journal_publication_date": None,
        "issue": None,
        "library_url": None,
        "abstract": None,
        "topic": None,
        "author": None,
        # The free version, if there is one (see _open_access).
        "open_access": None,
        # Likely a commentary, editorial etc. (see _low_value_score).
        "low_value": False,
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


def openurl_resolver_for(email: str) -> str:
    """The OpenURL resolver of the library the user with this email belongs to."""
    domain = email.rpartition("@")[2].lower()
    return settings.OPENURL_RESOLVERS_BY_DOMAIN.get(domain, settings.OPENURL_RESOLVER)


def _crossref_openurl_fields(cr_work: Dict[str, Any]) -> Dict[str, str]:
    """The OpenURL citation fields from a Crossref work. The resolver matches the
    article to the library's licences by ISSN, volume and issue."""
    issns = {entry.get("type"): entry.get("value") for entry in cr_work.get("issn-type") or []}
    fields = {
        "rft.atitle": _clean_title((cr_work.get("title") or [None])[0]),
        # Without the ISSN the resolver can't check the licences; untyped ones still do.
        "rft.issn": issns.get("print") or (cr_work.get("ISSN") or [None])[0],
        "rft.eissn": issns.get("electronic"),
        "rft.date": (_date_parts_to_iso(cr_work.get("issued")) or "")[:4],
        "rft.volume": cr_work.get("volume"),
        "rft.issue": cr_work.get("issue"),
        "rft.spage": (cr_work.get("page") or "").split("-")[0],
    }
    return {key: value for key, value in fields.items() if value}


def _openalex_base_fields(work: Dict[str, Any]) -> Dict[str, Any]:
    """The values Crossref would otherwise give, from an OpenAlex work. OpenAlex
    doesn't know the journal issue date, so there is none."""
    source = (work.get("primary_location") or {}).get("source") or {}
    biblio = work.get("biblio") or {}
    first, last = biblio.get("first_page"), biblio.get("last_page")
    page = f"{first}-{last}" if first and last else first
    title = _clean_title(work.get("title"))
    return {
        "title": title,
        "journal_name": source.get("display_name"),
        "publication_date": work.get("publication_date"),
        "issue": _issue_label(biblio.get("volume"), biblio.get("issue")),
        "author": format_authors_apa(work.get("authorships")) or None,
        "openurl": {
            key: value
            for key, value in {
                "rft.atitle": title,
                "rft.issn": source.get("issn_l"),
                "rft.date": (work.get("publication_date") or "")[:4],
                "rft.volume": biblio.get("volume"),
                "rft.issue": biblio.get("issue"),
                "rft.spage": first,
            }.items()
            if value
        },
        # Internal; scored once the abstract is final (see _search).
        "low_value_hints": {
            "page": page,
            "reference_count": work.get("referenced_works_count"),
        },
    }


def _openurl(record: Dict[str, Any], resolver: str) -> str | None:
    """Link to the library's OpenURL resolver for this article."""
    doi = _clean_doi(record.get("doi") or "")
    if not doi:
        return None
    # The DOI alone often finds nothing, so the citation (see _crossref_openurl_fields)
    # goes along. No journal title, though: the resolver fuzzy-matches it, and e.g.
    # "Science" made it suggest unrelated journals.
    params = {
        "ctx_ver": "Z39.88-2004",
        "rft_val_fmt": "info:ofi/fmt:kev:mtx:journal",
        "rft.genre": "article",
        "rft_id": f"info:doi/{doi}",
        **(record.get("openurl") or {}),
    }
    query = urlencode(params)
    # Some resolver URLs already carry their own query (institution, view).
    separator = "&" if "?" in resolver else "?"
    return f"{resolver}{separator}{query}"


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

        # OpenAlex takes one semantic search per second; they queue up here.
        self._semantic_lock = asyncio.Lock()
        self._semantic_last = 0.0

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
                await check_quota("openalex", response)
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
        resolver: str = settings.OPENURL_RESOLVER,
        session: Session | None = None,
        semantic_query: str = "",
        source_ids: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        """Finds papers in the given journals (by ISSN) whose journal issue falls in
        the date range (Crossref). Without keywords they are enriched with OpenAlex
        metadata; with keywords OpenAlex finds them first (see top of module).

        With a `semantic_query`, OpenAlex' semantic search finds them instead, in
        the journals whose OpenAlex source id `source_ids` maps their ISSN to, by
        the years of the date range only; the keywords are ignored then.

        `external_apis` maps an ISSN to an external API whose handler gets that
        journal's records for individual processing (see external_api_service).
        `resolver` is the OpenURL resolver of the user's library (see
        openurl_resolver_for).

        With a `session`, the papers of journals that are only on their own
        website (see site_import_service) are included: with keywords ranked
        among the OpenAlex hits, without by date among the Crossref results. The
        semantic search leaves them out, as OpenAlex has no embeddings for them.
        """
        semantic_query = semantic_query.strip()
        if semantic_query:
            keywords = ""
        site_records: List[Dict[str, Any]] = []
        site_issns = [issn for issn in issns if issn in IMPORTERS]
        if session is not None and site_issns and not semantic_query:
            await sync_site_articles(session, site_issns)
            site_records = search_site_articles(session, site_issns, keywords, from_date, to_date)
        api_issns = [issn for issn in issns if issn not in IMPORTERS]

        # Website paper j goes in front of API result points[j]; in the whole
        # list, that is position points[j] + j.
        points = [0] * len(site_records)
        if site_records and api_issns:
            if keywords:
                site_records, points = await self._rank_site_records(
                    site_records, api_issns, keywords, from_date, to_date
                )
            else:
                points = await self._date_insertion_points(
                    site_records, api_issns, from_date, to_date
                )
        site_at = {
            point + j: record
            for j, (point, record) in enumerate(zip(points, site_records, strict=True))
        }

        offset = max(page - 1, 0) * limit
        page_positions = range(offset, offset + limit)
        api_records: List[Dict[str, Any]] = []
        count = len(site_records)
        if api_issns:
            data = await self._search(
                api_issns,
                keywords,
                from_date,
                to_date,
                offset - sum(position < offset for position in site_at),
                sum(position not in site_at for position in page_positions),
                external_apis,
                semantic_query,
                [(source_ids or {})[issn] for issn in api_issns if issn in (source_ids or {})],
            )
            api_records = data["results"]
            count += data["meta"]["count"]

        # API pages can come back short (non-papers are dropped), so the website
        # papers are placed by position and the API results fill the rest.
        api_iter = iter(api_records)
        records = []
        for position in page_positions:
            record = site_at.get(position) or next(api_iter, None)
            if record:
                records.append(record)

        # The library link differs per user, so it is added to copies of the
        # (shared, cached) records. Its citation fields stay internal. Website
        # papers have no DOI and bring their own link.
        return {
            "meta": {"count": count, "page": page, "per_page": limit},
            "results": [
                {
                    **{key: value for key, value in record.items() if key != "openurl"},
                    "library_url": _openurl(record, resolver) or record.get("library_url"),
                }
                for record in records
            ],
        }

    async def _date_insertion_points(
        self,
        site_records: List[Dict[str, Any]],
        api_issns: List[str],
        from_date: str,
        to_date: str,
    ) -> List[int]:
        """Where each website paper (newest first) goes among the Crossref results,
        which are newest first too: behind every result issued after it. Crossref
        counts those, so no result has to be fetched."""
        issns = sorted({issn.strip() for issn in api_issns if issn and issn.strip()})

        async def newer_than(published: str) -> int:
            after = (date.fromisoformat(published) + timedelta(days=1)).isoformat()
            if after > to_date:
                return 0
            cache_key = str(("crossref_count", tuple(issns), after, to_date))
            count = self.cache.get(cache_key)
            if count is None:
                params = {"filter": self._crossref_filter(issns, after, to_date), "rows": 0}
                message = (await self._fetch_crossref("/works", params)).get("message")
                if message is None:
                    return 0  # request failed; the paper goes first
                count = message.get("total-results", 0)
                self.cache.set(cache_key, count)
            return count

        dates = [record["publication_date"] for record in site_records]
        unique_dates = list(dict.fromkeys(dates))
        counts = await asyncio.gather(*(newer_than(d) for d in unique_dates))
        by_date = dict(zip(unique_dates, counts, strict=True))
        return [by_date[d] for d in dates]

    async def _rank_site_records(
        self,
        site_records: List[Dict[str, Any]],
        api_issns: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
    ) -> Tuple[List[Dict[str, Any]], List[int]]:
        """The website papers, best first, and where each goes among the keyword
        hits of the API journals (see _insertion_points)."""
        issns = sorted({issn.strip() for issn in api_issns if issn and issn.strip()})
        hits, oa_by_doi = await self._cached_keyword_hits(issns, keywords, from_date, to_date)

        # Scoring every hit takes a while, so the scores are kept with the hits.
        cache_key = str(("keyword_scores", tuple(issns), keywords, from_date, to_date))
        cached = self.keyword_cache.get(cache_key)
        if cached is None or len(cached[0]) != len(hits):
            corpus = []
            for work in hits:
                oa_work = oa_by_doi.get(_clean_doi(work.get("DOI") or "")) or {}
                corpus.append(
                    _ranking_text(
                        _clean_title((work.get("title") or [None])[0]),
                        self._extract_abstract(oa_work.get("abstract_inverted_index"))
                        or _strip_jats(work.get("abstract")),
                    )
                )
            score = _bm25_scorer(corpus, keywords)
            cached = ([score(doc) for doc in corpus], score)
            self.keyword_cache.set(cache_key, cached)
        api_scores, score = cached

        site_scores = [
            score(_ranking_text(record.get("title"), record.get("abstract")))
            for record in site_records
        ]
        ranked = sorted(zip(site_scores, site_records, strict=True), key=lambda pair: -pair[0])
        site_records = [record for _, record in ranked]
        return site_records, _insertion_points(api_scores, [s for s, _ in ranked])

    async def _search(
        self,
        issns: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
        offset: int,
        rows: int,
        external_apis: Dict[str, str] | None,
        semantic_query: str = "",
        source_ids: List[str] | None = None,
    ) -> Dict[str, Any]:
        """`rows` results from position `offset` on, and the total count."""
        external_apis = external_apis or {}
        source_ids = sorted(set(source_ids or []))
        key_parts = (
            tuple(sorted(issns)),
            tuple(sorted(external_apis.items())),
            keywords,
            semantic_query,
            from_date,
            to_date,
            offset,
            rows,
        )
        cache_key = str(key_parts)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        issns = sorted({issn.strip() for issn in issns if issn and issn.strip()})
        if not issns:
            # No journal filter would return the entire Crossref corpus.
            return {"meta": {"count": 0}, "results": []}

        label = f"search in {len(issns)} journal(s), from result {offset + 1}"
        if keywords:
            label += f", keywords {keywords!r}"
        elif semantic_query:
            label += f", semantic query {semantic_query[:60]!r}"
        with _track_openalex_cost(label):
            if semantic_query:
                hits, oa_by_doi = await self._cached_semantic_hits(
                    source_ids, semantic_query, from_date, to_date
                )
                records, api_by_doi = self._openalex_records(
                    hits[offset : offset + rows], external_apis
                )
                count = len(hits)
                self._fill_openalex(records, oa_by_doi)
            elif keywords:
                items, count, oa_by_doi = await self._search_keywords(
                    issns, keywords, from_date, to_date, offset, rows
                )
                records, api_by_doi = self._crossref_records(items, external_apis)
                # The keyword search already returned the OpenAlex values.
                self._fill_openalex(records, oa_by_doi)
            else:
                items, count = await self._search_crossref(issns, from_date, to_date, offset, rows)
                records, api_by_doi = self._crossref_records(items, external_apis)
                records = await self._add_openalex(records)

            await apply_external_apis(records, api_by_doi)

            # Guarantee the shapes the frontend expects.
            for record in records:
                hints = record.pop("low_value_hints", None) or {}
                record["low_value"] = (
                    _low_value_score(
                        record.get("title"),
                        hints.get("page"),
                        bool(record.get("abstract")),
                        hints.get("reference_count"),
                    )
                    >= _LOW_VALUE_THRESHOLD
                )
                record["abstract"] = record.get("abstract") or "No abstract available."
                record["author"] = record.get("author") or ""

            data = {"meta": {"count": count}, "results": records}
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
        self, issns: List[str], from_date: str, to_date: str, offset: int, rows: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """`rows` Crossref works from position `offset` on, newest journal issue
        first, and the total count."""
        params: Dict[str, Any] = {
            "filter": self._crossref_filter(issns, from_date, to_date),
            "rows": rows,
            "offset": offset,
            "select": _CROSSREF_SELECT,
            **_CROSSREF_NEWEST_FIRST,
        }
        message = (await self._fetch_crossref("/works", params)).get("message") or {}
        return message.get("items", []), message.get("total-results", 0)

    async def _search_keywords(
        self,
        issns: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
        offset: int,
        rows: int,
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Dict[str, Any]]]:
        """`rows` of the papers OpenAlex finds for the keywords whose journal issue
        (Crossref) falls in the date range, from position `offset` on, in OpenAlex's
        relevance order, the total count, and the OpenAlex works keyed by bare DOI."""
        hits, oa_by_doi = await self._cached_keyword_hits(issns, keywords, from_date, to_date)
        return hits[offset : offset + rows], len(hits), oa_by_doi

    async def _cached_keyword_hits(
        self, issns: List[str], keywords: str, from_date: str, to_date: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """The keyword hits of _keyword_hits, from the cache if they're in it."""
        cache_key = str(("keyword_hits", tuple(issns), keywords, from_date, to_date))
        cached = self.keyword_cache.get(cache_key)
        if cached is None:
            hits, oa_by_doi, complete = await self._keyword_hits(
                issns, keywords, from_date, to_date
            )
            cached = (hits, oa_by_doi)
            if complete:
                self.keyword_cache.set(cache_key, cached)
        return cached

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
        from_pub, to_pub = _search_window(from_date, to_date)
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

    async def _cached_semantic_hits(
        self,
        source_ids: List[str],
        query: str,
        from_date: str,
        to_date: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """The hits of _semantic_hits, from the cache if they're in it."""
        cache_key = str(("semantic_hits", tuple(source_ids), query, from_date, to_date))
        cached = self.keyword_cache.get(cache_key)
        if cached is None:
            hits, oa_by_doi, complete = await self._semantic_hits(
                source_ids, query, from_date, to_date
            )
            cached = (hits, oa_by_doi)
            if complete:
                self.keyword_cache.set(cache_key, cached)
        return cached

    async def _semantic_hits(
        self,
        source_ids: List[str],
        query: str,
        from_date: str,
        to_date: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], bool]:
        """The OpenAlex works in the journals (OpenAlex source ids) closest in
        meaning to the query published in the years of the date range, most
        similar first; the same works keyed by bare DOI; and whether the request
        succeeded."""
        if not source_ids:
            return [], {}, True
        params = {
            "filter": ",".join(
                [
                    f"primary_location.source.id:{'|'.join(source_ids)}",
                    f"type:{'|'.join(_PAPER_TYPES)}",
                    # Publication dates aren't supported, only years, so the
                    # date range only counts by its years.
                    f"publication_year:{from_date[:4]}-{to_date[:4]}",
                ]
            ),
            "search.semantic": query,
            "sort": "relevance_score:desc",
            "per_page": _SEMANTIC_MAX_RESULTS,
            "select": _SEMANTIC_SELECT,
            **_OPENALEX_INCLUDE_XPAC,
        }
        data = await self._fetch_openalex_semantic(params)
        if "results" not in data:
            return [], {}, False

        oa_by_doi: Dict[str, Dict[str, Any]] = {}
        for work in data["results"]:
            doi = _clean_doi(work.get("doi") or "")
            if doi:
                oa_by_doi.setdefault(doi, work)
        hits = sorted(
            oa_by_doi.values(), key=lambda work: work.get("relevance_score") or 0, reverse=True
        )
        return hits, oa_by_doi, True

    async def _fetch_openalex_semantic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """A semantic search on OpenAlex, at most one per second (its rate limit)."""
        async with self._semantic_lock:
            wait = self._semantic_last + _SEMANTIC_INTERVAL_SECONDS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await self._fetch_openalex("/works", params)
            finally:
                self._semantic_last = time.monotonic()

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

    def _openalex_records(
        self, works: List[Dict[str, Any]], external_apis: Dict[str, str]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """A base record per OpenAlex work, in the given order, and the external
        API per DOI; for the semantic search, which doesn't ask Crossref."""
        records: List[Dict[str, Any]] = []
        api_by_doi: Dict[str, str] = {}
        for work in works:
            doi = _clean_doi(work.get("doi") or "")
            if not doi:
                continue
            record = _empty_record(doi, doi)
            _merge(record, _openalex_base_fields(work))
            records.append(record)
            source = (work.get("primary_location") or {}).get("source") or {}
            for issn in source.get("issn") or []:
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
                record["open_access"] = _open_access(oa_work)

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
            "openurl": _crossref_openurl_fields(cr_work),
            # Internal; scored once the abstract is final (see _search).
            "low_value_hints": {
                "page": cr_work.get("page"),
                "reference_count": cr_work.get("references-count"),
            },
        }

    def _openalex_fields(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """The values only OpenAlex has: topic and abstract."""
        primary_topic = work.get("primary_topic") or {}

        return {
            "topic": primary_topic.get("display_name"),
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
