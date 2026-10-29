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

    def test_springer_abstracts_take_precedence(self, monkeypatch):
        requested = []

        async def fake_fetch(dois):
            requested.extend(dois)
            return {"a": "From Springer A", "b": "From Springer B"}

        monkeypatch.setattr(external_api_service, "_fetch_springer_abstracts", fake_fetch)
        records = [
            {"id": "a", "abstract": "From Crossref"},
            {"id": "b", "abstract": None},
            {"id": "c", "abstract": "From OpenAlex"},
        ]
        asyncio.run(
            apply_external_apis(records, {"a": "springer", "b": "springer", "c": "springer"})
        )

        assert requested == ["a", "b", "c"]
        assert [r["abstract"] for r in records] == [
            "From Springer A",
            "From Springer B",
            "From OpenAlex",
        ]
