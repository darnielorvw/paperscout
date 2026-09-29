"""Unit tests for auth_service: access tokens, email-verification tokens and the
token-decoding guards in get_current_user / require_admin.

The success path of get_current_user (DB lookup) is covered by the API tests;
here we only exercise the token handling, which needs no database.
"""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from config import settings
from services import auth_service


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestAccessToken:
    def test_roundtrip_contains_subject_and_expiry(self):
        token = auth_service.create_access_token({"sub": "a@b.de"}, timedelta(minutes=5))
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "a@b.de"
        assert "exp" in payload

    def test_default_expiry_is_applied_when_none_given(self):
        token = auth_service.create_access_token({"sub": "a@b.de"})
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert "exp" in payload


class TestGetCurrentUser:
    def test_missing_credentials_returns_401(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth_service.get_current_user(session=None, credentials=None))
        assert exc.value.status_code == 401

    def test_expired_token_returns_401(self):
        token = auth_service.create_access_token({"sub": "a@b.de"}, timedelta(minutes=-1))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth_service.get_current_user(session=None, credentials=_creds(token)))
        assert exc.value.status_code == 401

    def test_token_with_wrong_secret_returns_401(self):
        token = jwt.encode(
            {"sub": "a@b.de"},
            "a-different-secret-of-at-least-32-bytes",
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth_service.get_current_user(session=None, credentials=_creds(token)))
        assert exc.value.status_code == 401

    def test_token_without_sub_returns_401(self):
        token = jwt.encode({"foo": "bar"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth_service.get_current_user(session=None, credentials=_creds(token)))
        assert exc.value.status_code == 401


class TestRequireAdmin:
    def test_admin_passes_through(self):
        admin = SimpleNamespace(is_admin=True)
        assert asyncio.run(auth_service.require_admin(user=admin)) is admin

    def test_non_admin_gets_403(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth_service.require_admin(user=SimpleNamespace(is_admin=False)))
        assert exc.value.status_code == 403


class TestEmailVerificationToken:
    def _token(self, **overrides):
        data = {"email": "a@b.de", "name": "Ada", "hashed_password": "hash", "expire_hours": 24}
        data.update(overrides)
        return auth_service.create_email_verification_token(**data)

    def test_roundtrip_returns_the_registration_payload(self):
        payload = auth_service.decode_email_verification_token(self._token())
        assert payload["email"] == "a@b.de"
        assert payload["name"] == "Ada"
        assert payload["hashed_password"] == "hash"
        assert payload["purpose"] == "email_verification"

    def test_expired_token_returns_401(self):
        with pytest.raises(HTTPException) as exc:
            auth_service.decode_email_verification_token(self._token(expire_hours=-1))
        assert exc.value.status_code == 401

    def test_wrong_purpose_returns_400(self):
        token = jwt.encode(
            {"purpose": "something_else", "email": "a@b.de"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            auth_service.decode_email_verification_token(token)
        assert exc.value.status_code == 400

    def test_missing_email_returns_400(self):
        token = jwt.encode(
            {"purpose": "email_verification"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            auth_service.decode_email_verification_token(token)
        assert exc.value.status_code == 400

    def test_garbage_token_returns_401(self):
        with pytest.raises(HTTPException) as exc:
            auth_service.decode_email_verification_token("not-a-jwt")
        assert exc.value.status_code == 401
