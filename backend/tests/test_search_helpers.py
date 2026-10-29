"""Unit tests for the pure data-transformation helpers in the search service.

These functions do no I/O - they only reshape the JSON that Crossref and
OpenAlex return - so they can be tested directly with plain dicts.
"""

import asyncio
from urllib.parse import parse_qs

import pytest

from config import settings
from services.search_service import (
    SearchService,
    _apa_from_last_names,
    _clean_doi,
    _clean_title,
    _crossref_openurl_fields,
    _date_parts_to_iso,
    _is_paper,
    _issue_label,
    _low_value_score,
    _merge,
    _open_access,
    _openurl,
    _page_count,
    _strip_jats,
    format_authors_apa,
    format_authors_apa_crossref,
    openurl_resolver_for,
)


class TestCleanDoi:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("10.1000/ABC", "10.1000/abc"),
            ("https://doi.org/10.1000/abc", "10.1000/abc"),
            ("http://doi.org/10.1000/abc", "10.1000/abc"),
            ("doi:10.1000/abc", "10.1000/abc"),
            ("  10.1000/abc  ", "10.1000/abc"),
            ("", ""),
        ],
    )
    def test_normalises_every_doi_form(self, raw, expected):
        assert _clean_doi(raw) == expected

    def test_none_input(self):
        assert _clean_doi(None) == ""


class TestOpenurl:
    def test_builds_resolver_link(self):
        url = _openurl(
            {
                "doi": "https://doi.org/10.1000/ABC",
                "title": "Deep Learning & Co",
                "journal_name": "Nature",
                "publication_date": "2024-03-07",
            },
            settings.OPENURL_RESOLVER,
        )
        base, query = url.split("?", 1)
        assert base == settings.OPENURL_RESOLVER
        assert parse_qs(query) == {
            "ctx_ver": ["Z39.88-2004"],
            "rft_val_fmt": ["info:ofi/fmt:kev:mtx:journal"],
            "rft.genre": ["article"],
            "rft_id": ["info:doi/10.1000/abc"],
        }

    def test_no_doi(self):
        assert _openurl({"doi": None, "title": "Something"}, settings.OPENURL_RESOLVER) is None

    def test_resolver_with_own_query(self):
        url = _openurl({"doi": "10.1000/abc"}, "https://library.example/openurl?vid=X")
        base, query = url.split("?", 1)
        assert base == "https://library.example/openurl"
        assert parse_qs(query)["vid"] == ["X"]
        assert parse_qs(query)["rft_id"] == ["info:doi/10.1000/abc"]


class TestOpenurlResolverFor:
    def test_muenster_users_get_their_resolver(self):
        assert (
            openurl_resolver_for("someone@Uni-Muenster.de")
            == settings.OPENURL_RESOLVERS_BY_DOMAIN["uni-muenster.de"]
        )

    @pytest.mark.parametrize(
        "email", ["someone@fh-swf.de", "someone@wi.uni-muenster.de", "uni-muenster.de@gmail.com"]
    )
    def test_everyone_else_gets_the_default(self, email):
        assert openurl_resolver_for(email) == settings.OPENURL_RESOLVER


class TestDatePartsToIso:
    def test_full_date(self):
        assert _date_parts_to_iso({"date-parts": [[2024, 3, 7]]}) == "2024-03-07"

    def test_year_only_pads_to_january_first(self):
        assert _date_parts_to_iso({"date-parts": [[2024]]}) == "2024-01-01"

    def test_year_and_month_pads_day(self):
        assert _date_parts_to_iso({"date-parts": [[2024, 11]]}) == "2024-11-01"

    def test_zero_pads_single_digits(self):
        assert _date_parts_to_iso({"date-parts": [[2024, 1, 2]]}) == "2024-01-02"

    @pytest.mark.parametrize("value", [None, {}, {"date-parts": []}, {"date-parts": [[]]}])
    def test_missing_or_empty_returns_none(self, value):
        assert _date_parts_to_iso(value) is None

    def test_non_numeric_returns_none(self):
        assert _date_parts_to_iso({"date-parts": [["nope"]]}) is None


