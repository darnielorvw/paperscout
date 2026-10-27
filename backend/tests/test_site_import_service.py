"""Tests for the papers imported from journal websites (site_import_service) and
how the search puts them ahead of the Crossref/OpenAlex results."""

import asyncio
import base64
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database import models
from services import site_import_service
from services.search_service import (
    SearchService,
    _bm25_scorer,
    _insertion_points,
    _ranking_text,
)
from services.site_import_service import IJCP_ISSN, parse_ijcp_page

BASE = "https://ijcp.nationalwellbeingservice.com/volumes"

# Shaped like the current pages (e.g. Volume 7, Article 2).
CURRENT_PAGE = """
<h4><strong>Exploring professional boundaries between coaching and therapy</strong><br />
<strong>Jana Jenkins and Laura Rees-Davies</strong></h4>
<p><a href="https://ijcp.nationalwellbeingservice.com/wp-content/uploads/2026/08/IJCP-7-2.pdf">
<strong>ARTICLE DOWNLOAD</strong></a></p>
<p><strong>Citation:</strong> Jenkins, J., &amp; Rees-Davies, L. (2026). Exploring professional
boundaries. International Journal of Coaching Psychology, 7, 2, 1-16.</p>
<p><strong>Processing dates</strong>: Submitted: 6 May 2025; Accepted: 5 May 2026;
Published: 4 August 2026</p>
<p><strong>Abstract</strong><br />
<strong>Aims:</strong> The aim was to explore boundaries.</p>
<p><strong>Methods:</strong> Ten psychologists were interviewed.</p>
<p><strong>Keywords</strong>: coaching, therapy</p>
"""

# Shaped like the 2020 pages: a journal heading in front, the PDF only embedded.
OLD_PAGE = """
<h4><strong>International Journal of Coaching Psychology, Volume 1, Article 2</strong></h4>
<h4><strong>Coaching during the COVID-19 pandemic</strong><br />
<strong>Helen Williams and Stephen Palmer</strong></h4>
<p><strong>Citation: </strong>Williams, H., &amp; Palmer, S. (2020). Coaching during the
COVID-19 pandemic. International Journal of Coaching Psychology, 1, 2, 1-11.</p>
<p><strong>Processing Dates: </strong>Received 14 July 2020; Published online: 20 August, 2020</p>
<hr />
<p><strong>Abstract</strong><br />
This article considers the CLARITY model.</p>
<hr />
<iframe src="https://ijcp.nationalwellbeingservice.com/?pdfemb-data={embed}"></iframe>
"""


def _embed(data: dict) -> str:
    return base64.b64encode(json.dumps(data).encode()).decode().rstrip("=")


def _page(link: str, content: str, date: str = "2026-08-04T16:01:58") -> dict:
    return {"link": link, "date": date, "content": {"rendered": content}}


