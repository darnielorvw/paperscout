import logging
from datetime import datetime, timedelta, timezone
from html import escape
from typing import List
from urllib.parse import urlencode

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from config import settings
from database import models
from database.database import engine
from services.mail_service import MailService
from services.search_service import SearchService, openurl_resolver_for

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ARTICLES_PER_PROFILE = 25
# Commentaries, editorials etc. (`low_value`) are left out of the digest, so more
# results are fetched to still fill the profile's section.
_FETCH_PER_PROFILE = 2 * ARTICLES_PER_PROFILE


class DigestService:
    """Creates and sends the monthly paper digest for registered users."""

    def __init__(
        self,
        search_service: SearchService,
        mail_service: MailService,
    ):
        self.search_service = search_service
        self.mail_service = mail_service

    def _date_range(self) -> tuple[str, str]:
        """Returns the full previous calendar month as (from_date, to_date)."""
        today = datetime.now(timezone.utc).date()
        last_day_prev_month = today.replace(day=1) - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        return first_day_prev_month.isoformat(), last_day_prev_month.isoformat()

    def _build_frontend_link(
        self,
        journal_ids: List[str],
        keywords: str,
        from_date: str,
        to_date: str,
        semantic_query: str = "",
    ) -> str:
        """Builds a link to the results page in the frontend for the full profile.

        The digest email only carries the first ARTICLES_PER_PROFILE papers; this link
        lets the user browse the complete result set and pick papers themselves.
        """
        params: List[tuple[str, str]] = [("journal_ids", jid) for jid in journal_ids]
        params.append(("keywords", keywords or ""))
        if semantic_query:
            params.append(("semantic_query", semantic_query))
        params.append(("from_date", from_date))
        params.append(("to_date", to_date))
        return f"{settings.FRONTEND_URL}/results?{urlencode(params)}"

    def _render_profile_section(
        self,
        profile_name: str,
        articles: List[dict],
        frontend_link: str | None = None,
    ) -> str:
        browse_note = (
            f"<p style='margin:8px 0 16px;'>"
            f"<a href='{escape(frontend_link)}' style='display:inline-block;padding:8px 14px;"
            f"border:1px solid #1a56db;color:#1a56db;border-radius:6px;text-decoration:none;font-size:14px;'>"
            f"Browse all results &amp; select papers yourself</a>"
            f"</p>"
            if frontend_link
            else ""
        )

        if not articles:
            return (
                f"<h2 style='margin-top:32px;font-size:20px;'>Profile: {escape(profile_name)}</h2>"
                f"{browse_note}"
                f"<p style='color:#666;font-size:14px;'>No new results in this period.</p>"
            )

        items = []
        for article in articles:
            title = escape(article.get("title") or "Untitled")
            author = escape(article.get("author") or "")
            journal = escape(article.get("journal_name") or "")
            date = escape(article.get("publication_date") or "")
            # The library resolver leads to the full text via the institution's access.
            library_url = article.get("library_url")
            doi_url = article.get("doi")
            page_url = article.get("url")
            link = library_url or doi_url or page_url or "#"
            link_parts = []
            if doi_url:
                doi = doi_url.removeprefix("https://doi.org/")
                link_parts.append(
                    f"DOI: <a href='{escape(doi_url)}' style='color:#1a56db;'>{escape(doi)}</a>"
                )
            elif page_url:
                link_parts.append(
                    f"<a href='{escape(page_url)}' style='color:#1a56db;'>Article page</a>"
                )
            if library_url:
                link_parts.append(
                    f"<a href='{escape(library_url)}' style='color:#1a56db;'>Full text via your library</a>"
                )
            links = (
                f"<br/><span style='font-size:13px;'>{' &middot; '.join(link_parts)}</span>"
                if link_parts
                else ""
            )
            items.append(
                "<li style='margin-bottom:14px;'>"
                f"<a href='{escape(link)}' style='font-size:16px;font-weight:600;text-decoration:none;color:#1a56db;'>{title}</a><br/>"
                f"<span style='color:#555;font-size:13px;'>{author} &middot; {journal} &middot; {date}</span>"
                f"{links}"
                "</li>"
            )

        return (
            f"<h2 style='margin-top:32px;font-size:20px;'>Profile: {escape(profile_name)}</h2>"
            f"{browse_note}"
            f"<ul style='list-style:none;padding:0;'>{''.join(items)}</ul>"
        )

    async def _build_user_digest(self, session: Session, user: models.User) -> str | None:
        """Builds the HTML digest email for a user. Returns None if they have no profiles."""
        profiles = session.exec(
            select(models.Profile)
            .where(
                models.Profile.user_id == user.id,
                models.Profile.email_notifications == True,  # noqa: E712
            )
            .options(selectinload(models.Profile.journals))
        ).all()

        if not profiles:
            return None

        from_date, to_date = self._date_range()
        sections: List[str] = []

        for profile in profiles:
            journal_ids = [journal.id for journal in profile.journals]
            issns = [journal.issn for journal in profile.journals if journal.issn]
            external_apis = {
                journal.issn: journal.external_api
                for journal in profile.journals
                if journal.issn and journal.external_api
            }
            if not journal_ids:
                sections.append(self._render_profile_section(profile.profile_name, []))
                continue

            # The frontend link keeps the OpenAlex ids the journal picker knows.
            # Only the query of the profile's search mode is stored.
            semantic_query = profile.semantic_query if profile.search_mode == "semantic" else ""
            frontend_link = self._build_frontend_link(
                journal_ids, profile.searchTerm or "", from_date, to_date, semantic_query
            )

            data = await self.search_service.search(
                issns=issns,
                external_apis=external_apis,
                keywords=profile.searchTerm or "",
                semantic_query=semantic_query,
                source_ids={j.issn: j.id for j in profile.journals if j.issn},
                from_date=from_date,
                to_date=to_date,
                limit=_FETCH_PER_PROFILE,
                page=1,
                resolver=openurl_resolver_for(user.email),
                session=session,
            )
            articles = [a for a in data.get("results", []) if not a.get("low_value")]
            articles = articles[:ARTICLES_PER_PROFILE]
            sections.append(
                self._render_profile_section(profile.profile_name, articles, frontend_link)
            )

        body = "".join(sections)
        return (
            "<div style='font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;'>"
            f"<h1 style='margin-bottom:4px;font-size:24px;'>Your monthly PaperScout digest</h1>"
            f"<p style='color:#666;font-size:14px;'>New papers from {from_date} to {to_date}, sorted by your search profiles. "
            f"Each profile shows up to {ARTICLES_PER_PROFILE} papers here – use the "
            f"“Browse all results” link to see the full list and pick papers yourself.</p>"
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

    async def run_monthly_digest(self) -> int:
        """Generates and sends the digest to all registered users with at least one profile.

        Returns the number of emails sent.
        """
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
        return sent_count
