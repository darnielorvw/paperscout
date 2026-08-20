import asyncio
import io
import logging
import os
import re
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from config import settings
from fastapi import HTTPException

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class DownloadService:
    def __init__(self):
        self.DOWNLOAD_TOKEN_EXPIRE_MINUTES = 5

    async def aclose(self) -> None:
        """Cleanup hook für den Lifespan-Manager."""
        return None

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

    def _sanitize_filename(self, title: str, fallback: str) -> str:
        """Erstellt einen sicheren Dateinamen aus Titel und Fallback."""
        normalized = unicodedata.normalize("NFKD", title or fallback)
        ascii_text = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", ascii_text).strip("._-")
        return cleaned or fallback

    async def _download_pdf_bytes(self, openalex_id: str) -> bytes | None:
        """Lädt eine einzelne PDF-Datei von OpenAlex herunter."""
        clean_id = openalex_id.split("/")[-1]
        download_url = (
            f"https://content.openalex.org/works/{clean_id}.pdf"
            f"?api_key={settings.OPENALEX_API_KEY}"
        )

        headers = {
            "User-Agent": "MyAppName/1.0 (mailto:deine-email@domain.com)",
        }

        logging.info(f"Downloading PDF from OpenAlex: {download_url}")

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(download_url, headers=headers, timeout=30.0)

            if response.status_code != 200:
                logging.error(
                    f"OpenAlex download failed [{response.status_code}]: {response.text[:200]}"
                )
                return None

            content_type = response.headers.get("Content-Type", "")
            if (
                "application/pdf" not in content_type
                and "octet-stream" not in content_type
            ):
                logging.warning(
                    f"Download failed for {download_url}: Expected PDF, got '{content_type}'."
                )
                return None

            return response.content

        except httpx.RequestError as e:
            logging.error(
                f"Network error downloading from OpenAlex ({download_url}): {e}"
            )
            return None
        except Exception as e:
            logging.error(
                f"Unexpected error downloading from OpenAlex ({download_url}): {e}"
            )
            return None

    async def download_pdf_from_openalex(
        self, papers: list[tuple[str, str | None]]
    ) -> bytes | None:
        """Lädt mehrere PDFs parallel über die OpenAlex Content API herunter und gibt sie als ZIP zurück."""
        os.makedirs("downloads", exist_ok=True)

        if not papers:
            return None

        async def fetch_one(openalex_id: str, title: str | None):
            clean_id = openalex_id.split("/")[-1]
            pdf_bytes = await self._download_pdf_bytes(openalex_id)
            return clean_id, title, pdf_bytes

        # Parallel herunterladen
        results = await asyncio.gather(
            *(fetch_one(openalex_id, title) for openalex_id, title in papers),
            return_exceptions=True,
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for result in results:
                if isinstance(result, Exception):
                    logging.warning(f"Download fehlgeschlagen: {result}")
                    continue

                clean_id, title, pdf_bytes = result
                if not pdf_bytes:
                    logging.warning(f"Kein PDF erhalten für {clean_id}")
                    continue

                safe_title = self._sanitize_filename(title, clean_id)
                safe_name = f"{safe_title}.pdf"
                archive.writestr(safe_name, pdf_bytes)
                logging.info(f"Successfully added PDF to ZIP: {safe_name}")

        if buffer.tell() == 0:
            return None

        return buffer.getvalue()
