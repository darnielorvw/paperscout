"""Unit tests for the pure helpers defined in main.py (no DB, no request)."""

from main import _journal_values, _profile_queries
from schemas import ProfileSettings


class TestJournalValues:
    def _source(self, **overrides):
        base = {
            "id": "https://openalex.org/S12345",
            "issn_l": "1234-5678",
            "display_name": "Journal of Testing",
            "host_organization_name": "Test Publisher",
            "homepage_url": "https://example.org",
        }
        base.update(overrides)
        return base

    def test_maps_a_full_openalex_source(self):
        assert _journal_values(self._source()) == {
            "id": "S12345",
            "name": "Journal of Testing",
            "issn": "1234-5678",
            "publisher": "Test Publisher",
            "homepage": "https://example.org",
        }

    def test_extracts_bare_id_from_the_openalex_url(self):
        assert _journal_values(self._source())["id"] == "S12345"

    def test_source_without_issn_is_unusable(self):
        assert _journal_values(self._source(issn_l=None)) is None
        assert _journal_values(self._source(issn_l="")) is None

    def test_source_without_id_is_unusable(self):
        assert _journal_values(self._source(id="")) is None

    def test_missing_publisher_falls_back_to_unknown(self):
        assert _journal_values(self._source(host_organization_name=None))["publisher"] == "Unknown"

    def test_missing_homepage_falls_back_to_empty_string(self):
        assert _journal_values(self._source(homepage_url=None))["homepage"] == ""


class TestProfileQueries:
    def test_keyword_profile_drops_the_semantic_query(self):
        settings = ProfileSettings(searchTerm="robots", semanticQuery="trust in robots")
        assert _profile_queries(settings) == {
            "searchTerm": "robots",
            "semantic_query": "",
            "search_mode": "keywords",
        }

    def test_semantic_profile_drops_the_search_term(self):
        settings = ProfileSettings(
            searchTerm="robots", semanticQuery="trust in robots", searchMode="semantic"
        )
        assert _profile_queries(settings) == {
            "searchTerm": "",
            "semantic_query": "trust in robots",
            "search_mode": "semantic",
        }
