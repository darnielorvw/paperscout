import json
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import models
from database.database import engine, get_session
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    ProfileCreate,
    ProfileNotificationsUpdate,
    ProfileSettings,
    UserCreate,
    UserPublic,
)
from services import auth_service, user_service
from services.digest_service import DigestService
from services.download_service import DownloadService
from services.mail_service import MailService
from services.search_service import SearchService
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from config import settings

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

    print("🚀 Datenbank wurde überprüft und ist bereit!", flush=True)

    scheduler.add_job(
        digest_service.run_monthly_digest,
        CronTrigger.from_crontab(settings.DIGEST_CRON),
        id="monthly_paper_digest",
        replace_existing=True,
    )
    scheduler.start()
    print(f"📅 Monatlicher Digest-Versand geplant ({settings.DIGEST_CRON}).", flush=True)

    yield  # Hier läuft die FastAPI App
    scheduler.shutdown()
    await download_service.aclose()

    # ---- BEIM BEENDEN DER APP ----
    print("🛑 Server wird heruntergefahren...", flush=True)


app = FastAPI(title="PaperScout API", lifespan=lifespan, version="1.0")

# CORS-Mapping: Erlaubt deinem React-Frontend (Vite läuft meist auf Port 5173) den Zugriff
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
    """Startet die Registrierung: verschickt einen Bestätigungslink per E-Mail.

    Der Account wird erst angelegt, wenn der Link geklickt wird (siehe /api/verify-email).
    Das verhindert, dass Bots die DB mit unbegrenzt vielen Fake-Registrierungen fluten.
    """
    if auth_service.get_user_by_email(session, user.email):
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert.")

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
        "<h1 style='margin-bottom:4px;'>Willkommen bei PaperScout</h1>"
        "<p style='color:#666;'>Bitte bestätige deine E-Mail-Adresse, um deine Registrierung abzuschließen.</p>"
        f"<p><a href='{verify_link}' style='display:inline-block;padding:8px 14px;"
        "background:#1a56db;color:#fff;border-radius:6px;text-decoration:none;'>"
        "E-Mail-Adresse bestätigen</a></p>"
        f"<p style='color:#999;font-size:12px;'>Der Link ist {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} Stunden gültig.</p>"
        "</div>"
    )
    await mail_service.send_email(
        to=user.email,
        subject="Bitte bestätige deine E-Mail-Adresse",
        html_body=html_body,
    )

    return {
        "message": "Bitte bestätige deine E-Mail-Adresse über den Link, den wir dir geschickt haben."
    }


@app.get("/api/verify-email")
async def verify_email(token: str, session: Session = Depends(get_session)):
    """Schließt die Registrierung ab und legt den Nutzer erst jetzt in der DB an."""
    payload = auth_service.decode_email_verification_token(token)
    email = payload["email"]

    if auth_service.get_user_by_email(session, email):
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert.")

    new_user = user_service.create_db_user_from_hash(
        session, email=email, name=payload["name"], hashed_password=payload["hashed_password"]
    )
    session.commit()
    session.refresh(new_user)

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?verified=true")


@app.post("/api/login")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Authentifiziert einen Benutzer und gibt ein JWT-Token zurück."""
    user = auth_service.get_user_by_email(
        session, form_data.username
    )  # username ist die E-Mail
    if not user or not user_service.verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Falsche E-Mail oder Passwort.",
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
        return {"message": "Keine Journals gefunden.", "results": []}
    return {"results": results}


@app.post("/api/journals/import")
async def import_journals(
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.get_current_user),
):
    """Sucht Journals bei OpenAlex und speichert sie in der lokalen Datenbank."""
    external_results = await search_service.fetch_external_journals()

    imported_journals = []
    for item in external_results:
        oa_id = item.get("id", "").split("/")[-1]
        if not oa_id:
            continue

        stmt = (
            sqlite_insert(models.Journals)
            .values(
                id=oa_id,
                name=item.get("display_name"),
                issn=item.get("issn_l") or "",
                publisher=item.get("host_organization_name") or "Unknown",
                homepage=item.get("homepage_url") or "",
            )
            .on_conflict_do_nothing()
        )

        session.exec(stmt)
        imported_journals.append(oa_id)

    session.commit()
    return {
        "message": f"{len(imported_journals)} Journals importiert.",
        "results": imported_journals,
    }


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
    """Sucht nach wissenschaftlichen Artikeln in den gewählten Journals."""
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


@app.post("/api/profiles", status_code=201)
async def create_profile(
    profile_data: ProfileCreate,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Erstellt ein neues Suchprofil für den aktuellen Benutzer."""

    start = profile_data.settings.startDate
    end = profile_data.settings.endDate

    # 2. Neues DB-Profil mit den flachen Spalten befüllen
    new_profile = models.Profile(
        profile_name=profile_data.name,
        user_id=current_user.id,
        row_selection=profile_data.settings.rowSelection,
        searchTerm=profile_data.settings.searchTerm,
        start_date=start,
        end_date=end,
        email_notifications=profile_data.settings.emailNotifications,
    )

    new_profile.settings_hash = new_profile.generate_hash()

    try:
        session.add(new_profile)
        session.commit()
        session.refresh(new_profile)

    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A profile with the same name or settings already exists.",
        )

    # Kombiniere die Daten für die Antwort, wie vom Frontend erwartet
    response_data = {
        "name": new_profile.profile_name,
        "id": new_profile.id,
        "rowSelection": new_profile.row_selection,
        "searchTerm": new_profile.searchTerm,
        "date": {"from": new_profile.start_date, "to": new_profile.end_date},
        "emailNotifications": new_profile.email_notifications,
    }
    return response_data


