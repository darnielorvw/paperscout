import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete as sql_delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, SQLModel, select

from config import settings
from database import models
from database.database import engine, get_session
from lib import log_redaction
from schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    JournalImportByName,
    PaperPdfCreate,
    PaperPdfUploadToken,
    ProfileCreate,
    ProfileNotificationsUpdate,
    ProfileSettings,
    SavedArticlesCreate,
    SavedArticleUpdate,
    UserCreate,
    UserPublic,
)
from services import auth_service, blob_service, user_service
from services.digest_service import DigestService
from services.mail_service import MailService
from services.search_service import SearchService, openurl_resolver_for
from services.site_import_service import IMPORTERS

scheduler = AsyncIOScheduler()

JOURNALS_SEED_PATH = Path(__file__).resolve().parent / "database" / "journals_seed.json"

# OpenAlex and Springer take the API key as a query parameter, which httpx
# would otherwise write to the log with every request URL.
log_redaction.install()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)

    with engine.connect() as conn:
        # A fresh database (e.g. on another machine) gets the journal list from
        # the versioned seed file. Only an empty table is filled, so journals
        # added or removed later aren't overwritten on every start.
        if conn.exec_driver_sql("SELECT COUNT(*) FROM journals").scalar() == 0:
            journals = json.loads(JOURNALS_SEED_PATH.read_text(encoding="utf-8"))
            for journal in journals:
                conn.exec_driver_sql(
                    "INSERT INTO journals (id, name, issn, publisher, homepage, external_api) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        journal["id"],
                        journal["name"],
                        journal["issn"],
                        journal["publisher"],
                        journal["homepage"],
                        journal["external_api"],
                    ),
                )
            conn.commit()
            print(f"🌱 Seeded {len(journals)} journals.", flush=True)

        existing_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profile)")}
        if "email_notifications" not in existing_columns:
            conn.exec_driver_sql(
                "ALTER TABLE profile ADD COLUMN email_notifications BOOLEAN DEFAULT 1"
            )
            conn.commit()

        existing_user_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(user)")}
        if "is_admin" not in existing_user_columns:
            conn.exec_driver_sql("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0")
            conn.commit()

        existing_journal_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(journals)")
        }
        if "external_api" not in existing_journal_columns:
            conn.exec_driver_sql("ALTER TABLE journals ADD COLUMN external_api VARCHAR")
            # Springer journals whose abstracts Crossref/OpenAlex deliver unreliably:
            # Nature, Motivation and Emotion, International Journal of Social Robotics.
            conn.exec_driver_sql(
                "UPDATE journals SET external_api = 'springer' "
                "WHERE issn IN ('0028-0836', '0146-7239', '1875-4791')"
            )
            conn.commit()

        # Scopus is no longer used; its journals go back to Crossref/OpenAlex only.
        conn.exec_driver_sql(
            "UPDATE journals SET external_api = NULL WHERE external_api = 'scopus'"
        )
        conn.commit()

        # Reading list entries no longer have a note (it was NOT NULL without a
        # default, so a leftover column would make every insert fail) nor a
        # publisher link, which was always the DOI link.
        saved_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(savedarticle)")}
        for column in ("note", "pdf_landing_page"):
            if column in saved_columns:
                conn.exec_driver_sql(f"ALTER TABLE savedarticle DROP COLUMN {column}")
                conn.commit()

        # Papers without a DOI link their page at the publisher instead.
        if "url" not in saved_columns:
            conn.exec_driver_sql("ALTER TABLE savedarticle ADD COLUMN url VARCHAR")
            conn.commit()

        # Papers imported from a journal website may have a DOI.
        site_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sitearticle)")}
        if "doi" not in site_columns:
            conn.exec_driver_sql("ALTER TABLE sitearticle ADD COLUMN doi VARCHAR")
            conn.commit()

        # The International Journal of Coaching Psychology is on neither Crossref
        # nor OpenAlex; its papers come from its website (see site_import_service).
        conn.exec_driver_sql(
            "INSERT OR IGNORE INTO journals (id, name, issn, publisher, homepage, external_api) "
            "VALUES ('ijcp', 'International Journal of Coaching Psychology', '2634-7946', "
            "'National Wellbeing Service', 'https://ijcp.nationalwellbeingservice.com/', NULL)"
        )
        conn.commit()

        # Profiles no longer store a date range - drop the now-unused columns.
        existing_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profile)")}
        for column in ("start_date", "end_date"):
            if column in existing_columns:
                conn.exec_driver_sql(f"ALTER TABLE profile DROP COLUMN {column}")
                conn.commit()

        # Journals used to be stored as a JSON `row_selection` map on the profile
        # and de-duplicated via a globally unique `settings_hash`. They are now
        # normalised into the `profilejournallink` join table, and profile names
        # are unique per user instead of globally. Migrate legacy profile rows.
        legacy_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profile)")}
        if "row_selection" in legacy_columns or "settings_hash" in legacy_columns:
            if "row_selection" in legacy_columns:
                valid_ids = {row[0] for row in conn.exec_driver_sql("SELECT id FROM journals")}
                for profile_id, raw in conn.exec_driver_sql(
                    "SELECT id, row_selection FROM profile"
                ).fetchall():
                    try:
                        selection = json.loads(raw) if raw else {}
                    except (TypeError, ValueError):
                        selection = {}
                    for journal_id, selected in selection.items():
                        if selected and journal_id in valid_ids:
                            conn.exec_driver_sql(
                                "INSERT OR IGNORE INTO profilejournallink "
                                "(profile_id, journal_id) VALUES (?, ?)",
                                (profile_id, journal_id),
                            )

            # Rebuild `profile` without the legacy columns and with a per-user
            # unique name constraint. Row ids are preserved, so the freshly
            # backfilled join rows stay valid.
            conn.exec_driver_sql(
                """
                CREATE TABLE profile_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    profile_name VARCHAR NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES user (id),
                    "searchTerm" VARCHAR NOT NULL,
                    email_notifications BOOLEAN DEFAULT 1,
                    CONSTRAINT uq_profile_user_name UNIQUE (user_id, profile_name)
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO profile_new
                    (id, profile_name, user_id, "searchTerm", email_notifications)
                SELECT id, profile_name, user_id, "searchTerm",
                       COALESCE(email_notifications, 1)
                FROM profile
                """
            )
            conn.exec_driver_sql("DROP TABLE profile")
            conn.exec_driver_sql("ALTER TABLE profile_new RENAME TO profile")
            conn.commit()

        # Profiles can run a semantic search instead of the keyword search. After
        # the rebuild above, which would drop the columns again.
        profile_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profile)")}
        if "semantic_query" not in profile_columns:
            conn.exec_driver_sql(
                "ALTER TABLE profile ADD COLUMN semantic_query VARCHAR NOT NULL DEFAULT ''"
            )
            conn.commit()
        if "search_mode" not in profile_columns:
            conn.exec_driver_sql(
                "ALTER TABLE profile ADD COLUMN search_mode VARCHAR NOT NULL DEFAULT 'keywords'"
            )
            conn.commit()

    print("🚀 Database has been checked and is ready!", flush=True)

    scheduler.add_job(
        digest_service.run_monthly_digest,
        CronTrigger.from_crontab(settings.DIGEST_CRON),
        id="monthly_paper_digest",
        replace_existing=True,
    )
    scheduler.start()
    print(f"📅 Monthly digest send scheduled ({settings.DIGEST_CRON}).", flush=True)

    yield  # The FastAPI app runs here
    scheduler.shutdown()

    # ---- ON APP SHUTDOWN ----
    print("🛑 Server is shutting down...", flush=True)


