"""Unit tests for the external API quota alerts.

The database is an in-memory SQLite engine and the mail service a stub, so no
network access is needed.
"""

import asyncio

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database import models
from services import quota_alert_service
from services.quota_alert_service import check_quota, remaining_percent


class TestRemainingPercent:
    def test_openalex_uses_configured_budget(self, monkeypatch):
        monkeypatch.setattr(quota_alert_service.settings, "OPENALEX_DAILY_BUDGET_USD", 2.0)
        headers = httpx.Headers({"x-ratelimit-remaining-usd": "0.5"})
        assert remaining_percent("openalex", headers) == 25.0

    def test_scopus_uses_limit_header(self):
        headers = httpx.Headers({"x-ratelimit-remaining": "100", "x-ratelimit-limit": "20000"})
        assert remaining_percent("scopus", headers) == 0.5

    @pytest.mark.parametrize(
        "api, headers",
        [
            ("openalex", {}),
            ("scopus", {"x-ratelimit-remaining": "100"}),
            ("scopus", {"x-ratelimit-remaining": "abc", "x-ratelimit-limit": "100"}),
            ("scopus", {"x-ratelimit-remaining": "0", "x-ratelimit-limit": "0"}),
            ("springer", {"x-ratelimit-remaining": "1", "x-ratelimit-limit": "100"}),
        ],
    )
    def test_unknown_returns_none(self, api, headers):
        assert remaining_percent(api, httpx.Headers(headers)) is None


@pytest.fixture
def alert_env(monkeypatch):
    """In-memory database with one admin, a stub mail service and a fresh cache."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            models.User(
                email="admin@example.com",
                name="Admin",
                hashed_password="x",
                institution="x",
                is_admin=True,
            )
        )
        session.commit()

    sent = []

    class StubMail:
        result = True

        async def send_email(self, to, subject, html_body):
            sent.append((to, subject))
            return self.result

    mail = StubMail()
    monkeypatch.setattr(quota_alert_service, "engine", engine)
    monkeypatch.setattr(quota_alert_service, "_mail_service", mail)
    monkeypatch.setattr(quota_alert_service, "_handled", set())
    monkeypatch.setattr(quota_alert_service.settings, "API_QUOTA_WARN_PERCENT", 10.0)
    return engine, mail, sent


def _alerts(engine):
    with Session(engine) as session:
        return [(a.api, a.kind) for a in session.exec(select(models.ApiAlert)).all()]


class TestCheckQuota:
    def test_exhausted_sends_one_mail_per_day(self, alert_env):
        engine, _, sent = alert_env
        response = httpx.Response(429)
        asyncio.run(check_quota("springer", response))
        asyncio.run(check_quota("springer", response))

        assert sent == [("admin@example.com", "PaperScout: Springer Nature quota used up")]
        assert _alerts(engine) == [("springer", "exhausted")]

    def test_other_instance_does_not_send_again(self, alert_env, monkeypatch):
        engine, _, sent = alert_env
        asyncio.run(check_quota("springer", httpx.Response(429)))
        # A fresh instance only knows about the alert from the database.
        monkeypatch.setattr(quota_alert_service, "_handled", set())
        asyncio.run(check_quota("springer", httpx.Response(429)))

        assert len(sent) == 1

    def test_low_quota_sends_warning(self, alert_env):
        engine, _, sent = alert_env
        headers = {"x-ratelimit-remaining": "50", "x-ratelimit-limit": "1000"}
        asyncio.run(check_quota("scopus", httpx.Response(200, headers=headers)))

        assert sent == [("admin@example.com", "PaperScout: Scopus (Elsevier) quota running low")]
        assert _alerts(engine) == [("scopus", "low")]

    def test_enough_quota_sends_nothing(self, alert_env):
        engine, _, sent = alert_env
        headers = {"x-ratelimit-remaining": "500", "x-ratelimit-limit": "1000"}
        asyncio.run(check_quota("scopus", httpx.Response(200, headers=headers)))

        assert sent == []
        assert _alerts(engine) == []

    def test_failed_mail_frees_alert_for_retry(self, alert_env):
        engine, mail, sent = alert_env
        mail.result = False
        asyncio.run(check_quota("openalex", httpx.Response(429)))

        assert len(sent) == 1
        assert _alerts(engine) == []

    def test_errors_never_raise(self, alert_env, monkeypatch):
        async def broken(*args):
            raise RuntimeError("database down")

        monkeypatch.setattr(quota_alert_service, "_alert", broken)
        asyncio.run(check_quota("openalex", httpx.Response(429)))