@app.get("/api/profiles")
async def get_profiles(
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Gibt alle Suchprofile des aktuellen Benutzers zurück."""
    profiles = session.exec(
        select(models.Profile).where(models.Profile.user_id == current_user.id)
    ).all()

    # Transformiere die Daten, um dem Frontend-Format zu entsprechen
    results = [
        {
            "id": p.id,
            "name": p.profile_name,
            "rowSelection": p.row_selection,
            "searchTerm": p.searchTerm,
            "date": {"from": p.start_date, "to": p.end_date},
            "emailNotifications": p.email_notifications,
        }
        for p in profiles
    ]
    return {"results": results}


@app.put("/api/profiles/{profile_id}")
async def update_profile(
    profile_id: int,
    settings: ProfileSettings,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Aktualisiert ein bestehendes Suchprofil."""
    profile = session.get(models.Profile, profile_id)
    if not profile or profile.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden.")

    # Update der Felder
    profile.row_selection = settings.rowSelection
    profile.searchTerm = settings.searchTerm
    profile.start_date = settings.startDate
    profile.end_date = settings.endDate
    profile.email_notifications = settings.emailNotifications
    profile.settings_hash = profile.generate_hash()

    session.add(profile)
    session.commit()
    session.refresh(profile)

    response_data = {
        "id": profile.id,
        "name": profile.profile_name,
        "rowSelection": profile.row_selection,
        "searchTerm": profile.searchTerm,
        "date": {"from": profile.start_date, "to": profile.end_date},
        "emailNotifications": profile.email_notifications,
    }
    return response_data


@app.patch("/api/profiles/{profile_id}/notifications")
async def update_profile_notifications(
    profile_id: int,
    payload: ProfileNotificationsUpdate,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Schaltet die E-Mail-Benachrichtigungen für ein Suchprofil um."""
    profile = session.get(models.Profile, profile_id)
    if not profile or profile.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden.")

    profile.email_notifications = payload.emailNotifications
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return {
        "id": profile.id,
        "name": profile.profile_name,
        "rowSelection": profile.row_selection,
        "searchTerm": profile.searchTerm,
        "date": {"from": profile.start_date, "to": profile.end_date},
        "emailNotifications": profile.email_notifications,
    }


@app.delete("/api/profiles/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    session: Session = Depends(get_session),
    _: models.User = Depends(auth_service.get_current_user),
):
    """Löscht ein bestimmtes Suchprofil."""
    profile = session.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden.")
    session.delete(profile)
    session.commit()


@app.api_route("/api/users/me", response_model=UserPublic, methods=["GET", "HEAD"])
async def read_users_me(
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Gibt die Daten des aktuell authentifizierten Benutzers zurück."""
    return current_user


@app.put("/api/users/me/email")
async def update_email(
    payload: ChangeEmailRequest,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Ändert die E-Mail-Adresse des aktuellen Benutzers und stellt ein neues Token aus,
    da das alte Token auf die vorherige E-Mail-Adresse ausgestellt war."""
    if not user_service.verify_password(payload.currentPassword, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Falsches Passwort.")

    if payload.newEmail != current_user.email and auth_service.get_user_by_email(
        session, payload.newEmail
    ):
        raise HTTPException(status_code=400, detail="Diese E-Mail-Adresse wird bereits verwendet.")

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
    """Ändert das Passwort des aktuellen Benutzers."""
    if not user_service.verify_password(payload.currentPassword, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Falsches Passwort.")

    if len(payload.newPassword) < 8:
        raise HTTPException(
            status_code=400, detail="Das neue Passwort muss mindestens 8 Zeichen lang sein."
        )

    current_user.hashed_password = user_service.get_password_hash(payload.newPassword)
    session.add(current_user)
    session.commit()

    return {"message": "Passwort wurde erfolgreich geändert."}


@app.delete("/api/users/me", status_code=204)
async def delete_account(
    payload: DeleteAccountRequest,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Löscht den Account des aktuellen Benutzers unwiderruflich, inklusive aller Suchprofile."""
    if not user_service.verify_password(payload.currentPassword, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Falsches Passwort.")

    profiles = session.exec(
        select(models.Profile).where(models.Profile.user_id == current_user.id)
    ).all()
    for profile in profiles:
        session.delete(profile)

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
        raise HTTPException(status_code=400, detail="Keine Work-IDs übergeben.")

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
            detail="Der Bulk-Download konnte nicht erstellt werden.",
        )

    return StreamingResponse(
        iter([archive_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=papers.zip"},
    )


@app.get("/api/digest/download")
async def digest_download(token: str, zip_name: str = "papers"):
    """Öffentlicher Download-Endpunkt für die signierten ZIP-Links aus Digest-Mails.

    Erfordert keinen Login, da der Link direkt aus der E-Mail geklickt wird –
    der Token selbst übernimmt die Autorisierung (siehe DownloadService.create_bulk_download_token).
    """
    payload = download_service.decode_bulk_download_token(token)
    work_ids: List[str] = payload.get("work_ids", [])
    titles_by_id = await search_service.fetch_titles_by_ids(work_ids)
    papers = [(work_id, titles_by_id.get(work_id)) for work_id in work_ids]

    archive_bytes = await download_service.download_pdf_from_openalex(papers)
    if not archive_bytes:
        raise HTTPException(
            status_code=500,
            detail="Der Download konnte nicht erstellt werden.",
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
    """Verschickt den monatlichen Digest sofort an den aktuell eingeloggten Nutzer (zu Testzwecken)."""
    sent = await digest_service.send_digest_to_user(session, current_user)
    if not sent:
        raise HTTPException(
            status_code=400,
            detail="Kein Digest verschickt (keine Suchprofile vorhanden oder SMTP nicht konfiguriert – siehe Server-Logs).",
        )
    return {"message": f"Digest wurde an {current_user.email} verschickt."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
