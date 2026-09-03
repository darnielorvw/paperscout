import json
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import settings
from database import models
from database.database import engine, get_session
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from schemas import (ChangeEmailRequest, ChangePasswordRequest,
                     DeleteAccountRequest, JournalImportByName, ProfileCreate,
                     ProfileNotificationsUpdate, ProfileSettings, UserCreate,
                     UserPublic)
from services import auth_service, user_service
from services.digest_service import DigestService
from services.download_service import DownloadService
from services.mail_service import MailService
from services.search_service import SearchService
from sqlalchemy import delete as sql_delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, SQLModel, select

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):

    SQLModel.metadata.create_all(engine)

    with engine.connect() as conn:
        existing_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profile)")
        }
        if "email_notifications" not in existing_columns:
            conn.exec_driver_sql(
                "ALTER TABLE profile ADD COLUMN email_notifications BOOLEAN DEFAULT 1"
            )
            conn.commit()

        existing_user_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(user)")
        }
        if "is_admin" not in existing_user_columns:
            conn.exec_driver_sql(
                "ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"
            )
            conn.commit()

        # Profiles no longer store a date range - drop the now-unused columns.
        existing_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profile)")
        }
        for column in ("start_date", "end_date"):
            if column in existing_columns:
                conn.exec_driver_sql(f"ALTER TABLE profile DROP COLUMN {column}")
                conn.commit()

        # Journals used to be stored as a JSON `row_selection` map on the profile
        # and de-duplicated via a globally unique `settings_hash`. They are now
        # normalised into the `profilejournallink` join table, and profile names
        # are unique per user instead of globally. Migrate legacy profile rows.
        legacy_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profile)")
        }
        if "row_selection" in legacy_columns or "settings_hash" in legacy_columns:
            if "row_selection" in legacy_columns:
                valid_ids = {
                    row[0]
                    for row in conn.exec_driver_sql("SELECT id FROM journals")
                }
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
    await download_service.aclose()

    # ---- ON APP SHUTDOWN ----
    print("🛑 Server is shutting down...", flush=True)


app = FastAPI(title="PaperScout API", lifespan=lifespan, version="1.0")

# CORS mapping: allows your React frontend (Vite usually runs on port 5173) to access the API
_cors_origins = sorted(
    {settings.FRONTEND_URL}
   
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

search_service = SearchService()
download_service = DownloadService()
mail_service = MailService()
digest_service = DigestService(search_service, mail_service, download_service)

ACCESS_TOKEN_EXPIRE_MINUTES = 60


@app.post("/api/register", status_code=202)
async def register_user(user: UserCreate, session: Session = Depends(get_session)):
    """Starts registration: sends a confirmation link by email.

    The account is only created once the link is clicked (see /api/verify-email).
    This prevents bots from flooding the DB with an unlimited number of fake registrations.
    """
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
    user = auth_service.get_user_by_email(
        session, form_data.username
    )  # username is the email
    if not user or not user_service.verify_password(
        form_data.password, user.hashed_password
    ):
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
            }
        )

    if not results:
        return {"message": "No journals found.", "results": []}
    return {"results": results}


@app.get("/api/test")
async def test():
    return "hallo"


def _journal_values(oa_item: dict) -> dict | None:
    """Maps a raw OpenAlex 'source' item to our Journals columns, or None if unusable."""
    oa_id = oa_item.get("id", "").split("/")[-1]
    if not oa_id:
        return None
    return {
        "id": oa_id,
        "name": oa_item.get("display_name"),
        "issn": oa_item.get("issn_l") or "",
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
            detail=(
                f"Journal is used by {len(entries)} profile(s) and cannot "
                f"be deleted: {shown}"
            ),
        )

    session.delete(journal)
    session.commit()
    return {"message": "Journal deleted.", "id": journal_id}


@app.get("/api/articles")
async def search_articles(
    journal_ids: List[str] = Query([]),
    keywords: str = Query(""),
    from_date: str = Query(...),
    to_date: str = Query(...),
    page: int = Query(1),
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.get_current_user),
):
    """Searches for scientific articles in the selected journals."""
    statement = select(models.Journals.id).where(models.Journals.id.in_(journal_ids))
    oa_ids = session.exec(statement).all()

    data = await search_service.search(
        journal_ids=[id for id in oa_ids if id],
        keywords=keywords,
        from_date=from_date,
        to_date=to_date,
        limit=25,
        page=page,
    )
    return data


def _valid_journal_ids(
    session: Session, row_selection: dict[str, bool]
) -> list[str]:
    """Filters the frontend's {journal_id: bool} map down to the ids that are
    actually selected AND still exist in the database."""
    selected_ids = [jid for jid, selected in (row_selection or {}).items() if selected]
    if not selected_ids:
        return []
    return list(
        session.exec(
            select(models.Journals.id).where(models.Journals.id.in_(selected_ids))
        ).all()
    )