class TestParseIjcpPage:
    def test_reads_a_current_paper(self):
        article = parse_ijcp_page(_page(f"{BASE}/volume-7-2026/volume-7-article-2/", CURRENT_PAGE))
        assert article == {
            "id": f"{BASE}/volume-7-2026/volume-7-article-2/",
            "issn": IJCP_ISSN,
            "journal_name": "International Journal of Coaching Psychology",
            "title": "Exploring professional boundaries between coaching and therapy",
            "author": "Jenkins & Rees-Davies",
            "publication_date": "2026-08-04",
            "issue": "Vol. 7, Article 2",
            "abstract": "Aims: The aim was to explore boundaries. "
            "Methods: Ten psychologists were interviewed.",
            "url": f"{BASE}/volume-7-2026/volume-7-article-2/",
            "pdf_url": "https://ijcp.nationalwellbeingservice.com/wp-content/uploads/2026/08/IJCP-7-2.pdf",
        }

    def test_reads_an_old_paper_with_an_embedded_pdf(self):
        pdf = "https://ijcp.nationalwellbeingservice.com/wp-content/uploads/2020/08/IJCP-1-2.pdf"
        content = OLD_PAGE.format(embed=_embed({"url": pdf, "title": "IJCP 1-2"}))
        article = parse_ijcp_page(_page(f"{BASE}/volume-1-2020/volume-1-article-2/", content))
        assert article["title"] == "Coaching during the COVID-19 pandemic"
        assert article["author"] == "Williams & Palmer"
        assert article["publication_date"] == "2020-08-20"
        assert article["abstract"] == "This article considers the CLARITY model."
        assert article["pdf_url"] == pdf

    def test_skips_a_volume_and_article_heading(self):
        content = CURRENT_PAGE.replace(
            "<h4>", "<h3><strong>Volume 4, Article 5 </strong></h3><h4>", 1
        )
        article = parse_ijcp_page(_page(f"{BASE}/volume-4-2023/volume-4-article-5/", content))
        assert article["title"] == "Exploring professional boundaries between coaching and therapy"

    def test_a_protected_embedded_pdf_is_left_out(self):
        serve_url = "https%3A%2F%2Fexample.org%2Fsecurepdfs%2FIJCP-6-8.pdf"
        content = OLD_PAGE.format(embed=_embed({"pdfemb-serveurl": serve_url}))
        article = parse_ijcp_page(_page(f"{BASE}/volume-6-2025/volume-6-article-8/", content))
        assert article["pdf_url"] is None

    def test_falls_back_to_the_page_date(self):
        content = CURRENT_PAGE.replace("Published: 4 August 2026", "")
        article = parse_ijcp_page(
            _page(f"{BASE}/volume-7-2026/volume-7-article-2/", content, date="2026-08-01T10:00:00")
        )
        assert article["publication_date"] == "2026-08-01"

    def test_falls_back_to_the_author_line(self):
        content = CURRENT_PAGE.replace("Citation:", "Reference:")
        article = parse_ijcp_page(_page(f"{BASE}/volume-7-2026/volume-7-article-2/", content))
        assert article["author"] == "Jenkins & Rees-Davies"

    @pytest.mark.parametrize(
        "link, content",
        [
            (f"{BASE}/volume-7-2026/", ""),
            (f"{BASE}/volume-6-2025/volume-6-journal-cover/", ""),
            (f"{BASE}/volume-6-2025/volume-6-article-1-editorial/", CURRENT_PAGE),
            (f"{BASE}/volume-1-2020/volume-1-article-6/", "<p>Volume 1, Article 6</p>"),
            (
                f"{BASE}/volume-6-2025/volume-6-article-6/",
                "<h3><strong>Book review: Family Life Coaching Handbook</strong></h3>",
            ),
        ],
    )
    def test_other_pages_are_no_papers(self, link, content):
        assert parse_ijcp_page(_page(link, content)) is None


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _article(number: int, published: str, **overrides) -> dict:
    article = {
        "id": f"{BASE}/volume-7-2026/volume-7-article-{number}/",
        "issn": IJCP_ISSN,
        "journal_name": "International Journal of Coaching Psychology",
        "title": f"Paper {number}",
        "author": "Palmer",
        "publication_date": published,
        "issue": f"Vol. 7, Article {number}",
        "abstract": "About coaching.",
        "url": f"{BASE}/volume-7-2026/volume-7-article-{number}/",
        "pdf_url": None,
    }
    article.update(overrides)
    return article


@pytest.fixture
def importer(monkeypatch):
    """Replaces the IJCP importer; `calls` counts how often it ran."""
    state = {"articles": [], "calls": 0}

    async def fake_import():
        state["calls"] += 1
        return state["articles"]

    monkeypatch.setitem(site_import_service.IMPORTERS, IJCP_ISSN, fake_import)
    return state


class TestSync:
    def test_imports_and_updates_the_papers(self, db, importer):
        importer["articles"] = [_article(1, "2026-06-30")]
        asyncio.run(site_import_service.sync_site_articles(db, [IJCP_ISSN]))
        importer["articles"] = [
            _article(1, "2026-06-30", title="Corrected"),
            _article(2, "2026-08-04"),
        ]
        db.get(models.SiteImport, IJCP_ISSN).synced_at = datetime(2020, 1, 1)
        asyncio.run(site_import_service.sync_site_articles(db, [IJCP_ISSN]))

        titles = sorted(a.title for a in db.exec(select(models.SiteArticle)).all())
        assert titles == ["Corrected", "Paper 2"]

    def test_a_recent_import_is_reused(self, db, importer):
        asyncio.run(site_import_service.sync_site_articles(db, [IJCP_ISSN]))
        asyncio.run(site_import_service.sync_site_articles(db, [IJCP_ISSN]))
        assert importer["calls"] == 1

    def test_imports_again_after_a_day(self, db, importer):
        asyncio.run(site_import_service.sync_site_articles(db, [IJCP_ISSN]))
        state = db.get(models.SiteImport, IJCP_ISSN)
        state.synced_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()
        asyncio.run(site_import_service.sync_site_articles(db, [IJCP_ISSN]))
        assert importer["calls"] == 2

    def test_a_failing_website_keeps_the_papers(self, db, monkeypatch):
        db.add(models.SiteArticle(**_article(1, "2026-06-30")))
        db.commit()

        async def failing_import():
            raise RuntimeError("site down")

        monkeypatch.setitem(site_import_service.IMPORTERS, IJCP_ISSN, failing_import)
        asyncio.run(site_import_service.sync_site_articles(db, [IJCP_ISSN]))
        assert db.get(models.SiteImport, IJCP_ISSN) is None
        assert len(db.exec(select(models.SiteArticle)).all()) == 1


