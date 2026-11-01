"""Unit tests for the journal-specific external API handling.

The Springer HTTP lookups are replaced by a stub, so no network access is needed.
"""

import asyncio

import pytest

from services import external_api_service
from services.external_api_service import (
    _springer_abstract,
    apply_external_apis,
)


class TestSpringerAbstract:
    def test_plain_string(self):
        assert _springer_abstract("Some text") == "Some text"

    def test_structured_object(self):
        assert _springer_abstract({"h1": "Abstract", "p": "Some text"}) == "Some text"

    def test_structured_object_with_paragraph_list(self):
        assert _springer_abstract({"h1": "Abstract", "p": ["One.", "Two."]}) == "One. Two."

    def test_strips_markup(self):
        assert _springer_abstract("<p>Some <i>text</i></p>") == "Some text"

    @pytest.mark.parametrize("value", [None, "", {}, {"h1": "Abstract"}])
    def test_empty_returns_none(self, value):
        assert _springer_abstract(value) is None


class TestApplyExternalApis:
    def test_passes_only_flagged_records_to_their_handler(self, monkeypatch):
        seen = []

        async def handler(records):
            seen.extend(r["id"] for r in records)

        monkeypatch.setitem(external_api_service.HANDLERS, "dummy", handler)
        records = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        asyncio.run(apply_external_apis(records, {"a": "dummy", "c": "unknown-api"}))
        assert seen == ["a"]

    def test_springer_only_asked_for_open_access_papers_without_abstract(self, monkeypatch):
        requested = []

        async def fake_fetch(dois):
            requested.extend(dois)
            return {doi: f"From Springer {doi}" for doi in dois if doi != "d"}

        monkeypatch.setattr(external_api_service, "_fetch_springer_abstracts", fake_fetch)
        records = [
            {"id": "a", "abstract": None, "open_access": {"url": "x"}},
            {"id": "b", "abstract": "From OpenAlex", "open_access": {"url": "x"}},
            {"id": "c", "abstract": None, "open_access": None},
            {"id": "d", "abstract": None, "open_access": {"url": "x"}},
            {"id": "e", "abstract": None},
        ]
        apis = {r["id"]: "springer" for r in records}
        asyncio.run(apply_external_apis(records, apis))

        assert requested == ["a", "d"]
        assert [r["abstract"] for r in records] == [
            "From Springer a",
            "From OpenAlex",
            None,
            None,
            None,
        ]
