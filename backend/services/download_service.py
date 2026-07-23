import logging  # Importiere das Logging-Modul
import os
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from config import settings
from fastapi import HTTPException

# Konfiguriere Logging (kann auch global in main.py erfolgen, hier für den Diff)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DownloadService:
    def __init__(self):
        self.DOWNLOAD_TOKEN_EXPIRE_MINUTES = 5

    def create_download_token(self, filepath: str, filename: str) -> str:
        """Erstellt einen kurzlebigen JWT für einen sicheren Download-Link."""
        to_encode = {
            "filepath": filepath,
            "filename": filename,
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=self.DOWNLOAD_TOKEN_EXPIRE_MINUTES),
        }
        return jwt.encode(
            to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
        )

    def decode_download_token(self, token: str) -> dict:
        """Dekodiert und validiert einen Download-Token."""
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
            )
            filepath: str = payload.get("filepath")
            filename: str = payload.get("filename")
            if not filepath or not filename:
                raise HTTPException(status_code=400, detail="Ungültiges Token-Format.")
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Download-Link abgelaufen.")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Ungültiger Download-Link.")

    async def download_pdf(self, pdf_url: str, filename: str) -> str | None:
        """Lädt das PDF herunter und speichert es temporär auf dem Server."""
        os.makedirs("downloads", exist_ok=True)
        filepath = os.path.join("downloads", filename)
        
        # Wichtig: Ein realistischer User-Agent verhindert, dass Hoster blockieren
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        }
        logging.info(f"Attempting to download PDF from: {pdf_url}")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(pdf_url, headers=headers, timeout=20.0) # Timeout leicht erhöht
                
                if response.status_code == 200: # Erfolgreicher Download
                    # Prüfe den Content-Type, um sicherzustellen, dass es wirklich eine PDF ist
                    content_type = response.headers.get("Content-Type", "")
                    if "application/pdf" in content_type:
                        with open(filepath, "wb") as f:
                            f.write(response.content)
                        logging.info(f"Successfully downloaded PDF to: {filepath}")
                        return filepath
                    else:
                        logging.warning(f"Download failed for {pdf_url}: Expected 'application/pdf', got '{content_type}'. Status: {response.status_code}. Response body start: {response.text[:200]}...")
                        return None
                else: # Nicht-200 Statuscode
                    logging.error(f"Download failed for {pdf_url}: HTTP Status {response.status_code}. Response body start: {response.text[:200]}...")
                    return None
            except httpx.HTTPStatusError as e: # Fehlerhafte HTTP-Antwort (z.B. 4xx, 5xx)
                logging.error(f"HTTP Status Error during download from {pdf_url}: {e.response.status_code} - {e.response.text}")
                return None
            except httpx.RequestError as e: # Netzwerkfehler (z.B. Timeout, DNS-Problem)
                logging.error(f"Network Error during download from {pdf_url}: {e}")
                return None
            except Exception as e: # Alle anderen unerwarteten Fehler
                logging.error(f"Unexpected Error during download from {pdf_url}: {e}")
                return None