class TestSearchSiteArticles:
    @pytest.fixture(autouse=True)
    def papers(self, db):
        db.add(models.SiteArticle(**_article(1, "2026-06-30", title="Adlerian coaching")))
        db.add(models.SiteArticle(**_article(2, "2026-08-04", abstract="Coaching and therapy.")))
        db.add(models.SiteArticle(**_article(3, "2025-09-04")))
        db.commit()

    def _ids(self, db, keywords="", from_date="2026-01-01", to_date="2026-12-31"):
        results = site_import_service.search_site_articles(
            db, [IJCP_ISSN], keywords, from_date, to_date
        )
        return [r["issue"] for r in results]

    def test_date_range_newest_first(self, db):
        assert self._ids(db) == ["Vol. 7, Article 2", "Vol. 7, Article 1"]

    def test_every_keyword_must_match(self, db):
        assert self._ids(db, "coaching THERAPY") == ["Vol. 7, Article 2"]
        assert self._ids(db, "adlerian") == ["Vol. 7, Article 1"]

    def test_links_the_pdf_or_else_the_page(self, db):
        result = site_import_service.search_site_articles(
            db, [IJCP_ISSN], "adlerian", "2026-01-01", "2026-12-31"
        )[0]
        assert result["doi"] is None
        assert result["library_url"] == result["url"] == _article(1, "")["url"]

    def test_other_journals_have_none(self, db):
        assert (
            site_import_service.search_site_articles(
                db, ["1234-5678"], "", "2026-01-01", "2026-12-31"
            )
            == []
        )


# Crossref results of TestSearchMerge, newest first as Crossref returns them.
API_DATES = ["2026-11-01", "2026-09-01", "2026-07-01", "2026-05-01", "2026-02-15", "2026-01-15"]


class TestSearchMerge:
    """Without keywords, the website papers go by date among the Crossref results."""

    @pytest.fixture
    def service(self, monkeypatch, db, importer):
        importer["articles"] = [_article(n, f"2026-0{n}-01") for n in range(1, 4)]
        service = SearchService()
        service.calls = []
        service.counts = []

        async def fake_search(issns, keywords, from_date, to_date, offset, rows, external_apis):
            service.calls.append((issns, offset, rows))
            api = [{"id": f"10.1/{n}", "doi": f"https://doi.org/10.1/{n}"} for n in range(6)]
            return {"meta": {"count": len(api)}, "results": api[offset : offset + rows]}

        # Answers the count queries: the results issued from the given date on.
        async def fake_fetch_crossref(endpoint, params):
            after = re.search(r"from-issued-date:([\d-]+)", params["filter"]).group(1)
            service.counts.append(after)
            return {"message": {"total-results": sum(d >= after for d in API_DATES)}}

        monkeypatch.setattr(service, "_search", fake_search)
        monkeypatch.setattr(service, "_fetch_crossref", fake_fetch_crossref)
        return service

    def _ids(self, service, db, page, issns=(IJCP_ISSN, "1234-5678"), limit=2):
        data = asyncio.run(
            service.search(
                issns=list(issns),
                keywords="",
                from_date="2026-01-01",
                to_date="2026-12-31",
                limit=limit,
                page=page,
                session=db,
            )
        )
        return [r.get("issue") or r["id"] for r in data["results"]], data["meta"]

    def test_the_papers_go_by_date(self, service, db):
        ids, meta = self._ids(service, db, page=1, limit=25)
        assert ids == [
            "10.1/0",  # 2026-11-01
            "10.1/1",
            "10.1/2",
            "10.1/3",  # 2026-05-01
            "Vol. 7, Article 3",  # 2026-03-01
            "10.1/4",  # 2026-02-15
            "Vol. 7, Article 2",  # 2026-02-01
            "10.1/5",  # 2026-01-15
            "Vol. 7, Article 1",  # 2026-01-01
        ]
        assert meta == {"count": 9, "page": 1, "per_page": 25}

    def test_pages_cut_the_merged_list(self, service, db):
        pages = [self._ids(service, db, page=n)[0] for n in range(1, 6)]
        assert pages == [
            ["10.1/0", "10.1/1"],
            ["10.1/2", "10.1/3"],
            ["Vol. 7, Article 3", "10.1/4"],
            ["Vol. 7, Article 2", "10.1/5"],
            ["Vol. 7, Article 1"],
        ]

    def test_fetches_only_the_api_results_of_the_page(self, service, db):
        self._ids(service, db, page=3)
        assert service.calls == [(["1234-5678"], 4, 1)]

    def test_counts_are_cached(self, service, db):
        self._ids(service, db, page=1)
        self._ids(service, db, page=2)
        assert sorted(service.counts) == ["2026-01-02", "2026-02-02", "2026-03-02"]

    def test_only_a_website_journal_needs_no_api(self, service, db):
        ids, meta = self._ids(service, db, page=1, issns=[IJCP_ISSN], limit=25)
        assert ids == ["Vol. 7, Article 3", "Vol. 7, Article 2", "Vol. 7, Article 1"]
        assert meta["count"] == 3
        assert service.calls == []
        assert service.counts == []

    def test_without_a_session_only_the_apis_are_searched(self, service, db):
        data = asyncio.run(
            service.search(
                issns=["1234-5678"],
                keywords="",
                from_date="2026-01-01",
                to_date="2026-12-31",
                limit=2,
                page=1,
            )
        )
        assert [r["id"] for r in data["results"]] == ["10.1/0", "10.1/1"]
        assert data["meta"] == {"count": 6, "page": 1, "per_page": 2}


