"""Unit tests for masking API keys in log output."""

import logging

import pytest

from lib.log_redaction import RedactSecretsFilter, redact


class TestRedact:
    @pytest.mark.parametrize(
        "text, expected",
        [
            (
                "GET https://api.openalex.org/works?api_key=secret123&filter=x",
                "GET https://api.openalex.org/works?api_key=***&filter=x",
            ),
            (
                'GET https://api.springernature.com/meta/v2/json?q=x&api_key=secret "HTTP/1.1 200"',
                'GET https://api.springernature.com/meta/v2/json?q=x&api_key=*** "HTTP/1.1 200"',
            ),
            ("https://example.org/?apikey=secret", "https://example.org/?apikey=***"),
            ("https://example.org/?API_KEY=secret", "https://example.org/?API_KEY=***"),
        ],
    )
    def test_masks_key(self, text, expected):
        assert redact(text) == expected

    def test_leaves_other_text_alone(self):
        text = "GET https://api.crossref.org/works?filter=issn:1234"
        assert redact(text) == text


def test_filter_masks_formatted_record():
    # httpx logs the URL as an argument, not in the format string.
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        "HTTP Request: %s %s",
        ("GET", "https://api.openalex.org/works?api_key=secret123"),
        None,
    )
    assert RedactSecretsFilter().filter(record) is True
    assert record.getMessage() == "HTTP Request: GET https://api.openalex.org/works?api_key=***"