class TestCleanTitle:
    def test_removes_inline_tags(self):
        assert (
            _clean_title("Pretreatment of <scp>ADSC</scp> ‐Exos via <scp>YAP</scp>")
            == "Pretreatment of ADSC ‐Exos via YAP"
        )

    def test_does_not_split_words_at_tags(self):
        assert _clean_title("CO<sub>2</sub> and <i>E. coli</i>") == "CO2 and E. coli"

    def test_unescapes_entities(self):
        assert _clean_title("Cats &amp; Dogs &lt;3") == "Cats & Dogs <3"

    @pytest.mark.parametrize("value", [None, "", "  ", "<i></i>"])
    def test_empty_returns_none(self, value):
        assert _clean_title(value) is None


class TestStripJats:
    def test_removes_xml_tags(self):
        assert (
            _strip_jats("<jats:p>Hello <jats:italic>world</jats:italic></jats:p>") == "Hello world"
        )

    def test_collapses_whitespace(self):
        assert _strip_jats("<p>a</p>\n\n  <p>b</p>") == "a b"

    def test_strips_leading_abstract_label(self):
        assert _strip_jats("<jats:p>Abstract This paper</jats:p>") == "This paper"

    @pytest.mark.parametrize("value", [None, "", "   ", "<p></p>"])
    def test_empty_returns_none(self, value):
        assert _strip_jats(value) is None


class TestIssueLabel:
    def test_volume_and_issue(self):
        assert _issue_label("12", "3") == "Vol. 12, Issue 3"

    def test_volume_only(self):
        assert _issue_label("12", None) == "Vol. 12"

    def test_issue_only(self):
        assert _issue_label(None, "3") == "Issue 3"

    def test_neither_returns_none(self):
        assert _issue_label(None, None) is None
        assert _issue_label("", "") is None


class TestApaFromLastNames:
    @pytest.mark.parametrize(
        "names, expected",
        [
            ([], ""),
            (["Smith"], "Smith"),
            (["Smith", "Jones"], "Smith & Jones"),
            (["Smith", "Jones", "Brown"], "Smith et al."),
            (["Smith", None, ""], "Smith"),
        ],
    )
    def test_author_counts(self, names, expected):
        assert _apa_from_last_names(names) == expected


class TestFormatAuthorsApa:
    def test_openalex_shape_uses_last_word_of_display_name(self):
        authorships = [
            {"author": {"display_name": "Ada Lovelace"}},
            {"author": {"display_name": "Alan M. Turing"}},
        ]
        assert format_authors_apa(authorships) == "Lovelace & Turing"

    def test_openalex_skips_entries_without_a_name(self):
        authorships = [{"author": {"display_name": "Ada Lovelace"}}, {"author": {}}, {}]
        assert format_authors_apa(authorships) == "Lovelace"

    def test_openalex_empty(self):
        assert format_authors_apa([]) == ""
        assert format_authors_apa(None) == ""

    def test_crossref_shape_prefers_family_then_name(self):
        authors = [{"given": "Ada", "family": "Lovelace"}, {"name": "CERN Collaboration"}]
        assert format_authors_apa_crossref(authors) == "Lovelace & CERN Collaboration"

    def test_crossref_empty(self):
        assert format_authors_apa_crossref(None) == ""


class TestExtractAbstract:
    def setup_method(self):
        self.svc = SearchService()

    def test_reconstructs_from_inverted_index_in_position_order(self):
        inverted = {"This": [0], "is": [1], "an": [2], "abstract": [3]}
        assert self.svc._extract_abstract(inverted) == "This is an abstract"

    def test_handles_repeated_words(self):
        inverted = {"very": [0, 1], "long": [2]}
        assert self.svc._extract_abstract(inverted) == "very very long"

    def test_strips_leading_abstract_label(self):
        inverted = {"Abstract": [0], "body": [1]}
        assert self.svc._extract_abstract(inverted) == "body"

    @pytest.mark.parametrize("value", [None, {}])
    def test_empty_returns_none(self, value):
        assert self.svc._extract_abstract(value) is None


