"""Unit tests for the journal-specific external API handling.

The Springer and Scopus HTTP lookups are replaced by a stub, so no network access is needed.
"""

import asyncio

import httpx
import pytest

from services import external_api_service
from services.external_api_service import (
    _scopus_abstract,
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


class TestScopusAbstract:
    def test_strips_trailing_copyright(self):
        text = "Some text. © 2024 Elsevier Inc. All rights reserved."
        assert _scopus_abstract(text) == "Some text."

    @pytest.mark.parametrize(
        "text",
        [
            "© 2024 Elsevier Inc. All rights reserved. Some text.",
            "© 2023 Elsevier Ltd Some text.",
            "© 2023 The Author(s) Some text.",
        ],
    )
    def test_strips_leading_copyright(self, text):
        assert _scopus_abstract(text) == "Some text."

    def test_collapses_whitespace(self):
        assert _scopus_abstract("  Some\n  text  ") == "Some text"

    @pytest.mark.parametrize("value", [None, "", "© 2024 Elsevier Inc.", 42])
    def test_empty_returns_none(self, value):
        assert _scopus_abstract(value) is None


class TestFetchScopusAbstracts:
    def test_skipped_without_institutional_access(self, monkeypatch):
        monkeypatch.setenv("ELSEVIER_API_KEY", "key")
        monkeypatch.delenv("HAS_INSTITUTIONAL_ACCESS", raising=False)

        def fail(*args, **kwargs):
            raise AssertionError("no request expected")

        monkeypatch.setattr(external_api_service.httpx, "AsyncClient", fail)
        assert asyncio.run(external_api_service._fetch_scopus_abstracts(["a"])) == {}

    def test_skipped_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ELSEVIER_API_KEY", raising=False)
        monkeypatch.setenv("HAS_INSTITUTIONAL_ACCESS", "true")
        assert asyncio.run(external_api_service._fetch_scopus_abstracts(["a"])) == {}

    def test_batches_dois_and_parses_entries(self, monkeypatch):
        monkeypatch.setenv("ELSEVIER_API_KEY", "key")
        monkeypatch.setenv("HAS_INSTITUTIONAL_ACCESS", "true")
        queries = []

        def respond(request):
            queries.append(request.url.params["query"])
            entries = [
                {"prism:doi": "10.1/A", "dc:description": "Text A. © 2024 Elsevier Inc."},
                {"prism:doi": "10.1/b", "dc:description": None},
            ]
            if len(queries) > 1:
                entries = [{"error": "Result set was empty"}]
            return httpx.Response(200, json={"search-results": {"entry": entries}})

        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            external_api_service.httpx,
            "AsyncClient",
            lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
        )
        dois = [f"10.1/{i}" for i in range(30)]
        result = asyncio.run(external_api_service._fetch_scopus_abstracts(dois))

        assert len(queries) == 2
        assert queries[0].startswith('DOI("10.1/0") OR DOI("10.1/1")')
        assert queries[1].count("DOI(") == 5
        assert result == {"10.1/a": "Text A."}


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

    def test_scopus_abstracts_take_precedence(self, monkeypatch):
        requested = []

        async def fake_fetch(dois):
            requested.extend(dois)
            return {"a": "From Scopus A", "b": "From Scopus B"}

        monkeypatch.setattr(external_api_service, "_fetch_scopus_abstracts", fake_fetch)
        records = [
            {"id": "a", "abstract": "From Crossref"},
            {"id": "b", "abstract": None},
            {"id": "c", "abstract": "From OpenAlex"},
        ]
        asyncio.run(apply_external_apis(records, {"a": "scopus", "b": "scopus", "c": "scopus"}))

        assert requested == ["a", "b", "c"]
        assert [r["abstract"] for r in records] == [
            "From Scopus A",
            "From Scopus B",
            "From OpenAlex",
        ]