def _set_profile_journals(
    session: Session, profile_id: int, journal_ids: list[str]
) -> None:
    """Replaces a profile's journal links with `journal_ids` using two bulk
    statements (one DELETE, one multi-row INSERT), so the number of round trips
    to the database stays constant instead of growing with the selection size."""
    session.execute(
        sql_delete(models.ProfileJournalLink).where(
            models.ProfileJournalLink.profile_id == profile_id
        )
    )
    if journal_ids:
        session.execute(
            sqlite_insert(models.ProfileJournalLink).values(
                [
                    {"profile_id": profile_id, "journal_id": jid}
                    for jid in journal_ids
                ]
            )
        )


def _profile_response(
    profile: models.Profile, journal_ids: list[str] | None = None
) -> dict:
    if journal_ids is None:
        journal_ids = [journal.id for journal in profile.journals]
    return {
        "id": profile.id,
        "name": profile.profile_name,
        "rowSelection": {jid: True for jid in journal_ids},
        "searchTerm": profile.searchTerm,
        "emailNotifications": profile.email_notifications,
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
        searchTerm=profile_data.settings.searchTerm,
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
        )

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

    profile.searchTerm = settings.searchTerm
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
    if not user_service.verify_password(
        payload.currentPassword, current_user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Incorrect password.")

    if payload.newEmail != current_user.email and auth_service.get_user_by_email(
        session, payload.newEmail
    ):
        raise HTTPException(
            status_code=400, detail="This email address is already in use."
        )

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
    if not user_service.verify_password(
        payload.currentPassword, current_user.hashed_password
    ):
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
    """Irrevocably deletes the current user's account, including all search profiles."""
    if not user_service.verify_password(
        payload.currentPassword, current_user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Incorrect password.")

    profile_ids = session.exec(
        select(models.Profile.id).where(models.Profile.user_id == current_user.id)
    ).all()
    if profile_ids:
        session.execute(
            sql_delete(models.ProfileJournalLink).where(
                models.ProfileJournalLink.profile_id.in_(profile_ids)
            )
        )
        session.execute(
            sql_delete(models.Profile).where(models.Profile.id.in_(profile_ids))
        )

    session.delete(current_user)
    session.commit()


@app.get("/api/bulk-download")
async def bulk_download(
    work_ids: str,
    titles: str | None = None,
    _: models.User = Depends(auth_service.get_current_user),
):
    ids = [work_id for work_id in work_ids.split(",") if work_id]
    if not ids:
        raise HTTPException(status_code=400, detail="No work IDs provided.")

    parsed_titles: list[str] = []
    if titles:
        try:
            parsed_titles = json.loads(titles)
        except json.JSONDecodeError:
            parsed_titles = []

    papers = [
        (work_id, parsed_titles[index] if index < len(parsed_titles) else None)
        for index, work_id in enumerate(ids)
    ]
    archive_bytes = await download_service.download_pdf_from_openalex(papers)
    if not archive_bytes:
        raise HTTPException(
            status_code=500,
            detail="The bulk download could not be created.",
        )

    return StreamingResponse(
        iter([archive_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=papers.zip"},
    )


@app.get("/api/digest/download")
async def digest_download(token: str, zip_name: str = "papers"):
    """Public download endpoint for the signed ZIP links from digest emails.

    Requires no login since the link is clicked directly from the email —
    the token itself handles the authorization (see DownloadService.create_bulk_download_token).
    """
    payload = download_service.decode_bulk_download_token(token)
    work_ids: List[str] = payload.get("work_ids", [])
    titles_by_id = await search_service.fetch_titles_by_ids(work_ids)
    papers = [(work_id, titles_by_id.get(work_id)) for work_id in work_ids]

    archive_bytes = await download_service.download_pdf_from_openalex(papers)
    if not archive_bytes:
        raise HTTPException(
            status_code=500,
            detail="The download could not be created.",
        )

    safe_name = download_service.sanitize_filename(zip_name, "papers")
    return StreamingResponse(
        iter([archive_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.zip"},
    )


@app.post("/api/digest/send-test")
async def send_test_digest(
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Sends the monthly digest immediately to the currently logged-in user (for testing purposes)."""
    sent = await digest_service.send_digest_to_user(session, current_user)
    if not sent:
        raise HTTPException(
            status_code=400,
            detail="No digest sent (no search profiles found or SMTP not configured — see server logs).",
        )
    return {"message": f"Digest sent to {current_user.email}."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
