import base64
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List

import httpx
from sqlmodel import Session, select

from database import models

logger = logging.getLogger(__name__)

# --- Journals that only exist on their own website ----------------------------
# Some journals are neither on Crossref nor on OpenAlex. Their papers are
# imported from the journal's website into `SiteArticle` and searched there
# alongside the Crossref/OpenAlex results (see search_service).
#
# A new journal is added by writing an importer that returns its papers as
# `SiteArticle` values and registering it in `IMPORTERS` under the journal's ISSN.

SiteArticleValues = Dict[str, Any]
Importer = Callable[[], Awaitable[List[SiteArticleValues]]]

# How long imported papers are used before the website is asked again.
_SYNC_INTERVAL = timedelta(hours=24)


def _text(fragment: str) -> str:
    """HTML fragment to plain text, whitespace collapsed."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", text).strip()


def _apa_authors(last_names: List[str]) -> str:
    """Short APA-style author string, as search_service builds it."""
    if len(last_names) == 1:
        return last_names[0]
    if len(last_names) == 2:
        return f"{last_names[0]} & {last_names[1]}"
    return f"{last_names[0]} et al." if last_names else ""


# --- International Journal of Coaching Psychology -----------------------------
# A WordPress site: every paper is a page under its volume, e.g.
# /volumes/volume-7-2026/volume-7-article-2/, with title and authors in an <h4>,
# an APA citation, the processing dates, the abstract and the PDF (linked or
# embedded). The papers are open access (CC licences) and have no DOI.

IJCP_ISSN = "2634-7946"
_IJCP_NAME = "International Journal of Coaching Psychology"
_IJCP_PAGES = "https://ijcp.nationalwellbeingservice.com/wp-json/wp/v2/pages"
_IJCP_ARTICLE_LINK = re.compile(r"/volume-(\d+)-article-(\d+)(-[^/]*)?/?$")
# Headings that only repeat the journal or the volume and article number.
_IJCP_LABEL_HEADING = re.compile(
    rf"^({re.escape(_IJCP_NAME)}|Volume \d+,? Article \d+)", flags=re.I
)


def _ijcp_published(content: str) -> str | None:
    """'Published: 4 August 2026' or 'Published online: 20 August, 2020' as ISO date."""
    match = re.search(
        r"Published(?: online)?\s*:?\s*(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", _text(content)
    )
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return datetime.strptime(f"{day} {month} {year}", "%d %B %Y").date().isoformat()
    except ValueError:
        return None


def _ijcp_title_and_authors(content: str) -> tuple[str | None, str | None]:
    """The paper's title and author line from the <strong> parts of its headings.
    Some pages put a heading like 'Volume 4, Article 5' or 'International Journal
    of Coaching Psychology, Volume 1, Article 2' in front, which is skipped."""
    headings = re.findall(r"<h\d[^>]*>(.*?)</h\d>", content, flags=re.S)
    parts = [
        _text(part)
        for heading in headings
        for part in re.findall(r"<strong>(.*?)</strong>", heading, flags=re.S)
    ]
    parts = [part for part in parts if part and not _IJCP_LABEL_HEADING.match(part)]
    title = parts[0] if parts else None
    authors = parts[1] if len(parts) > 1 else None
    return title, authors


def _ijcp_last_names(content: str, author_line: str | None) -> List[str]:
    """Last names from the APA citation ('Jenkins, J., & Rees-Davies, L. (2026).'),
    or else from the author line ('Jana Jenkins and Laura Rees-Davies')."""
    citation = re.search(r"Citation:\s*(.*?)\(\d{4}\)", _text(content))
    if citation:
        names = re.findall(r"([^,&]+?),\s*(?:[A-Z][a-z]?\.\s*-?)+", citation.group(1))
        names = [name.strip() for name in names if name.strip()]
        if names:
            return names
    if not author_line:
        return []
    people = re.split(r",\s*|\s+and\s+|\s*&\s*", author_line)
    return [person.split()[-1] for person in people if person.strip()]


def _ijcp_abstract(content: str) -> str | None:
    """The text between the 'Abstract' heading and the keywords (or the next rule)."""
    match = re.search(
        r"<strong>\s*Abstract\s*</strong>(.*?)(?:<strong>\s*Key\s*words|<hr|<div|$)",
        content,
        flags=re.S | re.I,
    )
    if not match:
        return None
    return _text(match.group(1)) or None


def _ijcp_pdf(content: str) -> str | None:
    """The PDF linked from the page, or the one in its embedded PDF viewer. Newer
    pages embed a PDF that can't be opened on its own (`pdfemb-serveurl`, under
    /securepdfs/); they have none."""
    link = re.search(r'href="([^"]+\.pdf)"', content)
    if link:
        return link.group(1)
    embed = re.search(r"pdfemb-data=([A-Za-z0-9+/=]+)", content)
    if embed:
        try:
            data = json.loads(base64.b64decode(embed.group(1) + "=" * (-len(embed.group(1)) % 4)))
            return data.get("url")
        except ValueError:
            return None
    return None


