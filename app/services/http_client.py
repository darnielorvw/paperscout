import os
from typing import Dict, Optional

import httpx
import streamlit as st


def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    mailto = os.getenv("CROSSREF_MAILTO") or "you@example.com"
    base = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
        "From": mailto,
    }
    if extra:
        base.update(extra)
    return base

def _proxy_dict() -> Optional[dict]:
    p = (st.session_state.get("proxy_url") or
         os.getenv("PAPERSCOUT_PROXY") or "").strip()
    if not p:
        return None
    return {"http": p, "https": p}

def _http_client(timeout: float, headers: dict | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers=headers or _headers(),
        follow_redirects=True,
        http2=False,
        proxies=_proxy_dict(),
        cookies=httpx.Cookies(),
    )

def fetch_html(url: str, timeout: float = 25.0) -> Optional[str]:
    try:
        base_headers = _headers({
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        })
        with _http_client(timeout=timeout, headers=base_headers) as c:
            r = c.get(url)
            if r.status_code == 403:
                domain_ref = None # Domain-spezifische Referrer als Retry
                if "wiley.com" in url: domain_ref = "https://onlinelibrary.wiley.com/"
                elif "sagepub.com" in url: domain_ref = "https://journals.sagepub.com/"
                elif "sciencedirect.com" in url: domain_ref = "https://www.sciencedirect.com/"
                elif "journals.aom.org" in url: domain_ref = "https://journals.aom.org/"
                if domain_ref: r = c.get(url, headers=_headers({"Referer": domain_ref}))
            if r.status_code in (403, 429):
                alt_headers = dict(base_headers); alt_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117 Safari/537.36"
                r = c.get(url, headers=alt_headers)
            r.raise_for_status()
            return r.text or ""
    except Exception: return None