app = FastAPI(title="PaperScout API", lifespan=lifespan, version="1.0")

# CORS mapping: allows your React frontend (Vite usually runs on port 5173) to access the API
_cors_origins = sorted({settings.FRONTEND_URL})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

search_service = SearchService()
mail_service = MailService()
digest_service = DigestService(search_service, mail_service)

ACCESS_TOKEN_EXPIRE_MINUTES = 1440
ALLOWED_EMAIL_DETAIL = (
    "Only email addresses of the University of Münster (@uni-muenster.de) "
    "or FH Südwestfalen (@fh-swf.de) can be used."
)


@app.post("/api/register", status_code=202)
async def register_user(user: UserCreate, session: Session = Depends(get_session)):
    """Starts registration: sends a confirmation link by email.

    The account is only created once the link is clicked (see /api/verify-email).
    This prevents bots from flooding the DB with an unlimited number of fake registrations.
    """
    if not user_service.is_allowed_email(user.email):
        raise HTTPException(status_code=400, detail=ALLOWED_EMAIL_DETAIL)

    if auth_service.get_user_by_email(session, user.email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    hashed_password = user_service.get_password_hash(user.password)
    token = auth_service.create_email_verification_token(
        email=user.email,
        name=user.name,
        hashed_password=hashed_password,
        expire_hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS,
    )
    verify_link = f"{settings.BACKEND_URL}/api/verify-email?token={token}"
    html_body = (
        "<div style='font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;'>"
        "<h1 style='margin-bottom:4px;'>Welcome to PaperScout</h1>"
        "<p style='color:#666;'>Please confirm your email address to complete your registration.</p>"
        f"<p><a href='{verify_link}' style='display:inline-block;padding:8px 14px;"
        "background:#1a56db;color:#fff;border-radius:6px;text-decoration:none;'>"
        "Confirm email address</a></p>"
        f"<p style='color:#999;font-size:12px;'>This link is valid for {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} hours.</p>"
        "</div>"
    )
    await mail_service.send_email(
        to=user.email,
        subject="Please confirm your email address",
        html_body=html_body,
    )

    return {"message": "Please confirm your email address using the link we sent you."}


@app.get("/api/verify-email")
async def verify_email(token: str, session: Session = Depends(get_session)):
    """Completes registration and only now creates the user in the DB."""
    payload = auth_service.decode_email_verification_token(token)
    email = payload["email"]

    if auth_service.get_user_by_email(session, email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    new_user = user_service.create_db_user_from_hash(
        session,
        email=email,
        name=payload["name"],
        hashed_password=payload["hashed_password"],
    )
    session.commit()
    session.refresh(new_user)

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?verified=true")


@app.post("/api/login")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Authenticates a user and returns a JWT token."""
    user = auth_service.get_user_by_email(session, form_data.username)  # username is the email
    if not user or not user_service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/journals")
async def get_journals(
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.get_current_user),
):
    statement = select(models.Journals)

    db_journals = session.exec(statement).all()

    results = []
    for journal in db_journals:
        results.append(
            {
                "id": str(journal.id),
                "name": journal.name,
                "issn": journal.issn,
                "publisher": journal.publisher,
                "homepage_url": journal.homepage,
                "external_api": journal.external_api,
                # Papers only on the journal's own website aren't on OpenAlex.
                "semantic_search": journal.issn not in IMPORTERS,
            }
        )

    if not results:
        return {"message": "No journals found.", "results": []}
    return {"results": results}


def _journal_values(oa_item: dict) -> dict | None:
    """Maps a raw OpenAlex 'source' item to our Journals columns, or None if unusable.

    The OpenAlex source id stays the primary key; the ISSN is what we later hand
    to Crossref for the article search, so a source without one is unusable.
    """
    oa_id = oa_item.get("id", "").split("/")[-1]
    issn = oa_item.get("issn_l") or ""
    if not oa_id or not issn:
        return None
    return {
        "id": oa_id,
        "name": oa_item.get("display_name"),
        "issn": issn,
        "publisher": oa_item.get("host_organization_name") or "Unknown",
        "homepage": oa_item.get("homepage_url") or "",
    }


@app.post("/api/journals/import-by-name")
async def import_journals_by_name(
    payload: JournalImportByName,
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.require_admin),
):
    """Looks up a list of journal names on OpenAlex and stores the matches. Admin only."""
    imported = []
    not_found = []

    for name in payload.names:
        match = await search_service.fetch_journal_by_name(name)
        values = _journal_values(match) if match else None
        if values is None:
            not_found.append(name)
            continue

        stmt = sqlite_insert(models.Journals).values(**values).on_conflict_do_nothing()
        session.exec(stmt)
        imported.append(values)

    session.commit()
    return {
        "message": f"{len(imported)} of {len(payload.names)} journals imported.",
        "results": imported,
        "not_found": not_found,
    }


@app.delete("/api/journals/{journal_id}")
async def delete_journal(
    journal_id: str,
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.require_admin),
):
    """Removes a journal from the database. Admin only.

    Refuses if the journal is still used by any search profile, so profiles can
    never end up referencing a journal that no longer exists.
    """
    journal = session.get(models.Journals, journal_id)
    if journal is None:
        raise HTTPException(status_code=404, detail="Journal not found.")

    using_profiles = session.exec(
        select(models.Profile.profile_name, models.User.email)
        .join(models.ProfileJournalLink)
        .join(models.User, models.Profile.user_id == models.User.id)
        .where(models.ProfileJournalLink.journal_id == journal_id)
    ).all()
    if using_profiles:
        entries = [f"{name} ({email})" for name, email in using_profiles]
        shown = ", ".join(entries[:5]) + (" …" if len(entries) > 5 else "")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Journal is used by {len(entries)} profile(s) and cannot be deleted: {shown}"),
        )

    session.delete(journal)
    session.commit()
    return {"message": "Journal deleted.", "id": journal_id}


@app.get("/api/articles")
async def search_articles(
    journal_ids: List[str] = Query([]),
    keywords: str = Query(""),
    semantic_query: str = Query("", max_length=2000),
    from_date: str = Query(...),
    to_date: str = Query(...),
    page: int = Query(1),
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Searches for scientific articles in the selected journals."""
    # journal_ids are OpenAlex source ids; Crossref needs the ISSNs.
    statement = select(
        models.Journals.issn, models.Journals.external_api, models.Journals.id
    ).where(models.Journals.id.in_(journal_ids))
    journals = session.exec(statement).all()

    data = await search_service.search(
        issns=[issn for issn, _, _ in journals if issn],
        external_apis={issn: api for issn, api, _ in journals if issn and api},
        keywords=keywords,
        semantic_query=semantic_query,
        source_ids={issn: journal_id for issn, _, journal_id in journals if issn},
        from_date=from_date,
        to_date=to_date,
        limit=25,
        page=page,
        resolver=openurl_resolver_for(current_user.email),
        session=session,
    )
    return data


def _valid_journal_ids(session: Session, row_selection: dict[str, bool]) -> list[str]:
    """Filters the frontend's {journal_id: bool} map down to the ids that are
    actually selected AND still exist in the database."""
    selected_ids = [jid for jid, selected in (row_selection or {}).items() if selected]
    if not selected_ids:
        return []
    return list(
        session.exec(select(models.Journals.id).where(models.Journals.id.in_(selected_ids))).all()
    )


def _set_profile_journals(session: Session, profile_id: int, journal_ids: list[str]) -> None:
    """Replaces a profile's journal links with `journal_ids` using two bulk
    statements (one DELETE, one multi-row INSERT), so the number of round trips
    to the database stays constant instead of growing with the selection size."""
    session.exec(
        sql_delete(models.ProfileJournalLink).where(
            models.ProfileJournalLink.profile_id == profile_id
        )
    )
    if journal_ids:
        session.exec(
            sqlite_insert(models.ProfileJournalLink).values(
                [{"profile_id": profile_id, "journal_id": jid} for jid in journal_ids]
            )
        )


def _profile_response(profile: models.Profile, journal_ids: list[str] | None = None) -> dict:
    if journal_ids is None:
        journal_ids = [journal.id for journal in profile.journals]
    return {
        "id": profile.id,
        "name": profile.profile_name,
        "rowSelection": dict.fromkeys(journal_ids, True),
        "searchTerm": profile.searchTerm,
        "semanticQuery": profile.semantic_query,
        "searchMode": profile.search_mode,
        "emailNotifications": profile.email_notifications,
    }


def _profile_queries(settings: ProfileSettings) -> dict:
    """The profile's query fields; only the query of its search mode is kept."""
    semantic = settings.searchMode == "semantic"
    return {
        "searchTerm": "" if semantic else settings.searchTerm,
        "semantic_query": settings.semanticQuery if semantic else "",
        "search_mode": settings.searchMode,
    }


@app.post("/api/profiles", status_code=201)
async def create_profile(
    profile_data: ProfileCreate,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Creates a new search profile for the current user."""

    journal_ids = _valid_journal_ids(session, profile_data.settings.rowSelection)

    new_profile = models.Profile(
        profile_name=profile_data.name,
        user_id=current_user.id,
        **_profile_queries(profile_data.settings),
        email_notifications=profile_data.settings.emailNotifications,
    )

    try:
        session.add(new_profile)
        session.flush()
        _set_profile_journals(session, new_profile.id, journal_ids)
        session.commit()

    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a profile with this name.",
        ) from None

    session.refresh(new_profile)
    return _profile_response(new_profile, journal_ids)


@app.get("/api/profiles")
async def get_profiles(
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Returns all search profiles of the current user."""
    profiles = session.exec(
        select(models.Profile)
        .where(models.Profile.user_id == current_user.id)
        .options(selectinload(models.Profile.journals))
    ).all()

    return {"results": [_profile_response(p) for p in profiles]}


@app.put("/api/profiles/{profile_id}")
async def update_profile(
    profile_id: int,
    settings: ProfileSettings,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Updates an existing search profile."""
    profile = session.get(models.Profile, profile_id)
    if not profile or profile.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Profile not found.")

    journal_ids = _valid_journal_ids(session, settings.rowSelection)

    for field, value in _profile_queries(settings).items():
        setattr(profile, field, value)
    profile.email_notifications = settings.emailNotifications
    session.add(profile)
    _set_profile_journals(session, profile.id, journal_ids)
    session.commit()
    session.refresh(profile)

    return _profile_response(profile, journal_ids)


@app.patch("/api/profiles/{profile_id}/notifications")
async def update_profile_notifications(
    profile_id: int,
    payload: ProfileNotificationsUpdate,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Toggles email notifications for a search profile."""
    profile = session.get(models.Profile, profile_id)
    if not profile or profile.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Profile not found.")

    profile.email_notifications = payload.emailNotifications
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return _profile_response(profile)


@app.delete("/api/profiles/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.get_current_user),
):
    """Deletes a specific search profile."""
    profile = session.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    # Clear the journal links in one bulk statement so the ORM cascade on
    # `session.delete` has nothing left to remove row by row.
    _set_profile_journals(session, profile.id, [])
    session.delete(profile)
    session.commit()


def _saved_article_response(
    saved: models.SavedArticle, pdf_url: str | None = None, pdf_requested: bool = False
) -> dict:
    """A reading list entry: the saved search result plus the user's own data."""
    return {
        "id": saved.id,
        "article": {
            "id": saved.article_id,
            "title": saved.title,
            "author": saved.author,
            "journal_name": saved.journal_name,
            "publication_date": saved.publication_date,
            "journal_publication_date": saved.journal_publication_date,
            "issue": saved.issue,
            "doi": saved.doi,
            "url": saved.url,
            "library_url": saved.library_url,
            "abstract": saved.abstract,
            "topic": saved.topic,
        },
        "isRead": saved.is_read,
        # SQLite hands the UTC timestamp back without a timezone.
        "savedAt": saved.saved_at.replace(tzinfo=saved.saved_at.tzinfo or timezone.utc).isoformat(),
        "pdfUrl": pdf_url,
        "pdfRequested": pdf_requested,
    }


def _saved_article_responses(
    session: Session, user: models.User, saved: List[models.SavedArticle]
) -> List[dict]:
    """Reading list entries, each with its uploaded PDF and whether the user
    asked for one."""
    article_ids = [s.article_id for s in saved]
    pdf_urls = dict(
        session.exec(
            select(models.PaperPdf.article_id, models.PaperPdf.url).where(
                models.PaperPdf.article_id.in_(article_ids)
            )
        ).all()
    )
    requested = set(
        session.exec(
            select(models.PaperRequest.article_id).where(
                models.PaperRequest.user_id == user.id,
                models.PaperRequest.article_id.in_(article_ids),
            )
        ).all()
    )
    return [
        _saved_article_response(s, pdf_urls.get(s.article_id), s.article_id in requested)
        for s in saved
    ]


def _get_own_saved_article(
    session: Session, saved_id: int, user: models.User
) -> models.SavedArticle:
    saved = session.get(models.SavedArticle, saved_id)
    if not saved or saved.user_id != user.id:
        raise HTTPException(status_code=404, detail="Reading list entry not found.")
    return saved


@app.get("/api/saved-articles")
async def get_saved_articles(
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Returns the current user's reading list, most recently saved first."""
    saved = session.exec(
        select(models.SavedArticle)
        .where(models.SavedArticle.user_id == current_user.id)
        .order_by(models.SavedArticle.saved_at.desc(), models.SavedArticle.id.desc())
    ).all()
    return {"results": _saved_article_responses(session, current_user, saved)}


@app.post("/api/saved-articles", status_code=201)
async def save_articles(
    payload: SavedArticlesCreate,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Adds search results to the reading list. Articles already on it are skipped."""
    existing = set(
        session.exec(
            select(models.SavedArticle.article_id).where(
                models.SavedArticle.user_id == current_user.id
            )
        ).all()
    )

    added: List[models.SavedArticle] = []
    for article in payload.articles:
        if article.id in existing:
            continue
        existing.add(article.id)
        values = article.model_dump(exclude={"id"})
        added.append(models.SavedArticle(user_id=current_user.id, article_id=article.id, **values))

    try:
        session.add_all(added)
        session.commit()
    except IntegrityError:
        # Another request saved one of them in the meantime.
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Some of these articles were just saved elsewhere. Please reload.",
        ) from None

    for saved in added:
        session.refresh(saved)
    return {
        "results": _saved_article_responses(session, current_user, added),
        "skipped": len(payload.articles) - len(added),
    }


@app.patch("/api/saved-articles/{saved_id}")
async def update_saved_article(
    saved_id: int,
    payload: SavedArticleUpdate,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Marks a reading list entry as read or unread."""
    saved = _get_own_saved_article(session, saved_id, current_user)
    saved.is_read = payload.isRead
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return _saved_article_responses(session, current_user, [saved])[0]


@app.delete("/api/saved-articles/{saved_id}", status_code=204)
async def delete_saved_article(
    saved_id: int,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Removes an article from the reading list, along with a PDF request for it."""
    saved = _get_own_saved_article(session, saved_id, current_user)
    _delete_paper_requests(session, current_user, [saved.article_id])
    session.delete(saved)
    session.commit()


@app.delete("/api/saved-articles", status_code=204)
async def delete_saved_articles(
    ids: List[int] = Query(..., max_length=500),
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Removes several articles from the reading list at once. Ids that aren't
    on the user's own list are ignored."""
    article_ids = session.exec(
        select(models.SavedArticle.article_id).where(
            models.SavedArticle.user_id == current_user.id,
            models.SavedArticle.id.in_(ids),
        )
    ).all()
    _delete_paper_requests(session, current_user, list(article_ids))
    session.exec(
        sql_delete(models.SavedArticle).where(
            models.SavedArticle.user_id == current_user.id,
            models.SavedArticle.id.in_(ids),
        )
    )
    session.commit()


def _delete_paper_requests(session: Session, user: models.User, article_ids: List[str]) -> None:
    if article_ids:
        session.exec(
            sql_delete(models.PaperRequest).where(
                models.PaperRequest.user_id == user.id,
                models.PaperRequest.article_id.in_(article_ids),
            )
        )


async def _notify_admins_of_pdf_request(
    session: Session, user: models.User, saved: models.SavedArticle
) -> None:
    """Mails all admins that a user is asking for a paper's PDF."""
    title = escape(saved.title or saved.article_id)
    journal = escape(saved.journal_name or "")
    doi_link = escape(saved.doi or saved.url or f"https://doi.org/{saved.article_id}")
    admin_link = escape(f"{settings.FRONTEND_URL}/admin/pdf-requests")
    html = (
        "<div style='font-family:Arial,Helvetica,sans-serif;max-width:640px;'>"
        "<h1 style='font-size:20px;'>New PDF request</h1>"
        f"<p style='font-size:14px;'>{escape(user.name)} ({escape(user.email)}) has no access "
        "to this paper through the library and asks for its PDF:</p>"
        f"<p style='font-size:16px;font-weight:600;margin-bottom:4px;'>{title}</p>"
        f"<p style='color:#555;font-size:13px;margin-top:0;'>{journal} &middot; "
        f"<a href='{doi_link}'>{doi_link}</a></p>"
        f"<p style='font-size:14px;'><a href='{admin_link}'>Upload the PDF in PaperScout</a></p>"
        "</div>"
    )
    for email in user_service.get_admin_emails(session):
        await mail_service.send_email(to=email, subject=f"PDF request: {title}", html_body=html)


@app.post("/api/saved-articles/{saved_id}/pdf-request")
async def request_paper_pdf(
    saved_id: int,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Asks the admins for the PDF of a paper on the reading list, for papers the
    library has no access to. Does nothing if a PDF is already there."""
    saved = _get_own_saved_article(session, saved_id, current_user)
    has_pdf = session.get(models.PaperPdf, saved.article_id) is not None
    if not has_pdf:
        session.add(models.PaperRequest(user_id=current_user.id, article_id=saved.article_id))
        try:
            session.commit()
        except IntegrityError:
            # Already requested.
            session.rollback()
        else:
            await _notify_admins_of_pdf_request(session, current_user, saved)
    return _saved_article_responses(session, current_user, [saved])[0]


@app.delete("/api/saved-articles/{saved_id}/pdf-request")
async def cancel_paper_pdf_request(
    saved_id: int,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Withdraws the user's PDF request for a paper on the reading list."""
    saved = _get_own_saved_article(session, saved_id, current_user)
    _delete_paper_requests(session, current_user, [saved.article_id])
    session.commit()
    return _saved_article_responses(session, current_user, [saved])[0]


@app.get("/api/admin/pdf-requests")
async def list_pdf_requests(
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.require_admin),
):
    """All requested papers, oldest request first, with who asked for them and the
    uploaded PDF if there is one, followed by uploaded PDFs without requests.
    Admin only."""
    rows = session.exec(
        select(models.PaperRequest, models.User.email, models.SavedArticle)
        .join(models.User, models.PaperRequest.user_id == models.User.id)
        .join(
            models.SavedArticle,
            (models.SavedArticle.user_id == models.PaperRequest.user_id)
            & (models.SavedArticle.article_id == models.PaperRequest.article_id),
        )
        .order_by(models.PaperRequest.requested_at, models.PaperRequest.id)
    ).all()
    pdfs = {pdf.article_id: pdf for pdf in session.exec(select(models.PaperPdf)).all()}

    papers: dict = {}
    for request, email, saved in rows:
        paper = papers.get(request.article_id)
        if paper is None:
            pdf = pdfs.get(request.article_id)
            requested_at = request.requested_at.replace(
                tzinfo=request.requested_at.tzinfo or timezone.utc
            )
            paper = papers[request.article_id] = {
                "articleId": request.article_id,
                "title": saved.title,
                "journalName": saved.journal_name,
                "doi": saved.doi,
                "libraryUrl": saved.library_url,
                "requestedAt": requested_at.isoformat(),
                "requesters": [],
                "pdfUrl": pdf.url if pdf else None,
            }
        paper["requesters"].append(email)

    # PDFs nobody asks for anymore (every requester removed the paper) are listed
    # too, so they can still be replaced or deleted.
    for pdf in pdfs.values():
        if pdf.article_id in papers:
            continue
        saved = session.exec(
            select(models.SavedArticle).where(models.SavedArticle.article_id == pdf.article_id)
        ).first()
        papers[pdf.article_id] = {
            "articleId": pdf.article_id,
            "title": saved.title if saved else None,
            "journalName": saved.journal_name if saved else None,
            "doi": saved.doi if saved else f"https://doi.org/{pdf.article_id}",
            "libraryUrl": saved.library_url if saved else None,
            "requestedAt": None,
            "requesters": [],
            "pdfUrl": pdf.url,
        }
    return {"results": list(papers.values()), "uploadsEnabled": blob_service.is_configured()}


@app.post("/api/admin/pdf-upload-token")
async def create_pdf_upload_token(
    payload: PaperPdfUploadToken,
    _: models.User = Depends(auth_service.require_admin),
):
    """A short-lived token the admin's browser uploads one paper PDF to Vercel Blob
    with. Admin only."""
    if not blob_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="PDF uploads are not configured (BLOB_READ_WRITE_TOKEN missing).",
        )
    pathname = blob_service.paper_pathname(payload.article_id)
    token = blob_service.create_client_token(
        pathname,
        allowed_content_types=["application/pdf"],
        maximum_size_in_bytes=settings.PAPER_PDF_MAX_MB * 1024 * 1024,
    )
    return {"pathname": pathname, "clientToken": token}


@app.put("/api/admin/pdfs")
async def store_paper_pdf(
    payload: PaperPdfCreate,
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.require_admin),
):
    """Stores the URL of a PDF uploaded with a token from /api/admin/pdf-upload-token.
    From then on everyone with the paper on their reading list can open it. A PDF
    already stored for the paper is replaced. Admin only."""
    if not blob_service.is_uploaded_blob_url(
        payload.url, blob_service.paper_pathname(payload.article_id)
    ):
        raise HTTPException(status_code=400, detail="Not an uploaded PDF for this paper.")

    pdf = session.get(models.PaperPdf, payload.article_id)
    replaced_url = pdf.url if pdf and pdf.url != payload.url else None
    if pdf is None:
        pdf = models.PaperPdf(article_id=payload.article_id, url=payload.url)
    else:
        pdf.url = payload.url
        pdf.uploaded_at = datetime.now(timezone.utc)
    session.add(pdf)
    session.commit()

    if replaced_url:
        await blob_service.delete_blob(replaced_url)
    return {"articleId": pdf.article_id, "pdfUrl": pdf.url}


@app.delete("/api/admin/pdfs", status_code=204)
async def delete_paper_pdf(
    # A query parameter, since DOIs contain slashes.
    article_id: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.require_admin),
):
    """Deletes a paper's uploaded PDF. Its requests stay, so the paper is open
    again and a new PDF can be uploaded. Admin only."""
    pdf = session.get(models.PaperPdf, article_id)
    if pdf is None:
        raise HTTPException(status_code=404, detail="No PDF uploaded for this paper.")
    url = pdf.url
    session.delete(pdf)
    session.commit()
    await blob_service.delete_blob(url)


@app.api_route("/api/users/me", response_model=UserPublic, methods=["GET", "HEAD"])
async def read_users_me(
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Returns the data of the currently authenticated user."""
    return current_user


@app.put("/api/users/me/email")
async def update_email(
    payload: ChangeEmailRequest,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Changes the email address of the current user and issues a new token,
    since the old token was issued for the previous email address."""
    if not user_service.verify_password(payload.currentPassword, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password.")

    if not user_service.is_allowed_email(payload.newEmail):
        raise HTTPException(status_code=400, detail=ALLOWED_EMAIL_DETAIL)

    if payload.newEmail != current_user.email and auth_service.get_user_by_email(
        session, payload.newEmail
    ):
        raise HTTPException(status_code=400, detail="This email address is already in use.")

    current_user.email = payload.newEmail
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    access_token = auth_service.create_access_token(
        data={"sub": current_user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.put("/api/users/me/password")
async def update_password(
    payload: ChangePasswordRequest,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Changes the password of the current user."""
    if not user_service.verify_password(payload.currentPassword, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password.")

    if len(payload.newPassword) < 8:
        raise HTTPException(
            status_code=400,
            detail="The new password must be at least 8 characters long.",
        )

    current_user.hashed_password = user_service.get_password_hash(payload.newPassword)
    session.add(current_user)
    session.commit()

    return {"message": "Password changed successfully."}


@app.delete("/api/users/me", status_code=204)
async def delete_account(
    payload: DeleteAccountRequest,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Irrevocably deletes the current user's account, including all search profiles
    and the reading list."""
    if not user_service.verify_password(payload.currentPassword, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password.")

    session.exec(
        sql_delete(models.SavedArticle).where(models.SavedArticle.user_id == current_user.id)
    )
    session.exec(
        sql_delete(models.PaperRequest).where(models.PaperRequest.user_id == current_user.id)
    )

    profile_ids = session.exec(
        select(models.Profile.id).where(models.Profile.user_id == current_user.id)
    ).all()
    if profile_ids:
        session.exec(
            sql_delete(models.ProfileJournalLink).where(
                models.ProfileJournalLink.profile_id.in_(profile_ids)
            )
        )
        session.exec(sql_delete(models.Profile).where(models.Profile.id.in_(profile_ids)))

    session.delete(current_user)
    session.commit()


@app.post("/api/digest/send-all")
async def send_digest_to_all(
    _: models.User = Depends(auth_service.require_admin),
):
    """Runs the monthly digest send for all users right now. Admin only."""
    sent_count = await digest_service.run_monthly_digest()
    return {"message": f"Digest sent. {sent_count} email(s) sent.", "sent": sent_count}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
