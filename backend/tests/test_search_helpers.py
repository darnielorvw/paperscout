"""Unit tests for the pure data-transformation helpers in the search service.

These functions do no I/O - they only reshape the JSON that Crossref and
OpenAlex return - so they can be tested directly with plain dicts.
"""

import pytest

from services.search_service import (
    SearchService,
    _apa_from_last_names,
    _clean_doi,
    _clean_title,
    _date_parts_to_iso,
    _issue_label,
    _strip_jats,
    format_authors_apa,
    format_authors_apa_crossref,
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
