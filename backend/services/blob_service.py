import base64
import hashlib
import hmac
import json
import logging
import re
import time
from typing import List
from urllib.parse import urlparse

import httpx

from config import settings

logger = logging.getLogger(__name__)

# --- Vercel Blob --------------------------------------------------------------
# Paper PDFs are uploaded by the admin's browser straight to Vercel Blob, since
# a Vercel function only accepts request bodies up to 4.5 MB. The backend only
# hands out a short-lived client token for one pathname, the same way
# `generateClientTokenFromReadWriteToken` in @vercel/blob does it, and stores the
# resulting URL once the upload is done.

_BLOB_API_URL = "https://vercel.com/api/blob"
_BLOB_API_VERSION = "13"
_PUBLIC_HOST_SUFFIX = ".public.blob.vercel-storage.com"


def is_configured() -> bool:
    return bool(settings.BLOB_READ_WRITE_TOKEN)


def _store_id(read_write_token: str) -> str:
    # Tokens look like "vercel_blob_rw_<storeId>_<secret>".
    parts = read_write_token.split("_")
    return parts[3] if len(parts) > 3 else ""


def paper_pathname(article_id: str) -> str:
    """The blob pathname for a paper's PDF. Vercel appends a random suffix."""
    return f"papers/{re.sub(r'[^A-Za-z0-9._-]+', '_', article_id)}.pdf"


def create_client_token(
    pathname: str,
    *,
    allowed_content_types: List[str],
    maximum_size_in_bytes: int,
    valid_seconds: int = 600,
) -> str:
    """A client token that lets a browser upload exactly one blob to `pathname`."""
    read_write_token = settings.BLOB_READ_WRITE_TOKEN
    store_id = _store_id(read_write_token)
    if not store_id:
        raise ValueError("BLOB_READ_WRITE_TOKEN is missing or invalid.")

    payload = base64.b64encode(
        json.dumps(
            {
                "pathname": pathname,
                "allowedContentTypes": allowed_content_types,
                "maximumSizeInBytes": maximum_size_in_bytes,
                "addRandomSuffix": True,
                "validUntil": int((time.time() + valid_seconds) * 1000),
            },
            separators=(",", ":"),
        ).encode()
    ).decode()
    signature = hmac.new(read_write_token.encode(), payload.encode(), hashlib.sha256).hexdigest()
    secured = base64.b64encode(f"{signature}.{payload}".encode()).decode()
    return f"vercel_blob_client_{store_id}_{secured}"


def is_uploaded_blob_url(url: str, pathname: str) -> bool:
    """Whether `url` is a public blob uploaded to `pathname` (plus random suffix)."""
    parsed = urlparse(url)
    stem = pathname.removesuffix(".pdf")
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and parsed.hostname.endswith(_PUBLIC_HOST_SUFFIX)
        and parsed.path.startswith(f"/{stem}-")
        and parsed.path.endswith(".pdf")
    )


async def delete_blob(url: str) -> None:
    """Deletes a blob, e.g. a PDF that was replaced. Failures are only logged."""
    if not is_configured():
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{_BLOB_API_URL}/delete",
                json={"urls": [url]},
                headers={
                    "authorization": f"Bearer {settings.BLOB_READ_WRITE_TOKEN}",
                    "x-api-version": _BLOB_API_VERSION,
                },
            )
            response.raise_for_status()
    except Exception as e:
        logger.error(f"Deleting blob {url} failed: {e}")
