import os
import re
from typing import Any, Awaitable, Callable, Dict, List

import httpx

from services.quota_alert_service import check_quota

# --- Journal-specific external APIs ------------------------------------------
# `Journals.external_api` flags a journal whose papers need individual handling
# on top of Crossref/OpenAlex. After the regular search has built its records,
# each flagged journal's records are passed to the handler registered here
# under that name. A handler may change the records in place however that API
# requires (fill missing fields, correct values, ...).
#
# A new API is added by writing a handler with the same signature and
# registering it in `HANDLERS`.

Record = Dict[str, Any]
Handler = Callable[[List[Record]], Awaitable[None]]


# --- Springer Nature ---------------------------------------------------------
# Springer deposits abstracts with Crossref/OpenAlex only unreliably, so they
# are looked up on the Springer Nature Meta API, which takes precedence.

_SPRINGER_BASE = "https://api.springernature.com/meta/v2/json"
# The Meta API returns at most 25 records per request on the basic plan.
_SPRINGER_PAGE_SIZE = 25


def _springer_abstract(value: Any) -> str | None:
    """Springer returns the abstract either as a plain string or as a structured
    object like `{"h1": "Abstract", "p": "..." | ["...", ...]}`. Inline markup
    is stripped to plain text."""
    if isinstance(value, dict):
        value = value.get("p")
    if isinstance(value, list):
        value = " ".join(p for p in value if isinstance(p, str))
    if not isinstance(value, str):
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


async def _fetch_springer_abstracts(dois: List[str]) -> Dict[str, str]:
    """Looks up abstracts on the Springer Nature Meta API. Keys are bare, lowercase DOIs.

    Returns nothing if SPRINGER_API_KEY isn't set.
    """
    api_key = os.environ.get("SPRINGER_API_KEY")
    if not api_key or not dois:
        return {}

    abstracts: Dict[str, str] = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i in range(0, len(dois), _SPRINGER_PAGE_SIZE):
            batch = dois[i : i + _SPRINGER_PAGE_SIZE]
            params = {
                "q": "(" + " OR ".join(f"doi:{doi}" for doi in batch) + ")",
                "p": len(batch),
                "api_key": api_key,
            }
            try:
                response = await client.get(_SPRINGER_BASE, params=params)
                await check_quota("springer", response)
                response.raise_for_status()
                records = response.json().get("records", [])
            except httpx.HTTPStatusError as e:
                # Its message would contain the request URL, API key included.
                print(f"Error during Springer request: HTTP {e.response.status_code}")
                continue
            except Exception as e:
                print(f"Error during Springer request: {e}")
                continue

            for record in records:
                doi = (record.get("doi") or "").strip().lower()
                abstract = _springer_abstract(record.get("abstract"))
                if doi and abstract:
                    abstracts[doi] = abstract
    return abstracts


async def handle_springer(records: List[Record]) -> None:
    """Replaces the Crossref/OpenAlex abstracts with Springer's where it has
    one; the others are kept."""
    abstracts = await _fetch_springer_abstracts([r["id"] for r in records])
    for record in records:
        record["abstract"] = abstracts.get(record["id"]) or record.get("abstract")


# --- Scopus (Elsevier) -------------------------------------------------------
# Elsevier withholds abstracts from Crossref/OpenAlex, so they are looked up
# on the Scopus Search API, which takes precedence. Scopus only serves abstracts
# from inside a subscribing institution's network (e.g. via VPN), so the lookup
# is skipped unless HAS_INSTITUTIONAL_ACCESS is set - without it every request
# would fail anyway (e.g. on Vercel).

_SCOPUS_BASE = "https://api.elsevier.com/content/search/scopus"
# Abstracts need the COMPLETE view, which returns at most 25 results per request.
_SCOPUS_PAGE_SIZE = 25


def _has_institutional_access() -> bool:
    return os.environ.get("HAS_INSTITUTIONAL_ACCESS", "false").lower() in ("1", "true", "yes")


def _scopus_abstract(value: Any) -> str | None:
    """Scopus' `dc:description` carries a copyright notice ('© 2024 Elsevier Inc.
    All rights reserved.'), usually at the end, sometimes at the start; it is
    stripped along with surplus whitespace."""
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value).strip()
    # Leading notice: up to its last sentence-ending period before the abstract.
    text = re.sub(
        r"^(?:Copyright\s*)?©[^.]*?(?:Elsevier\s+\w+|Author\(?s\)?|reserved)\.?\s*(?:All rights reserved\.\s*)?",
        "",
        text,
    )
    # Trailing notice: everything from the © on.
    text = re.sub(r"\s*(?:Copyright\s*)?©.*$", "", text)
    return text.strip() or None


async def _fetch_scopus_abstracts(dois: List[str]) -> Dict[str, str]:
    """Looks up abstracts on the Scopus Search API. Keys are bare, lowercase DOIs.

    Returns nothing without institutional access or if ELSEVIER_API_KEY isn't set.
    """
    api_key = os.environ.get("ELSEVIER_API_KEY")
    if not api_key or not dois or not _has_institutional_access():
        return {}

    headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}
    abstracts: Dict[str, str] = {}
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for i in range(0, len(dois), _SCOPUS_PAGE_SIZE):
            batch = dois[i : i + _SCOPUS_PAGE_SIZE]
            params = {
                # Quoted, since DOIs may contain parentheses.
                "query": " OR ".join(f'DOI("{doi}")' for doi in batch),
                "view": "COMPLETE",
                "field": "prism:doi,dc:description",
                "count": len(batch),
            }
            try:
                response = await client.get(_SCOPUS_BASE, params=params)
                await check_quota("scopus", response)
                response.raise_for_status()
                entries = response.json().get("search-results", {}).get("entry", [])
            except Exception as e:
                print(f"Error during Scopus request: {e}")
                continue

            # An empty result comes back as a single `{"error": ...}` entry,
            # which has no DOI and is skipped below.
            for entry in entries:
                doi = (entry.get("prism:doi") or "").strip().lower()
                abstract = _scopus_abstract(entry.get("dc:description"))
                if doi and abstract:
                    abstracts[doi] = abstract
    return abstracts


async def handle_scopus(records: List[Record]) -> None:
    """Replaces the Crossref/OpenAlex abstracts with Scopus' where it has
    one; the others are kept."""
    abstracts = await _fetch_scopus_abstracts([r["id"] for r in records])
    for record in records:
        record["abstract"] = abstracts.get(record["id"]) or record.get("abstract")


HANDLERS: Dict[str, Handler] = {
    "springer": handle_springer,
    "scopus": handle_scopus,
}


async def apply_external_apis(records: List[Record], api_by_doi: Dict[str, str]) -> None:
    """Passes each record whose journal is flagged with an external API to that
    API's handler. Unknown API names are ignored."""
    records_by_api: Dict[str, List[Record]] = {}
    for record in records:
        api = api_by_doi.get(record["id"])
        if api in HANDLERS:
            records_by_api.setdefault(api, []).append(record)

    for api, api_records in records_by_api.items():
        await HANDLERS[api](api_records)
