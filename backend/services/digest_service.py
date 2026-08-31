import logging
from datetime import datetime, timedelta, timezone
from html import escape
from typing import List
from urllib.parse import urlencode

from config import settings
from database import models
from database.database import engine
from services.download_service import DownloadService
from services.mail_service import MailService
from services.search_service import SearchService
from sqlmodel import Session, select

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

ARTICLES_PER_PROFILE = 25
MAX_DOWNLOAD_PAPERS_PER_PROFILE = 25


class DigestService:
    """Creates and sends the monthly paper digest for registered users."""

    def __init__(
        self,
        search_service: SearchService,
        mail_service: MailService,
        download_service: DownloadService,
    ):
        self.search_service = search_service
        self.mail_service = mail_service
        self.download_service = download_service

    def _date_range(self) -> tuple[str, str]:
        today = datetime.now(timezone.utc).date()
        one_month_ago = today - timedelta(days=30)
        return one_month_ago.isoformat(), today.isoformat()

    def _build_download_link(self, profile_name: str, articles: List[dict]) -> str | None:
        """Creates a long-lived, signed link to download all papers of a profile as a ZIP.

        Deliberately encodes only the short OpenAlex IDs (not the full URLs or titles) in the
        token, so the link stays short enough not to be truncated by mail clients.
        """
        clean_ids = [
            a["id"].split("/")[-1] for a in articles if a.get("id")
        ][:MAX_DOWNLOAD_PAPERS_PER_PROFILE]
        if not clean_ids:
            return None

        token = self.download_service.create_bulk_download_token(
            clean_ids, expire_days=settings.DIGEST_DOWNLOAD_LINK_EXPIRE_DAYS
        )
        query = urlencode({"token": token, "zip_name": profile_name})
        return f"{settings.BACKEND_URL}/api/digest/download?{query}"

    def _render_profile_section(
        self, profile_name: str, articles: List[dict], download_link: str | None
    ) -> str:
        if not articles:
            return (
                f"<h2 style='margin-top:32px;'>{escape(profile_name)}</h2>"
                f"<p style='color:#666;'>No new results in this period.</p>"
            )

        items = []
        for article in articles:
            title = escape(article.get("title") or "Untitled")
            author = escape(article.get("author") or "")
            journal = escape(article.get("journal_name") or "")
            date = escape(article.get("publication_date") or "")
            link = article.get("pdf_url") or article.get("pdf_landing_page") or article.get("doi") or "#"
            items.append(
                "<li style='margin-bottom:14px;'>"
                f"<a href='{escape(link)}' style='font-weight:600;text-decoration:none;color:#1a56db;'>{title}</a><br/>"
                f"<span style='color:#555;font-size:14px;'>{author} &middot; {journal} &middot; {date}</span>"
                "</li>"
            )

        download_note = (
            f"<p style='margin:8px 0 16px;'>"
            f"<a href='{escape(download_link)}' style='display:inline-block;padding:8px 14px;"
            f"background:#1a56db;color:#fff;border-radius:6px;text-decoration:none;font-size:14px;'>"
            f"Download all PDFs of this profile as ZIP</a>"
            f"<br/><span style='color:#999;font-size:12px;'>Link valid for {settings.DIGEST_DOWNLOAD_LINK_EXPIRE_DAYS} days.</span>"
            f"</p>"
            if download_link
            else ""
        )

        return (
            f"<h2 style='margin-top:32px;'>{escape(profile_name)}</h2>"
            f"{download_note}"
            f"<ul style='list-style:none;padding:0;'>{''.join(items)}</ul>"
        )

    async def _build_user_digest(self, session: Session, user: models.User) -> str | None:
        """Builds the HTML digest email for a user. Returns None if they have no profiles."""
        profiles = session.exec(
            select(models.Profile).where(
                models.Profile.user_id == user.id,
                models.Profile.email_notifications == True,  # noqa: E712
            )
        ).all()

        if not profiles:
            return None

        from_date, to_date = self._date_range()
        sections: List[str] = []

        for profile in profiles:
            journal_ids = [
                jid for jid, selected in (profile.row_selection or {}).items() if selected
            ]
            if not journal_ids:
                sections.append(self._render_profile_section(profile.profile_name, [], None))
                continue

            data = await self.search_service.search(
                journal_ids=journal_ids,
                keywords=profile.searchTerm or "",
                from_date=from_date,
                to_date=to_date,
                limit=ARTICLES_PER_PROFILE,
                page=1,
            )
            articles = data.get("results", [])
            download_link = self._build_download_link(profile.profile_name, articles)
            sections.append(
                self._render_profile_section(profile.profile_name, articles, download_link)
            )

        body = "".join(sections)
        return (
            "<div style='font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;'>"
            f"<h1 style='margin-bottom:4px;'>Your monthly PaperScout digest</h1>"
            f"<p style='color:#666;'>New papers from {from_date} to {to_date}, sorted by your search profiles.</p>"
            f"{body}"
            "</div>"
        )

    async def send_digest_to_user(self, session: Session, user: models.User) -> bool:
        html = await self._build_user_digest(session, user)
        if html is None:
            return False
        return await self.mail_service.send_email(
            to=user.email,
            subject="Your monthly PaperScout digest",
            html_body=html,
        )

    async def run_monthly_digest(self) -> None:
        """Generates and sends the digest to all registered users with at least one profile."""
        logging.info("Starting monthly paper digest send...")
        sent_count = 0
        with Session(engine) as session:
            users = session.exec(select(models.User)).all()
            for user in users:
                try:
                    if await self.send_digest_to_user(session, user):
                        sent_count += 1
                except Exception as e:
                    logging.error(f"Digest send to {user.email} failed: {e}")
        logging.info(f"Monthly digest send complete. {sent_count} email(s) sent.")
