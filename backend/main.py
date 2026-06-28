import os
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List

from database import models
from database.database import engine, get_session
from database.seed_data import DEFAULT_JOURNALS
from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from schemas import UserCreate, UserLogin, UserPublic
from services import auth_service, user_service
from services.download_service import DownloadService
from services.search_service import SearchService
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, SQLModel, select


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- VOR DEM START DER APP ----
    # Hier passiert die Magie: Wenn die paperscout.db fehlt,
    # wird sie JETZT erstellt. Wenn sie da ist, passiert nichts.
    SQLModel.metadata.create_all(engine)

    # Standard-Journals hinzufügen, falls die Tabelle noch leer ist
    with Session(engine) as session:
        existing_journal = session.exec(select(models.Journals)).first()
        # if not existing_journal:
        #     default_journals = [
        #         models.Journals(**journal_data) for journal_data in DEFAULT_JOURNALS
        #     ]
        #     session.add_all(default_journals)
        #     session.commit()
        #     print(
        #         f"📚 {len(default_journals)} Standard-Journals wurden erfolgreich zur Datenbank hinzugefügt!",
        #         flush=True,
        #     )

    print("🚀 Datenbank wurde überprüft und ist bereit!", flush=True)

    yield  # Hier läuft die FastAPI App

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

ACCESS_TOKEN_EXPIRE_MINUTES = 30


@app.post("/api/register", response_model=UserPublic, status_code=201)
async def register_user(user: UserCreate, session: Session = Depends(get_session)):
    """Registriert einen neuen Benutzer in der Datenbank."""
    db_user = auth_service.get_user_by_email(session, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert.")

    new_user = user_service.create_db_user(session, user)
    session.commit()
    session.refresh(new_user)
    return new_user


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


@app.api_route("/api/users/me", response_model=UserPublic, methods=["GET", "HEAD"])
async def read_users_me(
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Gibt die Daten des aktuell authentifizierten Benutzers zurück."""
    return current_user


@app.get("/api/download")
async def download_paper(
    doi: str,
    title: str,
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Sucht die PDF-Quelle und streamt die Datei direkt an das Frontend."""
    # 1. Versuche die direkte PDF-URL über Unpaywall zu ermitteln
    pdf_url = await download_service.get_pdf_download_url(
        doi,
        current_user.email,  # Korrekter Zugriff auf die E-Mail des SQLModel-Benutzers
    )

    if not pdf_url:
        raise HTTPException(
            status_code=404,
            detail="Keine legale Open-Access-PDF-URL für diese DOI gefunden.",
        )

    # 2. Dateinamen säubern
    safe_title = "".join(
        [c for c in title if c.isalpha() or c.isdigit() or c == " "]
    ).rstrip()
    filename = f"{safe_title[:50]}.pdf".replace(" ", "_")

    # 3. PDF auf den Server spiegeln
    filepath = await download_service.download_pdf(pdf_url, filename)

    if not filepath or not os.path.exists(filepath):
        raise HTTPException(
            status_code=500,
            detail="Der automatische Download vom Verlags-Server ist fehlgeschlagen.",
        )

    # 4. Datei als Download an React zurückgeben
    return FileResponse(path=filepath, filename=filename, media_type="application/pdf")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