class TestInsertionPoints:
    def test_goes_behind_every_hit_that_scores_higher(self):
        assert _insertion_points([9.0, 7.0, 5.0, 3.0], [6.0]) == [2]

    def test_best_and_worst(self):
        assert _insertion_points([9.0, 7.0], [10.0, 1.0]) == [0, 2]

    def test_ties_stay_in_front(self):
        assert _insertion_points([9.0, 7.0, 7.0], [7.0]) == [3]

    def test_keeps_the_openalex_order(self):
        # OpenAlex ranks a lower-scoring hit first (e.g. by citations); the paper
        # still goes behind it, since a higher-scoring hit follows.
        assert _insertion_points([2.0, 8.0, 1.0], [5.0]) == [2]


class TestBm25:
    def test_more_matches_score_higher(self):
        corpus = [_ranking_text("coaching therapy", "boundaries"), _ranking_text("leadership", "")]
        score = _bm25_scorer(corpus, "coaching therapy")
        assert score(_ranking_text("coaching therapy", "")) > score(_ranking_text("coaching", ""))
        assert score(_ranking_text("leadership", "")) == 0

    def test_the_title_counts_more_than_the_abstract(self):
        score = _bm25_scorer([_ranking_text("x", "y")], "coaching")
        assert score(_ranking_text("coaching", "a b")) > score(_ranking_text("a b", "coaching"))


class TestKeywordRanking:
    """With keywords, the website papers are ranked among the OpenAlex hits."""

    @pytest.fixture
    def service(self, monkeypatch, db, importer):
        importer["articles"] = [
            _article(1, "2026-03-01", title="Coaching and therapy", abstract=""),
            _article(2, "2026-04-01", title="Leadership", abstract="Some coaching and therapy."),
        ]
        service = SearchService()
        # Five hits in OpenAlex order, from strong to weak matches.
        titles = ["coaching therapy coaching", "coaching therapy", "therapy", "other", "other"]
        hits = [{"DOI": f"10.1/{n}", "title": [title]} for n, title in enumerate(titles)]

        async def fake_hits(issns, keywords, from_date, to_date):
            return hits, {}

        async def fake_search(issns, keywords, from_date, to_date, offset, rows, external_apis):
            api = [{"id": hit["DOI"]} for hit in hits]
            return {"meta": {"count": len(api)}, "results": api[offset : offset + rows]}

        monkeypatch.setattr(service, "_cached_keyword_hits", fake_hits)
        monkeypatch.setattr(service, "_search", fake_search)
        return service

    def _ids(self, service, db, page, limit=10):
        data = asyncio.run(
            service.search(
                issns=[IJCP_ISSN, "1234-5678"],
                keywords="coaching therapy",
                from_date="2026-01-01",
                to_date="2026-12-31",
                limit=limit,
                page=page,
                session=db,
            )
        )
        return [r.get("issue") or r["id"] for r in data["results"]], data["meta"]["count"]

    def test_ranks_the_papers_among_the_hits(self, service, db):
        ids, count = self._ids(service, db, page=1)
        # Both papers score below the two "coaching therapy" hits and above the
        # "therapy" one; the better one first.
        assert ids == [
            "10.1/0",
            "10.1/1",
            "Vol. 7, Article 1",
            "Vol. 7, Article 2",
            "10.1/2",
            "10.1/3",
            "10.1/4",
        ]
        assert count == 7

    def test_pages_cut_the_merged_list(self, service, db):
        pages = [self._ids(service, db, page=n, limit=3)[0] for n in (1, 2, 3)]
        assert pages == [
            ["10.1/0", "10.1/1", "Vol. 7, Article 1"],
            ["Vol. 7, Article 2", "10.1/2", "10.1/3"],
            ["10.1/4"],
        ]