def parse_ijcp_page(page: Dict[str, Any]) -> SiteArticleValues | None:
    """A paper from a page of the WordPress API, or None for every other page
    (volume overviews, covers, editorials, empty placeholders)."""
    link = page.get("link") or ""
    match = _IJCP_ARTICLE_LINK.search(link)
    # Editorials aren't papers, as in the Crossref/OpenAlex search.
    if not match or "editorial" in (match.group(3) or ""):
        return None
    content = (page.get("content") or {}).get("rendered") or ""
    title, author_line = _ijcp_title_and_authors(content)
    # Pages of papers yet to come have no title; book reviews aren't papers.
    if not title or title.lower().startswith("book review"):
        return None
    volume, number = match.group(1), match.group(2)
    return {
        "id": link,
        "issn": IJCP_ISSN,
        "journal_name": _IJCP_NAME,
        "title": title,
        "author": _apa_authors(_ijcp_last_names(content, author_line)) or None,
        # The page's own date is when it went up, which is close enough if the
        # processing dates are missing.
        "publication_date": _ijcp_published(content) or (page.get("date") or "")[:10] or None,
        "issue": f"Vol. {volume}, Article {number}",
        "abstract": _ijcp_abstract(content),
        "url": link,
        "pdf_url": _ijcp_pdf(content),
    }


async def import_ijcp() -> List[SiteArticleValues]:
    """Every paper on the IJCP website."""
    articles: List[SiteArticleValues] = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        page_number = 1
        while True:
            response = await client.get(
                _IJCP_PAGES,
                params={
                    "per_page": 100,
                    "page": page_number,
                    "_fields": "date,link,content",
                },
            )
            response.raise_for_status()
            articles += [a for a in map(parse_ijcp_page, response.json()) if a]
            if page_number >= int(response.headers.get("X-WP-TotalPages") or 1):
                return articles
            page_number += 1


IMPORTERS: Dict[str, Importer] = {
    IJCP_ISSN: import_ijcp,
}


# --- Sync and search ----------------------------------------------------------


async def sync_site_articles(session: Session, issns: List[str]) -> None:
    """Imports the papers of the given journals whose last import is older than a
    day. A failing website keeps its earlier papers; the search goes on without
    the new ones."""
    now = datetime.now(timezone.utc)
    for issn in issns:
        importer = IMPORTERS.get(issn)
        if importer is None:
            continue
        state = session.get(models.SiteImport, issn)
        # SQLite hands the UTC timestamp back without a timezone.
        synced_at = state and state.synced_at.replace(tzinfo=timezone.utc)
        if synced_at and now - synced_at < _SYNC_INTERVAL:
            continue
        try:
            articles = await importer()
        except Exception as e:
            logger.error("Import of the papers of journal %s failed: %s", issn, e)
            continue
        for values in articles:
            session.merge(models.SiteArticle(**values))
        session.merge(models.SiteImport(issn=issn, synced_at=now))
        session.commit()
        logger.info("Imported %d paper(s) of journal %s", len(articles), issn)


def _matches(article: models.SiteArticle, words: List[str]) -> bool:
    """Every keyword appears in the title, abstract or authors."""
    text = " ".join(
        value or "" for value in (article.title, article.abstract, article.author)
    ).lower()
    return all(word in text for word in words)


def search_site_articles(
    session: Session, issns: List[str], keywords: str, from_date: str, to_date: str
) -> List[Dict[str, Any]]:
    """The imported papers of the journals published in the date range that
    contain every keyword, newest first, as search results."""
    if not any(issn in IMPORTERS for issn in issns):
        return []
    articles = session.exec(
        select(models.SiteArticle).where(
            models.SiteArticle.issn.in_(issns),
            models.SiteArticle.publication_date >= from_date,
            models.SiteArticle.publication_date <= to_date,
        )
    ).all()
    words = keywords.lower().split()
    articles = sorted(
        (a for a in articles if _matches(a, words)),
        key=lambda a: a.publication_date or "",
        reverse=True,
    )
    return [
        {
            "id": article.id,
            "doi": None,
            "url": article.url,
            "title": article.title,
            "journal_name": article.journal_name,
            "publication_date": article.publication_date,
            "journal_publication_date": article.publication_date,
            "issue": article.issue,
            # Open access, so the PDF (or the page that shows it) stands in for
            # the library's full text.
            "library_url": article.pdf_url or article.url,
            "abstract": article.abstract,
            "topic": None,
            "author": article.author,
        }
        for article in articles
    ]
