import os

import httpx
from fastapi import HTTPException


class DownloadService:
    def __init__(self):
        self.unpaywall_url = "https://api.unpaywall.org/v2/"

    async def get_pdf_download_url(self, doi: str, email: str) -> str:
        """Fragt Unpaywall nach der direkten, legalen PDF-URL für eine DOI."""
        clean_doi = doi.replace("https://doi.org/", "")
        url = f"{self.unpaywall_url}{clean_doi}?email={email}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                # Suche nach dem besten Open-Access-Link (bevorzugt PDF)
                best_location = data.get("best_oa_location", {})
                if best_location:
                    return best_location.get("url_for_pdf") or best_location.get("url")
            return None

    async def download_pdf(self, pdf_url: str, filename: str) -> str:
        """Lädt das PDF herunter und speichert es temporär auf dem Server."""
        os.makedirs("downloads", exist_ok=True)
        filepath = os.path.join("downloads", filename)
        
        # Wichtig: Ein realistischer User-Agent verhindert, dass Hoster blockieren
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(pdf_url, headers=headers, timeout=15.0)
                if response.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    return filepath
            except Exception as e:
                print(f"Download fehlgeschlagen: {e}")
            return None