class TestIsPaper:
    @pytest.mark.parametrize("work_type", ["article", "review"])
    def test_keeps_papers(self, work_type):
        assert _is_paper({"type": work_type})

    @pytest.mark.parametrize("work_type", ["editorial", "erratum", "letter", "paratext", None])
    def test_drops_non_papers(self, work_type):
        assert not _is_paper({"type": work_type})

    def test_keeps_dois_unknown_to_openalex(self):
        assert _is_paper(None)


class TestPageCount:
    @pytest.mark.parametrize(
        "page, expected",
        [("123-125", 3), ("S12–S14", 3), ("7-7", 1), ("e12345", None), ("12", None), (None, None)],
    )
    def test_counts_page_ranges(self, page, expected):
        assert _page_count(page) == expected


class TestLowValueScore:
    @pytest.mark.parametrize(
        "title",
        [
            "A Commentary on “Leadership and Trust in Remote Teams” by Smith et al.",
            "Reply to Jones: The effect remains robust",
            "Rethinking burnout: A response to critics",
            "Editorial: Looking back on ten years",
            "Correction to: Effects of sleep on memory",
            "Introduction to the special issue on work and health",
            "From the editors: What makes a theory contribution?",
            "Erratum",
            "HUMAN RELATIONSCall for Proposals: Critical Reviews Special Issue",
        ],
    )
    def test_commentary_titles_reach_the_threshold(self, title):
        assert _low_value_score(title, None, True, None) >= 3

    @pytest.mark.parametrize(
        "title",
        [
            "Neural responses to threat in anxious adolescents",
            "Comment sections and online incivility",
            "Employee reply behaviour in e-mail threads",
            "Editorial board diversity and citation impact",
            "Retraction rates in psychology journals",
            "Why do papers get retracted? Editorial decisions under scrutiny",
            "Erratum management in hospitals",
        ],
    )
    def test_ordinary_titles_score_nothing(self, title):
        assert _low_value_score(title, "100-120", True, 60) == 0

    def test_short_paper_alone_doesnt(self):
        assert _low_value_score("Some findings", "100-102", True, 40) == 2

    def test_short_paper_without_abstract_reaches_the_threshold(self):
        assert _low_value_score("Some findings", "100-102", False, None) >= 3

    def test_missing_abstract_and_few_references_alone_dont(self):
        assert _low_value_score("Some findings", None, False, 14) == 2

    def test_zero_references_are_unknown(self):
        assert _low_value_score("Some findings", None, True, 0) == 0


class TestOpenAccess:
    def test_green_paper_links_the_repository_copy(self):
        work = {
            "open_access": {"is_oa": True, "oa_status": "green", "oa_url": "https://repo/1"},
            "best_oa_location": {
                "landing_page_url": "https://repo/1",
                "source": {"display_name": "Some Repository"},
            },
        }
        assert _open_access(work) == {
            "url": "https://repo/1",
            "status": "green",
            "host": "Some Repository",
        }

    @pytest.mark.parametrize(
        "work",
        [
            {},
            {"open_access": {"is_oa": False, "oa_url": None}},
            {"open_access": {"is_oa": True, "oa_url": None}, "best_oa_location": None},
        ],
    )
    def test_none_without_free_version(self, work):
        assert _open_access(work) is None


