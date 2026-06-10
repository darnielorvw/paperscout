import os
from contextlib import asynccontextmanager

from database import models
from database.database import engine
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from services.auth_service import get_current_user
from services.download_service import DownloadService
from services.search_service import SearchService
from sqlmodel import SQLModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- VOR DEM START DER APP ----
    # Hier passiert die Magie: Wenn die paperscout.db fehlt,
    # wird sie JETZT erstellt. Wenn sie da ist, passiert nichts.
    SQLModel.metadata.create_all(engine)
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


@app.get("/api/search")
async def search_papers(
    query: str = Query(..., description="Suchbegriff für die Literaturrecherche")
):
    """Sucht nach Open-Access-Papern basierend auf Keywords."""
    results = await search_service.search_open_access_papers(query=query)
    if not results:
        return {"message": "Keine Open-Access-Treffer gefunden.", "results": []}
    return {"results": results}


@app.get("/api/download")
async def download_paper(
    doi: str, title: str, current_user: dict = Depends(get_current_user)
):
    """Sucht die PDF-Quelle und streamt die Datei direkt an das Frontend."""
    # 1. Versuche die direkte PDF-URL über Unpaywall zu ermitteln
    pdf_url = await download_service.get_pdf_download_url(
        doi, current_user.get("email", "")
    )
    print(current_user)

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
