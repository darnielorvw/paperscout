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
    """Erstellt und versendet den monatlichen Paper-Digest für registrierte Nutzer."""

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
        """Erzeugt einen langlebigen, signierten Link zum Download aller Paper eines Profils als ZIP.

        Kodiert bewusst nur die kurzen OpenAlex-IDs (nicht die vollen URLs oder Titel) in den
        Token, damit der Link kurz genug bleibt, um von Mail-Clients nicht abgeschnitten zu werden.
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
                f"<p style='color:#666;'>Keine neuen Treffer in diesem Zeitraum.</p>"
            )

        items = []
        for article in articles:
            title = escape(article.get("title") or "Ohne Titel")
            author = escape(article.get("author") or "")
            journal = escape(article.get("journal_name") or "")
            date = escape(article.get("publication_date") or "")
            link = article.get("pdf_landing_page") or article.get("pdf_url") or article.get("doi") or "#"
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
            f"Alle PDFs dieses Profils als ZIP herunterladen</a>"
            f"<br/><span style='color:#999;font-size:12px;'>Link gültig für {settings.DIGEST_DOWNLOAD_LINK_EXPIRE_DAYS} Tage.</span>"
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
        """Baut die HTML-Digest-Mail für einen Nutzer. Gibt None zurück, wenn er keine Profile hat."""
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
            f"<h1 style='margin-bottom:4px;'>Ihr monatlicher PaperScout-Digest</h1>"
            f"<p style='color:#666;'>Neue Paper vom {from_date} bis {to_date}, sortiert nach Ihren Suchprofilen.</p>"
            f"{body}"
            "</div>"
        )

    async def send_digest_to_user(self, session: Session, user: models.User) -> bool:
        html = await self._build_user_digest(session, user)
        if html is None:
            return False
        return await self.mail_service.send_email(
            to=user.email,
            subject="Ihr monatlicher PaperScout-Digest",
            html_body=html,
        )

    async def run_monthly_digest(self) -> None:
        """Erzeugt und verschickt den Digest an alle registrierten Nutzer mit mindestens einem Profil."""
        logging.info("Starte monatlichen Paper-Digest-Versand...")
        sent_count = 0
        with Session(engine) as session:
            users = session.exec(select(models.User)).all()
            for user in users:
                try:
                    if await self.send_digest_to_user(session, user):
                        sent_count += 1
                except Exception as e:
                    logging.error(f"Digest-Versand an {user.email} fehlgeschlagen: {e}")
        logging.info(f"Monatlicher Digest-Versand abgeschlossen. {sent_count} E-Mail(s) versendet.")