class TestFillOpenalex:
    def setup_method(self):
        self.svc = SearchService()

    def test_openalex_abstract_beats_crossref_but_other_fields_only_fill_gaps(self):
        records = [
            {"id": "a", "abstract": "From Crossref", "topic": "Kept"},
            {"id": "b", "abstract": "From Crossref", "topic": None},
        ]
        oa_by_doi = {
            "a": {
                "abstract_inverted_index": {"From": [0], "OpenAlex": [1]},
                "primary_topic": {"display_name": "Other"},
            },
            "b": {"abstract_inverted_index": None, "primary_topic": {"display_name": "Filled"}},
        }
        self.svc._fill_openalex(records, oa_by_doi)
        assert [(r["abstract"], r["topic"]) for r in records] == [
            ("From OpenAlex", "Kept"),
            ("From Crossref", "Filled"),
        ]


class TestSemanticHits:
    def setup_method(self):
        self.svc = SearchService()
        self.requests = []

        async def fetch_openalex(endpoint, params):
            self.requests.append(params)
            return {
                "results": [
                    {"doi": "https://doi.org/10.1/A", "title": "Trust in robots"},
                    {"doi": "https://doi.org/10.1/b", "title": "Robot navigation"},
                    {"doi": None, "title": "Trust without a DOI"},
                ]
            }

        async def issued_in_range(dois, from_date, to_date, slots):
            # Crossref drops 10.1/b, which isn't issued in the date range.
            return [{"DOI": doi} for doi in dois if doi != "10.1/b"]

        self.svc._fetch_openalex = fetch_openalex
        self.svc._crossref_issued_in_range = issued_in_range

    def test_filters_by_source_type_and_year_and_keeps_similarity_order(self):
        hits, oa_by_doi, complete = asyncio.run(
            self.svc._semantic_hits(["S1", "S2"], "trust", "2026-01-01", "2026-03-31")
        )
        params = self.requests[0]
        assert params["search.semantic"] == "trust"
        assert params["filter"] == (
            "primary_location.source.id:S1|S2,type:article|review,publication_year:2024-2026"
        )
        assert params["per_page"] == 50
        assert hits == [{"DOI": "10.1/a"}]
        assert set(oa_by_doi) == {"10.1/a", "10.1/b"}
        assert complete

    def test_no_journals_no_request(self):
        assert asyncio.run(self.svc._semantic_hits([], "trust", "2026-01-01", "2026-03-31")) == (
            [],
            {},
            True,
        )
        assert self.requests == []


class TestMerge:
    def test_fills_only_empty_fields(self):
        record = {"title": "Kept", "abstract": None}
        _merge(record, {"title": "Other", "abstract": "Filled"})
        assert record == {"title": "Kept", "abstract": "Filled"}

    @pytest.mark.parametrize("empty", [None, "", []])
    def test_empty_values_never_overwrite(self, empty):
        record = {"issue": "Vol. 1"}
        _merge(record, {"issue": empty})
        assert record == {"issue": "Vol. 1"}


class TestCrossrefOpenurlFields:
    def test_citation_without_journal_title(self):
        fields = _crossref_openurl_fields(
            {
                "title": ["Array programming with NumPy"],
                "container-title": ["Nature"],
                "issn-type": [
                    {"type": "print", "value": "0028-0836"},
                    {"type": "electronic", "value": "1476-4687"},
                ],
                "issued": {"date-parts": [[2020, 9, 16]]},
                "volume": "585",
                "issue": "7825",
                "page": "357-362",
            }
        )
        assert fields == {
            "rft.atitle": "Array programming with NumPy",
            "rft.issn": "0028-0836",
            "rft.eissn": "1476-4687",
            "rft.date": "2020",
            "rft.volume": "585",
            "rft.issue": "7825",
            "rft.spage": "357",
        }

    def test_goes_into_the_link(self):
        url = _openurl(
            {"doi": "10.1000/abc", "openurl": {"rft.issn": "1234-5678"}},
            settings.OPENURL_RESOLVER,
        )
        query = parse_qs(url.split("?", 1)[1])
        assert query["rft.issn"] == ["1234-5678"]
        assert "rft.jtitle" not in query
