"""Unit tests for DownloadService: filename sanitising and the download tokens."""

import jwt
import pytest
from fastapi import HTTPException

from config import settings
from services.download_service import DownloadService


@pytest.fixture
def svc():
    return DownloadService()


class TestSanitizeFilename:
    def test_keeps_plain_ascii(self, svc):
        assert svc.sanitize_filename("my_paper-01.pdf", "fallback") == "my_paper-01.pdf"

    def test_transliterates_accents_and_umlauts(self, svc):
        assert svc.sanitize_filename("Über Café Naïve", "fallback") == "Uber_Cafe_Naive"

    def test_replaces_path_separators_and_traversal(self, svc):
        assert svc.sanitize_filename("../../etc/passwd", "fallback") == "etc_passwd"
        assert "/" not in svc.sanitize_filename("a/b/c", "fallback")

    def test_collapses_runs_of_special_chars_to_one_underscore(self, svc):
        assert svc.sanitize_filename("a   ***   b", "fallback") == "a_b"

    @pytest.mark.parametrize("title", ["", "   ", "***", None])
    def test_falls_back_when_nothing_usable_remains(self, svc, title):
        assert svc.sanitize_filename(title, "fallback") == "fallback"


class TestBulkDownloadToken:
    def test_roundtrip(self, svc):
        token = svc.create_bulk_download_token(["10.1/a", "10.1/b"], expire_days=1)
        assert svc.decode_bulk_download_token(token)["work_ids"] == ["10.1/a", "10.1/b"]

    def test_expired_token_is_rejected(self, svc):
        token = svc.create_bulk_download_token(["10.1/a"], expire_days=-1)
        with pytest.raises(HTTPException) as exc:
            svc.decode_bulk_download_token(token)
        assert exc.value.status_code == 401

    def test_token_signed_with_a_different_secret_is_rejected(self, svc):
        forged = jwt.encode(
            {"work_ids": ["x"]},
            "a-different-secret-of-at-least-32-bytes",
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            svc.decode_bulk_download_token(forged)
        assert exc.value.status_code == 401

    def test_token_without_work_ids_is_rejected(self, svc):
        empty = jwt.encode({"work_ids": []}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            svc.decode_bulk_download_token(empty)
        assert exc.value.status_code == 400


class TestDownloadToken:
    def test_roundtrip(self, svc):
        token = svc.create_download_token("/tmp/x.pdf", "x.pdf")
        payload = svc.decode_download_token(token)
        assert payload["filepath"] == "/tmp/x.pdf"
        assert payload["filename"] == "x.pdf"

    def test_token_missing_fields_is_rejected(self, svc):
        bad = jwt.encode(
            {"filepath": "/tmp/x"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
        )
        with pytest.raises(HTTPException) as exc:
            svc.decode_download_token(bad)
        assert exc.value.status_code == 400

    def test_garbage_token_is_rejected(self, svc):
        with pytest.raises(HTTPException) as exc:
            svc.decode_download_token("not-a-jwt")
        assert exc.value.status_code == 401
