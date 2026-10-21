import logging
from datetime import datetime, timezone
from html import escape

import httpx
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from config import settings
from database import models
from database.database import engine
from services.mail_service import MailService

logger = logging.getLogger(__name__)

# --- Quota alerts for external APIs ------------------------------------------
# Every request to a rate-limited API passes its response to `check_quota`.
# Once the remaining quota drops below API_QUOTA_WARN_PERCENT, or the API
# refuses requests (429/403), all admins get a mail - at most once per API,
# kind and day, which the `ApiAlert` table keeps track of across instances.

# Response headers with the remaining and the total quota. A missing total
# header means the total comes from settings (see _quota_limit).
_QUOTA_HEADERS = {
    "openalex": ("x-ratelimit-remaining-usd", None),
    "scopus": ("x-ratelimit-remaining", "x-ratelimit-limit"),
    "springer": (None, None),
}

_API_NAMES = {
    "openalex": "OpenAlex",
    "scopus": "Scopus (Elsevier)",
    "springer": "Springer Nature",
}

_mail_service = MailService()

# Alerts this instance already handled, so it doesn't hit the database on
# every request once a quota is low.
_handled: set[tuple[str, str, str]] = set()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _quota_limit(api: str, headers: httpx.Headers) -> str | float | None:
    if api == "openalex":
        return settings.OPENALEX_DAILY_BUDGET_USD
    limit_header = _QUOTA_HEADERS[api][1]
    return headers.get(limit_header) if limit_header else None


def remaining_percent(api: str, headers: httpx.Headers) -> float | None:
    """The remaining quota in percent, or None if the response doesn't tell."""
    remaining_header = _QUOTA_HEADERS[api][0]
    if not remaining_header:
        return None
    try:
        remaining = float(headers.get(remaining_header))
        limit = float(_quota_limit(api, headers))
    except (TypeError, ValueError):
        return None
    return remaining / limit * 100 if limit > 0 else None


async def check_quota(api: str, response: httpx.Response) -> None:
    """Sends the admins an alert if `response` shows that `api`'s quota is low or
    used up. Never raises, so a failing alert can't break a search."""
    try:
        if response.status_code in (403, 429):
            await _alert(
                api,
                "exhausted",
                f"{_API_NAMES[api]} refused a request with HTTP {response.status_code}. "
                "The quota is most likely used up (HTTP 403 can also mean the API key "
                "was rejected). Until it resets, results from this API are missing.",
            )
            return

        percent = remaining_percent(api, response.headers)
        if percent is not None and percent < settings.API_QUOTA_WARN_PERCENT:
            await _alert(
                api,
                "low",
                f"Only {percent:.1f}% of the {_API_NAMES[api]} quota is left "
                f"(alert threshold: {settings.API_QUOTA_WARN_PERCENT:g}%).",
            )
    except Exception as e:
        logger.error(f"Quota check for {api} failed: {e}")


async def _alert(api: str, kind: str, message: str) -> None:
    day = _today()
    if (api, kind, day) in _handled:
        return
    _handled.add((api, kind, day))

    with Session(engine) as session:
        # The unique constraint decides which request sends the alert, even
        # with several instances running at once.
        alert = models.ApiAlert(api=api, kind=kind, day=day)
        session.add(alert)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return

        admin_emails = session.exec(
            select(models.User.email).where(models.User.is_admin == True)  # noqa: E712
        ).all()
        if not admin_emails:
            logger.warning(f"Quota alert for {api} ({kind}) not sent: no admin users.")
            return

        subject = (
            f"PaperScout: {_API_NAMES[api]} quota used up"
            if kind == "exhausted"
            else f"PaperScout: {_API_NAMES[api]} quota running low"
        )
        html = (
            "<div style='font-family:Arial,Helvetica,sans-serif;max-width:640px;'>"
            f"<h1 style='font-size:20px;'>{escape(subject)}</h1>"
            f"<p style='font-size:14px;'>{escape(message)}</p>"
            f"<p style='color:#666;font-size:13px;'>This alert is sent at most once per day. "
            f"Date (UTC): {day}</p>"
            "</div>"
        )
        sent = False
        for email in admin_emails:
            sent = await _mail_service.send_email(to=email, subject=subject, html_body=html) or sent

        # Nobody got the mail (e.g. SMTP down): another instance, or this one
        # after a restart, may try again.
        if not sent:
            session.delete(alert)
            session.commit()
