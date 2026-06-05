import hashlib
import html
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from app.utils.constants import _HAS_OPENPYXL, _HAS_XLSXWRITER, STOPWORDS


def _pick_excel_engine() -> str | None:
    """Bevorzugt xlsxwriter; fällt auf openpyxl zurück; None wenn beides fehlt."""
    if _HAS_XLSXWRITER:
        return "xlsxwriter"
    if _HAS_OPENPYXL:
        return "openpyxl"
    return None

def _stable_sel_key(r: dict, suffix: str) -> str:
    """Erzeugt einen eindeutigen Key für Widgets basierend auf DOI und einem Suffix."""
    # robuste Basis: DOI -> URL -> Titel
    basis = (str(r.get("doi") or "") + "|" +
             str(r.get("url") or "") + "|" +
             str(r.get("title") or "")).lower()
    # kurze, saubere ID
    h = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"sel_card_{h}_{suffix}"

def _chk_key(name: str) -> str:
    return "chk_" + re.sub(r"\W+", "_", name.lower()).strip("_")

TAG_STRIP = re.compile(r"<[^>]+>")
def _clean_text(s: str) -> str:
    s = html.unescape(s or "")
    s = TAG_STRIP.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(abstract|zusammenfassung)\s*[:\-]\s*", "", s, flags=re.I)
    return s

def parse_date_any(s: Optional[str]) -> Optional[str]:
    if not s: return None
    s = s.strip()
    fmts = ["%Y-%m-%d","%Y/%m/%d","%d %B %Y","%B %Y","%Y-%m","%Y"]
    for f in fmts:
        try: return datetime.strptime(s,f).strftime("%Y-%m-%d")
        except Exception: pass
    m=re.search(r"(\d{4})",s)
    return f"{m.group(1)}-01-01" if m else None

def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß\-]{3,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS and not t.isdigit()]

def _top_terms(texts: List[str], n: int = 8) -> List[str]:
    freq: Dict[str, int] = {}
    for t in texts:
        for tok in _tokenize(t):
            freq[tok] = freq.get(tok, 0) + 1
    return [t for t, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:n]]

def _why_relevant(query: str, text: str, max_terms: int = 4) -> str:
    q_terms = set(_tokenize(query))
    if not q_terms:
        return ""
    t_terms = _tokenize(text)
    overlap = [t for t in t_terms if t in q_terms]
    if not overlap:
        return ""
    # Keep order but unique
    seen = set()
    uniq = []
    for t in overlap:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
        if len(uniq) >= max_terms:
            break
    return ", ".join(uniq)

def _safe_parse_date(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None

def _trend_summary(df: pd.DataFrame, recent_days: int = 30) -> Dict[str, Any]:
    if df.empty or "issued" not in df.columns:
        return {}
    dates = [_safe_parse_date(str(d)) for d in df["issued"].dropna().astype(str)]
    dates = [d for d in dates if d]
    if not dates:
        return {}
    ref_date = max(dates)
    recent_start = ref_date - timedelta(days=recent_days)
    prior_start = recent_start - timedelta(days=recent_days)
    recent_mask = df["issued"].astype(str).apply(lambda s: (_safe_parse_date(s) or datetime.min) >= recent_start)
    prior_mask = df["issued"].astype(str).apply(lambda s: prior_start <= (_safe_parse_date(s) or datetime.min) < recent_start)

    def _texts(mask):
        sub = df[mask]
        return (sub.get("abstract", "").fillna("") + " " + sub.get("title", "").fillna("")).tolist()

    recent_terms = _top_terms(_texts(recent_mask), n=8)
    prior_terms = _top_terms(_texts(prior_mask), n=8)
    emerging = [t for t in recent_terms if t not in prior_terms][:6]
    return {
        "recent_start": recent_start.date().isoformat(),
        "recent_end": ref_date.date().isoformat(),
        "recent_terms": recent_terms,
        "prior_terms": prior_terms,
        "emerging": emerging,
    }

def dedup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen=set();out=[]
    for a in items:
        d=(a.get("doi") or "").lower()
        if d in seen: continue
        seen.add(d); out.append(a)
    return out

def _to_http(u: str) -> str:
    if not isinstance(u, str): return ""
    u = u.strip()
    if u.startswith("http://doi.org/"): return "https://" + u[len("http://"):]
    if u.startswith("http"): return u
    if u.startswith("10."): return "https://doi.org/" + u
    return u

def _cosine_sim(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    num = sum(a * b for a, b in zip(v1, v2))
    den1 = sum(a * a for a in v1) ** 0.5
    den2 = sum(b * b for b in v2) ** 0.5
    if den1 == 0 or den2 == 0:
        return 0.0
    return num / (den1 * den2)

def add_signal_scores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "issued" not in df.columns:
        return df

    dates = [_safe_parse_date(str(x)) for x in df["issued"].astype(str).tolist()]
    valid_dates = [d for d in dates if d]
    if not valid_dates:
        return df

    ref_date = max(valid_dates)
    days_ago = [(ref_date - d).days if d else None for d in dates]

    denominator = max(max([d for d in days_ago if d is not None] or [0]), 1)

    recency_scores = []
    for d in days_ago:
        if d is None: recency_scores.append(0.0)
        else: recency_scores.append(round((1 - (d / denominator)) * 100, 1))

    df["days_ago"] = days_ago
    if "relevance_score" in df.columns:
        rel = pd.to_numeric(df["relevance_score"], errors="coerce").fillna(0.0)
        df["signal_score"] = (rel * 0.6 + pd.Series(recency_scores, index=df.index) * 0.4).round(1)
    else:
        df["signal_score"] = pd.Series(recency_scores, index=df.index).round(1)

    return df

def extract_abstract_from_html_simple(html_text: str) -> Optional[str]:
    if not html_text: return None
    m = re.search(r'<meta[^>]+name=["\']citation_abstract["\'][^>]+content=["\']([^"\']+)["\']', html_text, flags=re.I)
    if m: return _clean_text(m.group(1))
    m = re.search(r'<meta[^>]+name=["\']dc\.description["\'][^>]+content=["\']([^"\']+)["\']', html_text, flags=re.I)
    if m: return _clean_text(m.group(1))
    m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html_text, flags=re.I)
    if m: return _clean_text(m.group(1))

    m = re.search(r'<div[^>]+class=["\'][^"\']*hlFld-Abstract[^"\']*["\'][^>]*>(.*?)</div>', html_text, flags=re.I|re.S)
    if m: return _clean_text(m.group(1))
    m = re.search(r'<section[^>]+class=["\'][^"\']*abstract[^"\']*["\'][^>]*>(.*?)</section>', html_text, flags=re.I|re.S)
    if m: return _clean_text(m.group(1))
    m = re.search(r'<div[^>]+id=["\']abstract["\'][^>]*>(.*?)</div>', html_text, flags=re.I|re.S)
    if m: return _clean_text(m.group(1))
    return None