# UI-Update: Modernes Design mit CSS-Karten und Tabs.
# LOGIC-RESTORE: API-Key-Logik exakt wie in Version 6 (Hard Environment Set).
# FEATURE: Zentrale Render-Funktion für konsistente Karten (Relevanz, Cluster, Hauptliste).
# FEATURE: Checkboxen und Klapp-Abstracts überall verfügbar.
# FIX: Synchronisierung der Auswahl.

import os
from datetime import date, datetime, timedelta
from io import BytesIO
from math import ceil
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

# Importiere Module aus der neuen Struktur
from app.config import setup_smtp_from_secrets_or_env
from app.services.crossref_service import (fetch_crossref_any,
                                           fetch_sciencedirect_abstract)
from app.services.email_service import send_doi_email
from app.services.http_client import fetch_html
from app.services.openai_service import (_get_embedding,
                                         ai_extract_metadata_from_html,
                                         ai_generate_digest,
                                         build_clusters_openai,
                                         compute_relevance_scores,
                                         compute_relevance_scores_multi)
from app.services.semantic_openalex_service import (fetch_openalex,
                                                    fetch_semantic)
from app.ui.components import render_row_ui, section_card, toggle_doi
from app.ui.styles import apply_custom_styles
from app.utils.constants import ALT_ISSN, JOURNAL_ISSN
from app.utils.data_processing import (_chk_key, _clean_text,
                                       _pick_excel_engine, _safe_parse_date,
                                       _trend_summary, _why_relevant,
                                       add_signal_scores, dedup)

# ==========================================
# 1. API-KEY LOGIK (WIEDERHERGESTELLT VON V6)
# ==========================================
# Dieser Block muss ganz oben stehen, bevor irgendwelche Funktionen definiert werden.
# Er zwingt den Secret-Key in die Umgebungsvariablen, genau wie im alten Code.
# ------------------------------------------
try:
    if "PAPERSCOUT_OPENAI_API_KEY" in st.secrets:
        key_val = str(st.secrets["PAPERSCOUT_OPENAI_API_KEY"]).strip()
        # Entferne eventuelle Anführungszeichen, falls sie fälschlicherweise im Wert stehen
        key_val = key_val.strip('"').strip("'")
        if key_val:
            os.environ["PAPERSCOUT_OPENAI_API_KEY"] = key_val
            # WICHTIG: Auch die Standard-Variable setzen für Libraries
            os.environ["OPENAI_API_KEY"] = key_val
except Exception:
    pass

# Fallback: Falls der User "OPENAI_API_KEY" direkt in den Secrets nutzt
try:
    if "OPENAI_API_KEY" in st.secrets:
        key_val = str(st.secrets["OPENAI_API_KEY"]).strip()
        key_val = key_val.strip('"').strip("'")
        if key_val:
            os.environ["OPENAI_API_KEY"] = key_val
            os.environ["PAPERSCOUT_OPENAI_API_KEY"] = key_val
except Exception: pass
# ==========================================

setup_smtp_from_secrets_or_env() # Konfiguriert SMTP aus Secrets/Env

# =========================
# App-Konfiguration
# =========================
st.set_page_config(page_title="paperscout UI", layout="wide")

# ==========================================

# =========================
# Hauptpipeline
# =========================
def collect_all(
    journal: str,
    since: str,
    until: str,
    rows: int,
    ai_model: str,
    topic_query: Optional[str] = None,
    options: Optional[Dict[str, bool]] = None,
) -> List[Dict[str, Any]]:
    opts = {
        "use_semantic": True,
        "use_openalex": True,
        "use_html": True,
        "use_ai": True,
        "use_scidir": True,
    }
    if options:
        opts.update(options)
    issn = JOURNAL_ISSN.get(journal)
    if not issn:
        return []

    base = fetch_crossref_any(journal, issn, since, until, rows, query=topic_query)
    out: List[Dict[str, Any]] = []

    if not base:
        return []

    for rec in base:
        if rec.get("abstract"):
            rec["abstract_source"] = "crossref"
            out.append(rec)
            continue

        doi = rec.get("doi", "")

        for fn in (fetch_semantic, fetch_openalex):
            if fn == fetch_semantic and not opts.get("use_semantic", True):
                continue
            if fn == fetch_openalex and not opts.get("use_openalex", True):
                continue
            if not doi:
                break
            data = fn(doi)
            if data and data.get("abstract"):
                rec["abstract_source"] = "semantic" if fn == fetch_semantic else "openalex"
                for k in ["title", "authors", "journal", "issued", "abstract", "url"]:
                    if not rec.get(k):
                        rec[k] = data.get(k)
                break

        if not rec.get("abstract") and opts.get("use_scidir", True):
            is_sd_url = "sciencedirect.com" in (rec.get("url","") or "")
            is_sd_journal = (issn == "1048-9843") 
            
            if is_sd_url or is_sd_journal:
                abs_text = fetch_sciencedirect_abstract(rec.get("url") or rec.get("doi",""))
                if abs_text:
                    rec["abstract"] = abs_text
                    rec["abstract_source"] = "sciencedirect"

        if not rec.get("abstract") and rec.get("url") and opts.get("use_html", True):
            html_text = fetch_html(rec["url"])
            if html_text:
                abs_simple = extract_abstract_from_html_simple(html_text)
                if abs_simple:
                    rec["abstract"] = abs_simple
                    rec["abstract_source"] = "html"

        if not rec.get("abstract") and rec.get("url") and opts.get("use_ai", True):
            html_text = fetch_html(rec["url"])
            if html_text:
                ai = ai_extract_metadata_from_html(html_text, ai_model)
                if ai:
                    for k in ["title", "authors", "journal", "issued", "abstract", "doi", "url"]:
                        if not rec.get(k) and ai.get(k):
                            rec[k] = ai.get(k)
                    if ai.get("abstract"):
                        rec["abstract_source"] = "ai"

        if not rec.get("abstract"):
            rec["abstract_source"] = rec.get("abstract_source") or "none"

        out.append(rec)

    for r in out:
        d = (r.get("doi") or "").strip()
        if d.startswith("10."):
            r["doi"] = f"https://doi.org/{d}"
        elif d.startswith("http://doi.org/"):
            r["doi"] = "https://" + d[len("http://"):]
        if not r.get("url"):
            r["url"] = r.get("doi", "")

    return out

def dedup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen=set();out=[]
    for a in items:
        d=(a.get("doi") or "").lower()
        if d in seen: continue
        seen.add(d); out.append(a)
    return out

# =========================
# Themencluster mit OpenAI-Embeddings (ohne sklearn)
# =========================
def _get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    # KEY-CHANGE: Hier wieder direkt auf os.environ zugreifen
    key=os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        # Text etwas begrenzen
        text_short = text[:4000]
        resp = client.embeddings.create(
            model=model,
            input=text_short
        )
        return list(resp.data[0].embedding)
    except Exception:
        return []

def _kmeans(vectors: List[List[float]], k: int, max_iter: int = 20) -> List[int]:
    import random
    if not vectors or k <= 0:
        return []

    n = len(vectors)
    k = max(1, min(k, n))

    # Zufällige Startzentren
    centers = random.sample(vectors, k)

    labels = [0] * n
    for _ in range(max_iter):
        # Zuweisung
        changed = False
        for i, v in enumerate(vectors):
            dists = [sum((vi - ci) ** 2 for vi, ci in zip(v, c)) for c in centers]
            new_label = dists.index(min(dists))
            if new_label != labels[i]:
                labels[i] = new_label
                changed = True

        if not changed:
            break

        # Neue Zentren
        new_centers: List[List[float]] = []
        for cluster_id in range(k):
            members = [vectors[i] for i, lab in enumerate(labels) if lab == cluster_id]
            if not members:
                new_centers.append(random.choice(vectors))
                continue
            dim = len(members[0])
            avg = [sum(vec[d] for vec in members) / len(members) for d in range(dim)]
            new_centers.append(avg)
        centers = new_centers

    return labels

def _ai_name_cluster(examples: List[str], model: str = "gpt-4o-mini") -> Optional[str]:
    # KEY-CHANGE: Hier wieder direkt auf os.environ zugreifen
    key=os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None

    # Nur ein paar Beispiele und pro Text begrenzen, damit der Prompt klein bleibt
    snippets = [(t or "").strip()[:600] for t in examples[:5] if t and t.strip()]
    if not snippets:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)

        joined = "\n\n---\n\n".join(snippets)

        system_msg = (
            "Du bist eine wissenschaftliche Assistentin, die Themencluster aus "
            "Forschungsartikeln benennt. "
            "Deine Aufgabe ist es, einen sehr kurzen, prägnanten Titel (3–6 Wörter) "
            "für das Thema zu vergeben. Schreibe auf Deutsch, ohne Anführungszeichen."
        )
        user_msg = (
            "Hier sind einige Abstracts oder Titel von Artikeln, die zum selben Themencluster gehören:\n\n"
            f"{joined}\n\n"
            "Gib mir bitte NUR einen kurzen, sprechenden Namen für das Thema (3–6 Wörter, Deutsch), "
            "ohne Anführungszeichen, ohne zusätzliche Erklärung."
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
        label = (resp.choices[0].message.content or "").strip()
        label = re.sub(r'^[\"“”]+|[\"“”]+$', '', label).strip()
        return label or None
    except Exception:
        return None

def ai_generate_digest(records: List[Dict[str, Any]], model: str = "gpt-4o-mini", lang: str = "Deutsch") -> Optional[str]:
    key = os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key or not records:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        items = []
        for r in records[:12]:
            title = _clean_text(str(r.get("title","")))
            journal = _clean_text(str(r.get("journal","")))
            issued = _clean_text(str(r.get("issued","")))
            abstract = _clean_text(str(r.get("abstract","")))[:900]
            items.append(f"TITLE: {title}\nJOURNAL: {journal}\nDATE: {issued}\nABSTRACT: {abstract}")
        payload = "\n\n---\n\n".join(items)
        system_msg = (
            "You are a research analyst who produces concise, high-signal digests of recent papers."
        )
        user_msg = (
            f"Language: {lang}. Create a digest with these sections:\n"
            "1) Executive summary (4-6 bullets)\n"
            "2) Emerging themes (3 bullets)\n"
            "3) Open questions (3 bullets)\n"
            "4) Recommended papers (5 bullets, include title + one-line why)\n\n"
            f"PAPERS:\n{payload}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None


def build_clusters_openai(df: pd.DataFrame, k: int = 5, min_docs: int = 5) -> Optional[List[Dict[str, Any]]]:
    if df.empty:
        return None

    texts: List[str] = []
    indices: List[int] = []

    for idx, row in df.iterrows():
        abstract = str(row.get("abstract", "") or "").strip()
        title = str(row.get("title", "") or "").strip()
        text = abstract if len(abstract) > 40 else title
        if len(text) < 20:
            continue
        texts.append(text)
        indices.append(idx)

    if len(texts) < min_docs:
        return None

    embeddings: List[List[float]] = []
    clean_indices: List[int] = []
    clean_texts: List[str] = []

    for txt, idx in zip(texts, indices):
        emb = _get_embedding(txt)
        if emb:
            embeddings.append(emb)
            clean_indices.append(idx)
            clean_texts.append(txt)

    if len(embeddings) < min_docs:
        return None

    k = max(2, min(k, len(embeddings)))
    labels = _kmeans(embeddings, k=k)

    clusters: List[Dict[str, Any]] = []
    for cluster_id in range(k):
        member_positions = [i for i, lab in enumerate(labels) if lab == cluster_id]
        if not member_positions:
            continue
        member_indices = [clean_indices[i] for i in member_positions]
        sample_text = clean_texts[member_positions[0]]
        clusters.append(
            {
                "cluster_id": cluster_id,
                "label": f"Cluster {cluster_id+1}",
                "sample_text": (sample_text[:240] + "...") if len(sample_text) > 240 else sample_text,
                "indices": member_indices,
            }
        )

    if not clusters:
        return None

    # KEY-CHANGE: Hier wieder direkt auf os.environ zugreifen
    key=os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if key:
        # Mapping Index -> Text, damit wir pro Cluster die Beispiele holen können
        idx_to_text = {idx: txt for idx, txt in zip(clean_indices, clean_texts)}

        for cluster in clusters:
            ex_texts = [idx_to_text.get(i, "") for i in cluster.get("indices", [])]
            ex_texts = [t for t in ex_texts if t]
            if not ex_texts:
                continue
            ai_label = _ai_name_cluster(ex_texts)
            if ai_label:
                cluster["label"] = f"Cluster {cluster['cluster_id']+1}: {ai_label}"
                
    return clusters

# =========================
# Relevanz-Rating mit OpenAI-Embeddings (Berechnung & UI)
# =========================
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

def compute_relevance_scores(
    df: pd.DataFrame,
    query_text: str,
    min_text_len: int = 30,
    model: str = "text-embedding-3-small",
) -> Optional[pd.Series]:
    query_text = (query_text or "").strip()
    if not query_text:
        return None

    q_emb = _get_embedding(query_text, model=model)
    if not q_emb:
        return None

    scores: Dict[int, float] = {}
    for idx, row in df.iterrows():
        abstract = str(row.get("abstract", "") or "").strip()
        title = str(row.get("title", "") or "").strip()
        text = abstract if len(abstract) >= min_text_len else title
        
        if len(text) < min_text_len:
            scores[idx] = 0.0
            continue

        emb = _get_embedding(text, model=model)
        if not emb:
            scores[idx] = 0.0
            continue

        sim = _cosine_sim(q_emb, emb)
        sim = max(sim, 0.0)
        scores[idx] = round(sim * 100, 1)

    return pd.Series(scores, name="relevance_score") if scores else None

def compute_relevance_scores_multi(
    df: pd.DataFrame,
    queries: List[Dict[str, Any]],
    min_text_len: int = 30,
    model: str = "text-embedding-3-small",
) -> Optional[pd.Series]:
    clean = [(q.get("text","").strip(), float(q.get("weight", 1.0))) for q in queries if q.get("text","").strip()]
    if not clean:
        return None
    # Weighted query embedding
    emb_sum = None
    weight_sum = 0.0
    for text, w in clean:
        emb = _get_embedding(text, model=model)
        if not emb:
            continue
        if emb_sum is None:
            emb_sum = [0.0] * len(emb)
        for i, v in enumerate(emb):
            emb_sum[i] += v * w
        weight_sum += w
    if not emb_sum or weight_sum == 0:
        return None
    q_emb = [v / weight_sum for v in emb_sum]

    scores: Dict[int, float] = {}
    for idx, row in df.iterrows():
        abstract = str(row.get("abstract", "") or "").strip()
        title = str(row.get("title", "") or "").strip()
        text = abstract if len(abstract) >= min_text_len else title
        if len(text) < min_text_len:
            scores[idx] = 0.0
            continue
        emb = _get_embedding(text, model=model)
        if not emb:
            scores[idx] = 0.0
            continue
        sim = _cosine_sim(q_emb, emb)
        sim = max(sim, 0.0)
        scores[idx] = round(sim * 100, 1)
    return pd.Series(scores, name="relevance_score") if scores else None

def add_signal_scores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "issued" not in df.columns:
        return df

    dates = [_safe_parse_date(str(x)) for x in df["issued"].astype(str).tolist()]
    valid_dates = [d for d in dates if d is not None]
    if not valid_dates:
        return df

    ref_date = max(valid_dates)
    days_ago = [(ref_date - d).days if d is not None else None for d in dates]

    denominator = max(max([d for d in days_ago if d is not None] or [0]), 1)

    recency_scores = []
    for d in days_ago:
        if d is None:
            recency_scores.append(0.0)
        else:
            recency_scores.append(round((1 - (d / denominator)) * 100, 1))

    df["days_ago"] = days_ago
    if "relevance_score" in df.columns:
        rel = pd.to_numeric(df["relevance_score"], errors="coerce").fillna(0.0)
        df["signal_score"] = (rel * 0.6 + pd.Series(recency_scores, index=df.index) * 0.4).round(1)
    else:
        df["signal_score"] = pd.Series(recency_scores, index=df.index).round(1)

    return df




# =========================
# E-Mail Versand (SMTP) - JETZT MIT HTML-DESIGN
# =========================
def send_doi_email(
    to_email: str,
    records: List[Dict[str, Any]],
    sender_display: Optional[str] = None
) -> tuple[bool, str]:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "587"))
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    sender_addr = os.getenv("EMAIL_FROM") or user
    default_name = os.getenv("EMAIL_SENDER_NAME", "paperscout")
    use_tls = os.getenv("EMAIL_USE_TLS", "true").lower() in ("1","true","yes","y")
    use_ssl = os.getenv("EMAIL_USE_SSL", "false").lower() in ("1","true","yes","y")

    if not (host and port and sender_addr and user and password):
        return False, "SMTP nicht konfiguriert."

    display_name = (sender_display or "").strip() or default_name

    # --- HTML Tabellen-Inhalt generieren (modernes Design) ---
    table_rows = ""
    for i, rec in enumerate(records):
        title = html.escape(str(rec.get("title", "(ohne Titel)")))
        authors = html.escape(str(rec.get("authors", "Autor:innen unbekannt")))
        journal = html.escape(str(rec.get("journal", "Journal unbekannt")))
        issued = html.escape(str(rec.get("issued", "")))
        doi_url = str(rec.get("doi", ""))
        
        table_rows += f"""
        <tr>
            <td style="padding: 10px 0;">
                <div style="border:1px solid #e7e7ec; border-radius:14px; padding:16px; background:#ffffff;">
                    <div style="font-weight:700; color:#101217; font-size:16px; margin-bottom:6px;">{title}</div>
                    <div style="font-size:13px; color:#3a3f4b; margin-bottom:8px;">{authors}</div>
                    <div style="font-size:12px; color:#6a7282; margin-bottom:12px;">
                        <span style="font-weight:600;">{journal}</span> {f'· {issued}' if issued else ''}
                    </div>
                    <a href="{doi_url}" style="display:inline-block; padding:8px 12px; border-radius:999px; background:#ff6b35; color:#ffffff; text-decoration:none; font-size:12px; font-weight:700;">
                        DOI öffnen
                    </a>
                </div>
            </td>
        </tr>
        """

    # --- Das HTML-Template ---
    html_body = f"""
    <html>
    <body style="margin:0; padding:0; background:#f7f3ef; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color:#101217;">
        <div style="max-width: 720px; margin: 24px auto; padding: 0 16px;">
            <div style="border-radius: 18px; overflow: hidden; border:1px solid #e7e7ec; background:#ffffff;">
                <div style="padding: 20px; background: linear-gradient(135deg, #ff6b35, #ff9f2e); color: #ffffff;">
                    <div style="font-size: 20px; font-weight: 800; letter-spacing:-0.02em;">paperscout</div>
                    <div style="font-size: 12px; opacity:0.9;">Research Digest · {len(records)} Artikel</div>
                </div>
                <div style="padding: 20px;">
                    <p style="margin:0 0 10px 0;">Hallo,</p>
                    <p style="margin:0 0 14px 0; color:#3a3f4b;">
                        hier ist deine kuratierte Übersicht der ausgewählten Artikel.
                    </p>
                    <div style="font-size:12px; color:#6a7282; margin-bottom:12px;">
                        Ausgewählt von: <strong>{display_name}</strong>
                    </div>
                    <table style="width:100%; border-collapse: collapse;">
                        {table_rows}
                    </table>
                    <div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid #eeeeee; font-size: 11px; color: #8b92a1;">
                        Gesendet via paperscout · {datetime.now().strftime('%d.%m.%Y %H:%M')}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    # E-Mail Objekt erstellen
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[paperscout] {len(records)} Artikel — {display_name}"
    msg["From"] = formataddr((display_name, sender_addr))
    msg["To"] = to_email

    # Plaintext-Fallback für alte E-Mail-Clients
    text_fallback = f"Hallo,\n\nhier sind {len(records)} Artikel für dich.\n(Bitte HTML-Ansicht aktivieren für das volle Design.)"
    
    msg.attach(MIMEText(text_fallback, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                server.login(user, password)
                server.sendmail(sender_addr, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(user, password)
                server.sendmail(sender_addr, [to_email], msg.as_string())
        return True, "E-Mail mit neuem Design gesendet."
    except Exception as e:
        return False, f"E-Mail Versand fehlgeschlagen: {e}"
# =========================
# =========================
# NEUE UI (v3) - JETZT MIT DARK MODE
# =========================
# =========================
st.markdown(
    """
    <style>
    :root {
        --ps-bg: radial-gradient(1100px 600px at 8% -10%, #fff1d6 0%, rgba(255,241,214,0.0) 60%),
                 radial-gradient(900px 600px at 92% 0%, #e2f1ff 0%, rgba(226,241,255,0.0) 60%),
                 linear-gradient(180deg, #fff9f2 0%, #f9fbff 50%, #fffdf8 100%);
        --ps-ink: #0b1b3a;
        --ps-ink-2: #122a55;
        --ps-ink-3: #1d3a6e;
        --ps-accent: #cb2f98;
        --ps-accent-2: #5e3de3;
        --ps-accent-text: #9a1f76;
        --ps-link: #0f53d1;
        --ps-focus: #ffb703;
        --ps-on-accent: #ffffff;
        --ps-on-accent-2: #ffffff;
        --ps-card: rgba(255,255,255,0.96);
        --ps-card-border: rgba(11,27,58,0.10);
        --ps-shadow: 0 14px 30px rgba(11,27,58,0.12);
        --ps-control-bg: rgba(255,255,255,0.96);
        --ps-control-bg-hover: rgba(255,255,255,1.0);
        --ps-control-border: rgba(12,42,96,0.28);
        --ps-detail-bg: rgba(242,248,255,0.92);
        --ps-nav-bg: rgba(255,255,255,0.95);
        --ps-hero-start: rgba(255,255,255,0.92);
        --ps-hero-end: rgba(238,248,255,0.82);
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --ps-bg: radial-gradient(1150px 680px at 14% -8%, #3e2b8f 0%, rgba(62,43,143,0.0) 58%),
                     radial-gradient(980px 660px at 88% 0%, #1b4d98 0%, rgba(27,77,152,0.0) 60%),
                     linear-gradient(180deg, #15193e 0%, #1b1f4c 50%, #131736 100%);
            --ps-ink: #f7f8ff;
            --ps-ink-2: #dbe1ff;
            --ps-ink-3: #bec8ff;
            --ps-accent: #cf2ca1;
            --ps-accent-2: #5a38e2;
            --ps-accent-text: #ff7cdf;
            --ps-link: #7edbff;
            --ps-focus: #ffd86a;
            --ps-on-accent: #f9fbff;
            --ps-on-accent-2: #ffffff;
            --ps-card: rgba(26,30,79,0.92);
            --ps-card-border: rgba(133,173,255,0.48);
            --ps-shadow: 0 18px 38px rgba(14,11,44,0.62);
            --ps-control-bg: rgba(31,35,89,0.9);
            --ps-control-bg-hover: rgba(40,46,109,0.95);
            --ps-control-border: rgba(141,190,255,0.56);
            --ps-detail-bg: rgba(34,39,97,0.82);
            --ps-nav-bg: rgba(22,27,70,0.96);
            --ps-hero-start: rgba(60,42,141,0.93);
            --ps-hero-end: rgba(193,46,151,0.66);
        }
    }
    html[data-theme="dark"] {
        --ps-bg: radial-gradient(1150px 680px at 14% -8%, #3e2b8f 0%, rgba(62,43,143,0.0) 58%),
                 radial-gradient(980px 660px at 88% 0%, #1b4d98 0%, rgba(27,77,152,0.0) 60%),
                 linear-gradient(180deg, #15193e 0%, #1b1f4c 50%, #131736 100%);
        --ps-ink: #f7f8ff;
        --ps-ink-2: #dbe1ff;
        --ps-ink-3: #bec8ff;
        --ps-accent: #cf2ca1;
        --ps-accent-2: #5a38e2;
        --ps-accent-text: #ff7cdf;
        --ps-link: #7edbff;
        --ps-focus: #ffd86a;
        --ps-on-accent: #f9fbff;
        --ps-on-accent-2: #ffffff;
        --ps-card: rgba(26,30,79,0.92);
        --ps-card-border: rgba(133,173,255,0.48);
        --ps-shadow: 0 18px 38px rgba(14,11,44,0.62);
        --ps-control-bg: rgba(31,35,89,0.9);
        --ps-control-bg-hover: rgba(40,46,109,0.95);
        --ps-control-border: rgba(141,190,255,0.56);
        --ps-detail-bg: rgba(34,39,97,0.82);
        --ps-nav-bg: rgba(22,27,70,0.96);
        --ps-hero-start: rgba(60,42,141,0.93);
        --ps-hero-end: rgba(193,46,151,0.66);
    }
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Manrope:wght@400;500;600&display=swap');
    html, body, [class*="stApp"] {
        background: var(--ps-bg);
        color: var(--ps-ink);
        font-family: 'Manrope', sans-serif;
        line-height: 1.55;
    }
    h1, h2, h3, h4, h5 {
        font-family: 'Space Grotesk', sans-serif;
        letter-spacing: -0.02em;
    }
    a, .stMarkdown a {
        color: var(--ps-link);
        text-decoration: underline;
        text-underline-offset: 2px;
        text-decoration-thickness: 1.5px;
    }
    a:hover, .stMarkdown a:hover {
        color: var(--ps-accent-text);
    }
    *:focus-visible {
        outline: 3px solid var(--ps-focus) !important;
        outline-offset: 2px !important;
        border-radius: 8px;
    }
    .ps-hero {
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        background: linear-gradient(135deg, var(--ps-hero-start), var(--ps-hero-end));
        border: 1px solid var(--ps-card-border);
        box-shadow: var(--ps-shadow);
        margin-bottom: 1rem;
    }
    .ps-hero-title {
        font-size: 2rem;
        font-weight: 700;
        margin: 0 0 0.2rem 0;
    }
    .ps-hero-sub {
        color: var(--ps-ink-2);
        font-size: 1rem;
        margin: 0;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
    }
    .stButton > button {
        border-radius: 12px;
        border: 1px solid var(--ps-control-border);
        background: var(--ps-control-bg);
        color: var(--ps-ink);
        box-shadow: 0 8px 18px rgba(6,34,88,0.2);
        transition: transform 0.12s ease, box-shadow 0.12s ease, background 0.12s ease;
        font-weight: 600;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        background: var(--ps-control-bg-hover);
        box-shadow: 0 12px 24px rgba(6,34,88,0.28);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--ps-accent), var(--ps-accent-2));
        color: var(--ps-on-accent);
        border: 1px solid rgba(176,147,255,0.66);
        box-shadow: 0 12px 24px rgba(95,56,226,0.35);
    }
    .stTextInput input, .stTextArea textarea, .stNumberInput input, .stSelectbox select, .stMultiSelect div {
        border-radius: 12px !important;
        border: 1px solid var(--ps-control-border) !important;
        background: var(--ps-control-bg) !important;
        color: var(--ps-ink) !important;
    }
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder,
    .stNumberInput input::placeholder {
        color: var(--ps-ink-3) !important;
        opacity: 1 !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--ps-ink) !important;
        border-bottom: 3px solid var(--ps-accent-text) !important;
    }
    /* Checkbox labels (mobile-safe, BaseWeb) */
    div[data-baseweb="checkbox"] * {
        color: var(--ps-ink) !important;
    }
    div[data-baseweb="checkbox"] label span {
        color: var(--ps-ink) !important;
    }
    @media (prefers-color-scheme: dark) {
        div[data-baseweb="checkbox"] * {
            color: var(--ps-ink) !important;
        }
    }
    html[data-theme="dark"] div[data-baseweb="checkbox"] * {
        color: var(--ps-ink) !important;
    }
    .stExpander {
        border-radius: 14px;
        border: 1px solid var(--ps-card-border);
        background: var(--ps-card);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="ps-hero">
        <div class="ps-hero-title">🕵🏻‍♀️ Dein paperscout</div>
        <p class="ps-hero-sub">Frische Forschungsartikel, kuratiert in wenigen Sekunden.</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Init Session State für Auswahl
if "selected_dois" not in st.session_state:
    st.session_state["selected_dois"] = set()
if "saved_searches" not in st.session_state:
    st.session_state["saved_searches"] = []
if "collections" not in st.session_state:
    st.session_state["collections"] = {}
if "last_run_df" not in st.session_state:
    st.session_state["last_run_df"] = None
if "embedding_cache" not in st.session_state:
    st.session_state["embedding_cache"] = {}

# --- Command Center (ohne Tabs) ---
journals = sorted(JOURNAL_ISSN.keys())
today = date.today()

# --- Apply saved search before widgets are created ---
if "preset_to_apply" in st.session_state:
    preset_name = st.session_state.pop("preset_to_apply")
    preset = next((p for p in st.session_state.get("saved_searches", []) if p["name"] == preset_name), None)
    if preset:
        for j in journals:
            st.session_state[_chk_key(j)] = j in preset.get("journals", [])
        st.session_state["since_input"] = datetime.strptime(preset["since"], "%Y-%m-%d").date()
        st.session_state["until_input"] = datetime.strptime(preset["until"], "%Y-%m-%d").date()
        st.session_state["last7_input"] = preset.get("last7", False)
        st.session_state["last30_input"] = preset.get("last30", False)
        st.session_state["last1_input"] = preset.get("last1", False)
        st.session_state["rows_input"] = preset.get("rows", 100)
        st.session_state["ai_model_input"] = preset.get("ai_model", "gpt-4.1")
        st.session_state["topic_query_input"] = preset.get("topic_query", "")
        st.session_state["relevance_query_input"] = preset.get("relevance_query", "")
        st.session_state["brief_lang"] = preset.get("brief_lang", "Deutsch")

st.markdown("## Command Center")

with st.expander("🧭 Scope & Journals", expanded=True):
    with st.container(border=True):
        st.markdown("### 🧭 Scope & Journals")
        journal_filter = st.text_input("Journal suchen (Filter)", value="", key="journal_filter_input")

        sel_all_col, desel_all_col = st.columns([1, 1])
        with sel_all_col:
            select_all_clicked = st.button("Alle auswählen", use_container_width=True)
        with desel_all_col:
            deselect_all_clicked = st.button("Alle abwählen", use_container_width=True)

        if select_all_clicked:
            for j in journals:
                st.session_state[_chk_key(j)] = True
        if deselect_all_clicked:
            for j in journals:
                st.session_state[_chk_key(j)] = False

        filtered = [j for j in journals if journal_filter.lower().strip() in j.lower()] if journal_filter.strip() else journals
        cols = st.columns(2)
        for idx, j in enumerate(filtered):
            k = _chk_key(j)
            current_val = st.session_state.get(k, False)
            with cols[idx % 2]:
                if st.checkbox(j, value=current_val, key=k):
                    pass

        chosen = [j for j in journals if st.session_state.get(_chk_key(j), False)]
        st.markdown(f"**{len(chosen)}** Journal(s) ausgewählt.")
        st.session_state["chosen_journals"] = chosen

with st.expander("🗓️ Zeitfenster", expanded=True):
    with st.container(border=True):
        st.markdown("### 🗓️ Zeitfenster")
        date_col1, date_col2, date_col3 = st.columns(3)
        with date_col1:
            if "since_input" not in st.session_state:
                st.session_state["since_input"] = date(today.year, 1, 1)
            since = st.date_input("Seit (inkl.)", value=st.session_state["since_input"], key="since_input")
        with date_col2:
            if "until_input" not in st.session_state:
                st.session_state["until_input"] = today
            until = st.date_input("Bis (inkl.)", value=st.session_state["until_input"], key="until_input")
        with date_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            last30 = st.checkbox("Letzte 30 Tage", value=False, key="last30_input")
            last7 = st.checkbox("Letzte 7 Tage", value=False, key="last7_input")
            last1 = st.checkbox("Letzter Tag", value=False, key="last1_input")
        if last30:
            st.caption(f"Aktiv: {(today - timedelta(days=30)).isoformat()} bis {today.isoformat()}")
        if last7:
            st.caption(f"Aktiv: {(today - timedelta(days=7)).isoformat()} bis {today.isoformat()}")
        if last1:
            st.caption(f"Aktiv: {(today - timedelta(days=1)).isoformat()} bis {today.isoformat()}")

with st.expander("🎯 Ziel & Fokus", expanded=True):
    with st.container(border=True):
        st.markdown("<div class='ps-callout'>Empfohlen</div>", unsafe_allow_html=True)
        st.markdown("### 🎯 Ziel & Fokus")
        st.caption("Optionaler Fokustext für Relevanz-Rating & Briefing.")
        st.text_area(
            "Forschungsinteresse",
            value=st.session_state.get("relevance_query_input", ""),
            height=120,
            key="relevance_query_input",
        )
        st.caption("Wenn ausgefüllt, werden Ergebnisse automatisch nach Relevanz bewertet und ein Briefing erzeugt.")
        st.selectbox("Briefing-Sprache", ["Deutsch", "English"], index=0, key="brief_lang")

with st.expander("💾 Gespeicherte Suchen", expanded=False):
    with st.container(border=True):
        st.markdown("### 💾 Gespeicherte Suchen")
        ss_cols = st.columns([2, 1, 1])
        with ss_cols[0]:
            save_name = st.text_input("Name", value="")
        with ss_cols[1]:
            if st.button("Speichern", use_container_width=True):
                if not save_name.strip():
                    st.warning("Bitte einen Namen angeben.")
                else:
                    preset = {
                        "name": save_name.strip(),
                        "journals": st.session_state.get("chosen_journals", []),
                        "since": str(st.session_state.get("since_input")),
                        "until": str(st.session_state.get("until_input")),
                        "last7": bool(st.session_state.get("last7_input")),
                        "last30": bool(st.session_state.get("last30_input")),
                        "last1": bool(st.session_state.get("last1_input")),
                        "rows": int(st.session_state.get("rows_input", 100)),
                        "ai_model": st.session_state.get("ai_model_input", "gpt-4.1"),
                        "topic_query": st.session_state.get("topic_query_input", ""),
                        "relevance_query": st.session_state.get("relevance_query_input", ""),
                        "brief_lang": st.session_state.get("brief_lang", "Deutsch"),
                    }
                    st.session_state["saved_searches"] = [p for p in st.session_state["saved_searches"] if p["name"] != preset["name"]]
                    st.session_state["saved_searches"].append(preset)
                    st.success("Gespeichert.")
        with ss_cols[2]:
            if st.session_state["saved_searches"]:
                if st.button("Löschen", use_container_width=True):
                    st.session_state["saved_searches"] = []
                    st.success("Gelöscht.")

        if st.session_state["saved_searches"]:
            names = [p["name"] for p in st.session_state["saved_searches"]]
            pick = st.selectbox("Laden", options=names, index=0)
            if st.button("Anwenden", use_container_width=True):
                st.session_state["preset_to_apply"] = pick
                st.rerun()

with st.expander("🚀 Discovery Mode (optional)", expanded=False):
    with st.container(border=True):
        st.markdown("### 🚀 Discovery Mode")
        mode = st.radio(
            "Modus",
            ["Scout (schnell)", "Focus (balanciert)", "Deep (maximale Abdeckung)"],
            index=1,
            key="discovery_mode",
        )

        if "rows_input" not in st.session_state:
            st.session_state["rows_input"] = 100
        if "ai_model_input" not in st.session_state:
            st.session_state["ai_model_input"] = "gpt-4.1"

        if "use_semantic" not in st.session_state:
            st.session_state["use_semantic"] = True
        if "use_openalex" not in st.session_state:
            st.session_state["use_openalex"] = True
        if "use_html" not in st.session_state:
            st.session_state["use_html"] = True
        if "use_ai" not in st.session_state:
            st.session_state["use_ai"] = False
        if "use_scidir" not in st.session_state:
            st.session_state["use_scidir"] = True

        if st.button("Modus übernehmen"):
            if mode.startswith("Scout"):
                st.session_state["rows_input"] = 60
                st.session_state["use_semantic"] = True
                st.session_state["use_openalex"] = False
                st.session_state["use_html"] = False
                st.session_state["use_ai"] = False
                st.session_state["use_scidir"] = False
            elif mode.startswith("Focus"):
                st.session_state["rows_input"] = 100
                st.session_state["use_semantic"] = True
                st.session_state["use_openalex"] = True
                st.session_state["use_html"] = True
                st.session_state["use_ai"] = False
                st.session_state["use_scidir"] = True
            else:
                st.session_state["rows_input"] = 150
                st.session_state["use_semantic"] = True
                st.session_state["use_openalex"] = True
                st.session_state["use_html"] = True
                st.session_state["use_ai"] = True
                st.session_state["use_scidir"] = True
            st.success("Modus angewendet.")

        rows = st.number_input("Max. Treffer pro Journal", min_value=5, max_value=300, step=5, value=st.session_state["rows_input"], key="rows_input")
        ai_model = st.text_input("OpenAI Modell", value=st.session_state["ai_model_input"], key="ai_model_input")
        max_total = st.slider("Max. Treffer gesamt", min_value=100, max_value=2000, value=800, step=50, key="max_total_input")
        topic_query = st.text_input("Fokus-Keywords (optional, Crossref Filter)", value="", key="topic_query_input")

        st.markdown("**Quellen & Fallbacks**")
        st.checkbox("Semantic Scholar", value=st.session_state["use_semantic"], key="use_semantic")
        st.checkbox("OpenAlex", value=st.session_state["use_openalex"], key="use_openalex")
        st.checkbox("HTML-Abstracts", value=st.session_state["use_html"], key="use_html")
        st.checkbox("AI-Extraktion (Fallback)", value=st.session_state["use_ai"], key="use_ai")
        st.checkbox("ScienceDirect Spezial", value=st.session_state["use_scidir"], key="use_scidir")

with st.expander("🔑 Keys & Netzwerk (optional)", expanded=False):
    with st.container(border=True):
        st.markdown("### 🔑 Keys & Netzwerk")
        api_key_input = st.text_input("OpenAI API-Key", type="password", value="", help="Optional. Wird für KI-Funktionen benötigt.")
        if api_key_input:
            os.environ["PAPERSCOUT_OPENAI_API_KEY"] = api_key_input
            os.environ["OPENAI_API_KEY"] = api_key_input
            st.caption("API-Key für diese Sitzung gesetzt.")

        crossref_mail = st.text_input("Crossref Mailto", value=os.getenv("CROSSREF_MAILTO", ""), help="Empfohlen für stabilere Crossref-API.")
        if crossref_mail:
            os.environ["CROSSREF_MAILTO"] = crossref_mail
            st.caption("Crossref-Mailto gesetzt.")

        proxy_url = st.text_input("Proxy (optional)", value=os.getenv("PAPERSCOUT_PROXY", ""), help="Format: http://user:pass@host:port")
        if proxy_url:
            st.session_state["proxy_url"] = proxy_url.strip()
            st.success("Proxy aktiv.")
        else:
            st.session_state["proxy_url"] = ""

        with st.expander("E-Mail Versand (Status)", expanded=False):
            ok = all(os.getenv(k) for k in ["EMAIL_HOST","EMAIL_PORT","EMAIL_USER","EMAIL_PASSWORD","EMAIL_FROM"])
            if ok:
                st.success(f"SMTP konfiguriert: {os.getenv('EMAIL_FROM')}")
            else:
                st.error("SMTP nicht vollständig konfiguriert.")

st.divider()

# --- Start-Button ---
run_col1, run_col2, run_col3 = st.columns([2, 1, 2])
with run_col2:
    run = st.button("🚀 Let´s go! Metadaten ziehen", use_container_width=True, type="primary")

# Sync relevance query from input
st.session_state["relevance_query"] = st.session_state.get("relevance_query_input", "")

if run:
    if not chosen:
        st.warning("Bitte mindestens ein Journal auswählen.")
    else:
        st.info("Starte Abruf — Crossref, Semantic Scholar, OpenAlex, Fallbacks...")

        # Vorherige Ergebnisse merken für "Compare Runs"
        st.session_state["last_run_df"] = st.session_state.get("results_df", None)

        all_rows: List[Dict[str, Any]] = []
        progress = st.progress(0, "Starte...")
        n = len(chosen)
        if last7:
            s_since = (today - timedelta(days=7)).isoformat()
            s_until = today.isoformat()
        elif last30:
            s_since = (today - timedelta(days=30)).isoformat()
            s_until = today.isoformat()
        elif last1:
            s_since = (today - timedelta(days=1)).isoformat()
            s_until = today.isoformat()
        else:
            s_since, s_until = str(since), str(until)

        options = {
            "use_semantic": st.session_state.get("use_semantic", True),
            "use_openalex": st.session_state.get("use_openalex", True),
            "use_html": st.session_state.get("use_html", True),
            "use_ai": st.session_state.get("use_ai", True),
            "use_scidir": st.session_state.get("use_scidir", True),
        }

        for i, j in enumerate(chosen, 1):
            progress.progress(min(i / max(n, 1), 1.0), f"({i}/{n}) Verarbeite: {j}")
            rows_j = collect_all(
                j,
                s_since,
                s_until,
                int(rows),
                ai_model,
                topic_query=st.session_state.get("topic_query_input","").strip() or None,
                options=options,
            )
            rows_j = dedup(rows_j)
            all_rows.extend(rows_j)

        progress.empty()
        status_box = st.empty()
        status_box.info("Finalisiere Ergebnisse: Deduplizierung & Aufbereitung …")
        if not all_rows:
            st.warning("Keine Treffer im gewählten Zeitraum/Journals gefunden.")
            status_box.empty()
        else:
            # globale Deduplizierung + Limit
            status_box.info("Bereinige und aggregiere Treffer …")
            all_rows = dedup(all_rows)
            max_total_val = int(st.session_state.get("max_total_input", 0) or 0)
            if max_total_val > 0:
                all_rows = all_rows[:max_total_val]

            status_box.info("Baue Ergebnis-DataFrame …")
            df = pd.DataFrame(all_rows)
            cols = [c for c in ["title", "doi", "issued", "journal", "authors", "abstract", "url", "abstract_source"] if c in df.columns]
            if cols:
                df = df[cols]

            # --- Auto-Relevanz & Auto-Briefing (One-Step Workflow) ---
            rel_query = (st.session_state.get("relevance_query_input", "") or "").strip()
            rel_key = os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            if rel_query:
                if rel_key:
                    status_box.info("Berechne Relevanz (Embeddings) …")
                    min_len = int(st.session_state.get("relevance_min_text_len", 30) or 30)
                    rel_series = compute_relevance_scores(
                        df,
                        rel_query,
                        min_text_len=min_len,
                    )
                    if rel_series is not None:
                        df["relevance_score"] = rel_series
                        why_list = []
                        for _, row in df.iterrows():
                            text = (str(row.get("abstract","")) + " " + str(row.get("title",""))).strip()
                            why_list.append(_why_relevant(rel_query, text))
                        df["relevance_why"] = why_list

                        # Auto-Briefing: Top Relevanz
                        status_box.info("Erzeuge Research Brief …")
                        top_n = int(st.session_state.get("brief_n", 8) or 8)
                        top_n = max(3, min(top_n, 12))
                        top_df = df.sort_values("relevance_score", ascending=False).head(top_n)
                        brief_lang = st.session_state.get("brief_lang", "Deutsch")
                        brief = ai_generate_digest(top_df.to_dict(orient="records"), model=ai_model, lang=brief_lang)
                        if brief:
                            st.session_state["research_brief"] = brief
                    else:
                        st.warning("Relevanz konnte nicht automatisch berechnet werden.")
                else:
                    st.info("Relevanz & Briefing übersprungen: Bitte OpenAI API-Key im Command Center setzen.")

            st.session_state["results_df"] = df
            st.session_state["selected_dois"] = set() # Auswahl zurücksetzen
            
            # Alle Checkbox-States löschen/zurücksetzen, falls alte Keys von einem früheren Lauf existieren
            for key in list(st.session_state.keys()):
                if key.startswith("sel_card_"):
                    del st.session_state[key]
            
            # Compare Runs: neue DOIs seit letztem Lauf
            prev = st.session_state.get("last_run_df")
            if isinstance(prev, pd.DataFrame) and not prev.empty:
                prev_dois = set(prev.get("doi", pd.Series(dtype=str)).astype(str).str.lower())
                new_mask = ~df["doi"].astype(str).str.lower().isin(prev_dois)
                st.session_state["new_since_last_run"] = df[new_mask].copy()
            else:
                st.session_state["new_since_last_run"] = None

            status_box.success("Ergebnisse bereit.")
            st.success(f"🎉 {len(df)} Treffer geladen!")

# ================================
# --- NEUE ERGEBNISANZEIGE (v2) ---
# ================================

if "results_df" in st.session_state and not st.session_state["results_df"].empty:
    st.divider()
    st.subheader("📚 Ergebnisse")

    # --- Basisdaten (für Analyse + Ergebnisliste) ---
    df = add_signal_scores(st.session_state["results_df"].copy())

    # --- Research Question & Briefing (oben, ohne Karten) ---
    rel_query_display = (st.session_state.get("relevance_query_input", "") or "").strip()
    st.markdown("### Research Question")
    if rel_query_display:
        st.markdown(f"**{rel_query_display}**")
    else:
        st.caption("Noch keine Research Question angegeben.")

    brief_text = st.session_state.get("research_brief", "")
    st.markdown("### Briefing")
    if brief_text:
        st.markdown(brief_text)
    else:
        st.caption("Noch kein Briefing. Starte einen Run mit Research Question und API‑Key.")

    if "url" in df.columns: df["link"] = df["url"].apply(_to_http)
    elif "doi" in df.columns: df["link"] = df["doi"].apply(_to_http)
    else: df["link"] = ""

    if "selected_dois" not in st.session_state: st.session_state["selected_dois"] = set()

    analysis_open, analysis_body = section_card(
        "Weitere Analysemöglichkeiten ausklappen",
        "Empfehlungen, Cluster, Trends und manuelle Relevanz-Bewertung.",
        "exp_more",
    )
    if analysis_open:
        with analysis_body:
            # --- Compare Runs ---
            new_df = st.session_state.get("new_since_last_run")
            if isinstance(new_df, pd.DataFrame) and not new_df.empty:
                with st.expander(f"🆕 Neu seit letztem Lauf ({len(new_df)})", expanded=False):
                    for r_idx, (_, row) in enumerate(new_df.head(10).iterrows()):
                        render_row_ui(row, f"new_{r_idx}")
                    if len(new_df) > 10:
                        st.caption(f"Noch {len(new_df) - 10} weitere neue Ergebnisse.")

            # --------------------------------------
            # 🧩 Themencluster (Beta) – OpenAI-Embeddings
            # --------------------------------------
            cluster_open, cluster_body = section_card(
                "🧩 Themencluster (Beta)",
                "Findet thematische Gruppen in den Abstracts und vergibt automatische Clusternamen.",
                "exp_cluster",
            )
            if cluster_open:
                with cluster_body:
                    key_openai = os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
                    if not key_openai:
                        st.info("Bitte trage einen OpenAI API-Key ein (oben im Command Center), um Themencluster zu berechnen.")
                    else:
                        # Layout für Controls: Links Slider, Rechts Button
                        with st.container(border=True):
                            cl_controls_1, cl_controls_2, cl_controls_3 = st.columns([1, 1, 1])
                            with cl_controls_1:
                                 cluster_k = st.slider(
                                    "Anzahl Cluster",
                                    min_value=2,
                                    max_value=10,
                                    value=5,
                                    step=1,
                                    key="cluster_k_slider",
                                )
                            with cl_controls_2:
                                 cluster_min_docs = st.slider(
                                    "Min. Artikel/Cluster",
                                    min_value=3,
                                    max_value=20,
                                    value=5,
                                    step=1,
                                    key="cluster_min_docs_slider",
                                )
                            with cl_controls_3:
                                st.write("") # Spacer
                                st.write("") # Spacer
                                if st.button("🔍 Themencluster berechnen", use_container_width=True, key="btn_cluster_compute"):
                                    clusters = build_clusters_openai(df, k=cluster_k, min_docs=cluster_min_docs)
                                    if not clusters:
                                        st.warning("Konnte keine sinnvollen Themencluster bilden (zu wenig Text oder technische Probleme).")
                                    else:
                                        st.session_state["topic_clusters_openai"] = clusters
                                        st.success(f"{len(clusters)} Cluster erstellt.")

                        # --- UPDATE: Karten-Design (Expander untereinander) ---
                        clusters = st.session_state.get("topic_clusters_openai") or []
                        if clusters:
                            for c_idx, cluster in enumerate(clusters):
                                label_text = cluster["label"]
                                # Wir nutzen st.expander für das "Aufklappen"
                                with st.expander(label_text, expanded=False):
                                    # Inhalt in Container für Styling
                                    st.markdown(f"**Beispieltext:** *{cluster['sample_text']}*")
                                    
                                    sub_df = df.loc[cluster["indices"]] if cluster["indices"] else pd.DataFrame()
                                    st.caption(f"{len(sub_df)} Artikel in diesem Cluster:")
                                    
                                    # Hier rendern wir nun auch die vollwertigen Karten mit Checkboxen und Abstract
                                    for r_idx, (_, row) in enumerate(sub_df.iterrows()):
                                        render_row_ui(row, f"clus_{c_idx}_{r_idx}")
                        else:
                            if key_openai:
                                st.caption("Noch keine Cluster berechnet. Wähle Parameter und klicke auf „Themencluster berechnen“.")

            # --------------------------------------
            # 🧭 Trends & Insights (Zeitvergleich + Journal Trends)
            # --------------------------------------
            trends_open, trends_body = section_card(
                "🧭 Trends & Insights",
                "Zeigt Trend-Themen, Publikationen pro Monat und Abstract-Quellen.",
                "exp_trends",
            )
            if trends_open:
                with trends_body:
                    trend = _trend_summary(df, recent_days=30)
                    if trend:
                        st.caption(f"Zeitraum: {trend['recent_start']} bis {trend['recent_end']} (letzte 30 Tage)")
                        t_cols = st.columns(3)
                        with t_cols[0]:
                            st.markdown("**Top-Themen (letzte 30 Tage)**")
                            st.write(", ".join(trend.get("recent_terms", [])) or "–")
                        with t_cols[1]:
                            st.markdown("**Top-Themen (davor)**")
                            st.write(", ".join(trend.get("prior_terms", [])) or "–")
                        with t_cols[2]:
                            st.markdown("**Emerging Terms**")
                            st.write(", ".join(trend.get("emerging", [])) or "–")
                    else:
                        st.caption("Nicht genügend Datumsangaben für Trend-Analyse.")

                    # Journal-Trends
                    journal_counts = df.get("journal", pd.Series(dtype=str)).value_counts().head(5)
                    if not journal_counts.empty:
                        st.markdown("**Top Journals (Anzahl Treffer)**")
                        st.write(", ".join([f"{j} ({c})" for j, c in journal_counts.items()]))

                    # Zeitverlauf (Monat)
                    month_counts = df.get("issued", pd.Series(dtype=str)).dropna().astype(str).str[:7]
                    month_counts = month_counts[month_counts.str.match(r"\d{4}-\d{2}")]
                    if not month_counts.empty:
                        st.markdown("**Publikationen pro Monat**")
                        trend_series = month_counts.value_counts().sort_index()
                        st.bar_chart(trend_series)

                    if trend:
                        emerging = trend.get("emerging", [])
                        if emerging:
                            st.markdown("**Query-Ideen (automatisch)**")
                            suggestions = []
                            if len(emerging) >= 3:
                                suggestions.append(", ".join(emerging[:3]))
                            if len(emerging) >= 2:
                                suggestions.append(" ".join(emerging[:2]))
                            suggestions.append(emerging[0])
                            st.write(" · ".join(suggestions[:3]))

                    source_counts = df.get("abstract_source", pd.Series(dtype=str)).value_counts()
                    if not source_counts.empty:
                        st.markdown("**Abstract-Quellen**")
                        st.bar_chart(source_counts)

            # --------------------------------------
            # 🔮 Empfehlungen (ähnliche Reads zu Auswahl)
            # --------------------------------------
            rec_open, rec_body = section_card(
                "🔮 Empfohlene nächste Reads",
                "Schlägt Paper vor, die deiner Auswahl semantisch ähneln.",
                "exp_recs",
            )
            if rec_open:
                with rec_body:
                    rec_key = os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
                    if not rec_key:
                        st.info("Für Empfehlungen wird ein OpenAI API-Key benötigt (oben im Command Center).")
                    else:
                        rec_cols = st.columns([1, 3])
                        with rec_cols[0]:
                            rec_n = st.slider("Anzahl Empfehlungen", min_value=3, max_value=15, value=6, step=1)
                            if st.button("Empfehlungen berechnen", use_container_width=True):
                                sel = st.session_state.get("selected_dois", set())
                                if not sel:
                                    st.warning("Bitte wähle mindestens eine DOI aus.")
                                else:
                                    # Build embeddings cache
                                    cache = st.session_state.get("embedding_cache", {})
                                    def _embed_text(text: str) -> List[float]:
                                        key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
                                        if key in cache:
                                            return cache[key]
                                        emb = _get_embedding(text)
                                        if emb:
                                            cache[key] = emb
                                        return emb

                                    # Mean embedding of selected
                                    sel_rows = df[df["doi"].astype(str).str.lower().isin(sel)]
                                    sel_vecs = []
                                    for _, r in sel_rows.iterrows():
                                        text = (str(r.get("abstract","")) + " " + str(r.get("title",""))).strip()
                                        emb = _embed_text(text)
                                        if emb:
                                            sel_vecs.append(emb)
                                    if not sel_vecs:
                                        st.warning("Keine Embeddings für Auswahl verfügbar.")
                                    else:
                                        # Average
                                        dim = len(sel_vecs[0])
                                        mean = [0.0] * dim
                                        for v in sel_vecs:
                                            for i in range(dim):
                                                mean[i] += v[i]
                                        mean = [v / len(sel_vecs) for v in mean]

                                        # Score others
                                        scores = []
                                        for idx, r in df.iterrows():
                                            if str(r.get("doi","")).lower() in sel:
                                                continue
                                            text = (str(r.get("abstract","")) + " " + str(r.get("title",""))).strip()
                                            emb = _embed_text(text)
                                            if not emb:
                                                continue
                                            scores.append((idx, _cosine_sim(mean, emb)))
                                        scores = sorted(scores, key=lambda x: x[1], reverse=True)[:rec_n]
                                        st.session_state["rec_indices"] = [i for i, _ in scores]
                                        st.session_state["embedding_cache"] = cache

                        with rec_cols[1]:
                            rec_idx = st.session_state.get("rec_indices", [])
                            if rec_idx:
                                sub_df = df.loc[rec_idx]
                                for r_idx, (_, row) in enumerate(sub_df.iterrows()):
                                    render_row_ui(row, f"rec_{r_idx}")
                            else:
                                st.caption("Wähle DOIs und berechne Empfehlungen.")

            # --------------------------------------
            # 🧠 Research Brief (KI) - Regenerieren
            # --------------------------------------
            brief_open, brief_body = section_card(
                "🧠 Research Brief (Regenerieren)",
                "Erzeuge das Briefing erneut (z. B. mit anderem Umfang).",
                "exp_brief",
            )
            if brief_open:
                with brief_body:
                    brief_key = os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
                    if not brief_key:
                        st.info("Für den Research Brief wird ein OpenAI API-Key benötigt (oben im Command Center).")
                    else:
                        b_cols = st.columns([1, 2])
                        with b_cols[0]:
                            brief_source = st.radio(
                                "Quelle",
                                ["Auswahl", "Top Relevanz", "Alle (Limit)"],
                                index=0,
                                key="brief_source",
                            )
                            brief_n = st.slider("Anzahl Papers", min_value=3, max_value=12, value=8, step=1, key="brief_n")
                            if st.button("Briefing erzeugen", use_container_width=True):
                                if brief_source == "Auswahl":
                                    sel = st.session_state.get("selected_dois", set())
                                    if not sel:
                                        st.warning("Bitte wähle mindestens eine DOI aus.")
                                    else:
                                        sub = df[df["doi"].astype(str).str.lower().isin(sel)].head(brief_n)
                                        brief = ai_generate_digest(sub.to_dict(orient="records"), model=ai_model, lang=st.session_state.get("brief_lang", "Deutsch"))
                                        st.session_state["research_brief"] = brief
                                elif brief_source == "Top Relevanz" and "relevance_score" in df.columns:
                                    sub = df.sort_values("relevance_score", ascending=False).head(brief_n)
                                    brief = ai_generate_digest(sub.to_dict(orient="records"), model=ai_model, lang=st.session_state.get("brief_lang", "Deutsch"))
                                    st.session_state["research_brief"] = brief
                                else:
                                    sub = df.head(brief_n)
                                    brief = ai_generate_digest(sub.to_dict(orient="records"), model=ai_model, lang=st.session_state.get("brief_lang", "Deutsch"))
                                    st.session_state["research_brief"] = brief
                        with b_cols[1]:
                            brief_text = st.session_state.get("research_brief", "")
                            if brief_text:
                                st.markdown(brief_text)
                            else:
                                st.caption("Noch kein Briefing. Quelle wählen und generieren.")

            # --------------------------------------
            # 🎯 Relevanz-Rating (Beta) - Manuell
            # --------------------------------------
            rel_open, rel_body = section_card(
                "🎯 Relevanz-Rating (Beta)",
                "Bewertet Papers nach semantischer Nähe zu deinem Forschungsfokus.",
                "exp_relevance",
                default_open=True,
                accent=True,
            )
            if rel_open:
                with rel_body:
                    rel_key = os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
                    if not rel_key:
                        st.info("Für das Relevanz-Rating wird ein OpenAI API-Key benötigt (oben im Command Center).")
                    else:
                        # Layout Aufteilung: Links Eingabe, Rechts Ergebnisse
                        # Damit die Ergebnisse nicht "gequetscht" wirken, geben wir rechts mehr Platz
                        rel_col_left, rel_col_right = st.columns([1, 2])
                        
                        with rel_col_left:
                            st.markdown("#### Eingabe")
                            advanced_rel = st.checkbox("Mehrere Queries (gewichtet)", value=False, key="advanced_relevance")
                            if advanced_rel:
                                if "rel_queries" not in st.session_state:
                                    st.session_state["rel_queries"] = [{"text": "", "weight": 1.0}]
                                for i, q in enumerate(st.session_state["rel_queries"]):
                                    row_cols = st.columns([3, 1, 1])
                                    with row_cols[0]:
                                        st.text_input("Query", value=q.get("text",""), key=f"rel_q_{i}")
                                    with row_cols[1]:
                                        st.number_input("Gewicht", min_value=0.1, max_value=5.0, value=float(q.get("weight",1.0)), step=0.1, key=f"rel_w_{i}")
                                    with row_cols[2]:
                                        if st.button("Entfernen", key=f"rel_rm_{i}"):
                                            st.session_state["rel_queries"].pop(i)
                                            st.rerun()
                                if st.button("Query hinzufügen"):
                                    st.session_state["rel_queries"].append({"text": "", "weight": 1.0})
                                # Sync back inputs
                                synced = []
                                for i in range(len(st.session_state["rel_queries"])):
                                    synced.append({
                                        "text": st.session_state.get(f"rel_q_{i}", ""),
                                        "weight": st.session_state.get(f"rel_w_{i}", 1.0),
                                    })
                                st.session_state["rel_queries"] = synced
                                relevance_query = " ".join([q["text"] for q in synced if q.get("text")])
                            else:
                                relevance_query = st.text_area(
                                    "Forschungsinteresse / Fragestellung:",
                                    value=st.session_state.get("relevance_query_input", ""),
                                    height=150,
                                    help="Beispiel: 'transformational leadership, follower well-being, mediated by trust'",
                                    key="relevance_query_detail",
                                )

                            min_len = st.slider(
                                "Min. Textlänge (Zeichen)",
                                min_value=20,
                                max_value=100,
                                value=30,
                                step=5,
                                key="relevance_min_text_len",
                            )

                            if st.button("⭐ Relevanz berechnen", use_container_width=True, key="btn_compute_relevance"):
                                if not relevance_query.strip():
                                    st.warning("Bitte gib eine Beschreibung ein.")
                                else:
                                    st.session_state["relevance_query"] = relevance_query.strip()
                                    if advanced_rel:
                                        rel_series = compute_relevance_scores_multi(
                                            df,
                                            st.session_state.get("rel_queries", []),
                                            min_text_len=min_len,
                                        )
                                    else:
                                        rel_series = compute_relevance_scores(
                                            df,
                                            relevance_query.strip(),
                                            min_text_len=min_len,
                                        )
                                    if rel_series is None:
                                        st.warning("Konnte keine Werte berechnen.")
                                    else:
                                        # In DataFrame übernehmen
                                        df["relevance_score"] = rel_series
                                        # Warum relevant? (simple term overlap)
                                        combined_query = relevance_query.strip()
                                        why_list = []
                                        for _, row in df.iterrows():
                                            text = (str(row.get("abstract","")) + " " + str(row.get("title",""))).strip()
                                            why_list.append(_why_relevant(combined_query, text))
                                        df["relevance_why"] = why_list
                                        st.session_state["results_df"] = df
                                        st.success("Berechnet!")
                                        st.rerun()

                        with rel_col_right:
                            st.markdown("#### Top 10 Ergebnisse")
                            if "relevance_score" in df.columns:
                                top_df = df.sort_values("relevance_score", ascending=False).head(10)
                                # Hier rendern wir ebenfalls die vollwertigen Karten
                                for r_idx, (_, row) in enumerate(top_df.iterrows()):
                                    render_row_ui(row, f"rel_top_{r_idx}")
                            else:
                                st.caption("Gib links dein Thema ein und klicke auf Berechnen, um die Top 10 zu sehen.")

    # --- Inline Filter & Sort (für Ergebnisliste) ---
    base_df = df.copy()
    f_cols = st.columns([2, 1, 1, 1, 1])
    with f_cols[0]:
        filter_keyword = st.text_input("🔎 Keyword in Titel/Abstract", value="", key="filter_keyword")
    with f_cols[1]:
        filter_author = st.text_input("👤 Autor enthält", value="", key="filter_author")
    with f_cols[2]:
        filter_has_abs = st.checkbox("Nur mit Abstract", value=False, key="filter_has_abs")
    with f_cols[3]:
        filter_journals = st.multiselect("📘 Journals", options=sorted(base_df.get("journal", pd.Series(dtype=str)).dropna().unique().tolist()))
    with f_cols[4]:
        min_rel = 0.0
        if "relevance_score" in base_df.columns:
            min_rel = st.slider("⭐ Min. Relevanz", min_value=0.0, max_value=100.0, value=0.0, step=5.0)

    df = base_df.copy()
    if filter_keyword.strip():
        kw = filter_keyword.strip().lower()
        df = df[
            df.get("title", "").astype(str).str.lower().str.contains(kw, na=False) |
            df.get("abstract", "").astype(str).str.lower().str.contains(kw, na=False)
        ]
    if filter_author.strip():
        au = filter_author.strip().lower()
        df = df[df.get("authors", "").astype(str).str.lower().str.contains(au, na=False)]
    if filter_has_abs:
        df = df[df.get("abstract", "").astype(str).str.len() > 0]
    if filter_journals:
        df = df[df.get("journal", "").isin(filter_journals)]
    if "relevance_score" in df.columns:
        df = df[df["relevance_score"].fillna(0.0) >= min_rel]

    sort_col1, sort_col2 = st.columns([1, 3])
    with sort_col1:
        sort_options = ["Neueste zuerst", "Älteste zuerst", "Signal-Score", "Relevanz", "Titel (A-Z)"]
        if "relevance_score" in df.columns and df["relevance_score"].notna().any():
            default_sort = "Relevanz"
        else:
            default_sort = "Neueste zuerst"
        sort_by = st.selectbox(
            "Sortieren",
            sort_options,
            index=sort_options.index(default_sort),
        )
    if sort_by == "Neueste zuerst":
        df["_issued_dt"] = df.get("issued", "").astype(str).apply(_safe_parse_date)
        df = df.sort_values("_issued_dt", ascending=False, na_position="last").drop(columns=["_issued_dt"])
    elif sort_by == "Älteste zuerst":
        df["_issued_dt"] = df.get("issued", "").astype(str).apply(_safe_parse_date)
        df = df.sort_values("_issued_dt", ascending=True, na_position="last").drop(columns=["_issued_dt"])
    elif sort_by == "Signal-Score":
        if "signal_score" in df.columns:
            df = df.sort_values("signal_score", ascending=False, na_position="last")
        else:
            df["_issued_dt"] = df.get("issued", "").astype(str).apply(_safe_parse_date)
            df = df.sort_values("_issued_dt", ascending=False, na_position="last").drop(columns=["_issued_dt"])
    elif sort_by == "Relevanz":
        if "relevance_score" in df.columns:
            df = df.sort_values("relevance_score", ascending=False, na_position="last")
        else:
            df["_issued_dt"] = df.get("issued", "").astype(str).apply(_safe_parse_date)
            df = df.sort_values("_issued_dt", ascending=False, na_position="last").drop(columns=["_issued_dt"])
    elif sort_by == "Titel (A-Z)":
        df = df.sort_values("title", ascending=True, na_position="last")

    # --- Pagination ---
    p_cols = st.columns([1, 1, 2])
    with p_cols[0]:
        page_size = st.selectbox("Ergebnisse pro Seite", [25, 50, 100], index=1, key="page_size")
    total_pages = max(1, ceil(len(df) / page_size))
    current_page = st.session_state.get("page_num", 1)
    if current_page > total_pages:
        current_page = total_pages
    with p_cols[1]:
        page_num = st.selectbox("Seite", list(range(1, total_pages + 1)), index=list(range(1, total_pages + 1)).index(current_page), key="page_num")
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    df_page = df.iloc[start_idx:end_idx].copy()
    with p_cols[2]:
        st.caption(f"Zeige {start_idx + 1}-{min(end_idx, len(df))} von {len(df)}")

    st.caption("Klicke auf die Checkboxen (egal in welcher Liste), um Einträge für den E-Mail-Versand auszuwählen.")

    # --- Fixierte Pfeil-Navigation (Start/Ende) ---
    FIXED_NAV_HTML = """
    <style>
    .fixed-nav {
        position: fixed;
        bottom: 1.5rem;
        left: 50%;
        transform: translateX(-50%);
        background-color: var(--ps-nav-bg);
        border: 1px solid var(--ps-control-border);
        border-radius: 25px;
        padding: 0.5rem 1rem;
        box-shadow: 0 10px 24px rgba(6,34,88,0.28);
        z-index: 9999;
        opacity: 1;
    }
    .fixed-nav a {
        display: inline-block;
        text-decoration: underline;
        text-underline-offset: 2px;
        color: var(--ps-ink);
        font-size: 1.25rem;
        margin: 0 0.75rem;
        transition: transform 0.1s ease-in-out;
    }
    .fixed-nav a:hover {
        transform: scale(1.2);
        color: var(--ps-accent-text);
    }
    </style>
    
    <div class="fixed-nav">
        <a href="#results_top" title="Zum Anfang der Liste">⬆️</a>
        <a href="#actions_bottom" title="Zum E-Mail Versand">⬇️</a>
    </div>
    """
    st.markdown(FIXED_NAV_HTML, unsafe_allow_html=True)

    # --- Keyboard Shortcuts (G / Shift+G) ---
    components.html(
        """
        <script>
        document.addEventListener('keydown', function(e) {
          if (e.key === 'g' && !e.shiftKey) {
            window.location.hash = '#results_top';
          }
          if (e.key === 'G' || (e.key === 'g' && e.shiftKey)) {
            window.location.hash = '#actions_bottom';
          }
        });
        </script>
        """,
        height=0,
    )
    st.caption("Shortcuts: `g` zum Anfang, `Shift+g` zum E-Mail-Versand.")

    # --- Ergebnis-Loop (paged) ---
    for i, (_, r) in enumerate(df_page.iterrows(), start=start_idx + 1):
        render_row_ui(r, str(i))

    st.markdown("---")

    # --- KORREKTUR 2 (Sync-Fix): Logik für "Alle auswählen/abwählen" ---
    # Wir müssen *vor* den Buttons eine Map aller DOIs und Keys erstellen.
    doi_key_map = {}
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        doi_norm = (r.get("doi", "") or "").lower()
        if doi_norm:
            sel_key = _stable_sel_key(r, str(i))
            doi_key_map[doi_norm] = sel_key
    # --- ENDE KORREKTUR 2 ---


    # --- Aktionen: Auswahl & Download ---
    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])
    with action_col1:
        st.metric(label="Aktuell ausgewählt", value=f"{len(st.session_state['selected_dois'])} / {len(df)}")
    
    with action_col2:
        if st.button("Alle **Ergebnisse** auswählen", use_container_width=True):
            # --- KORREKTUR 3 (Sync-Fix): Button-Logik aktualisiert ---
            # Wir setzen alle DOIs in die Selected List
            st.session_state["selected_dois"] = set(doi_key_map.keys())
            st.rerun()
            # --- ENDE KORREKTUR 3 ---

    with action_col3:
        if st.button("Alle **Ergebnisse** abwählen", use_container_width=True):
            # --- KORREKTUR 4 (Sync-Fix): Button-Logik aktualisiert ---
            st.session_state["selected_dois"].clear()
            st.rerun()
            # --- ENDE KORREKTUR 4 ---
    
    qa_cols = st.columns([1, 1, 1])
    with qa_cols[0]:
        quick_n = st.slider("Quick-Pick Anzahl", min_value=5, max_value=50, value=10, step=5, key="quick_pick_n")
    with qa_cols[1]:
        if st.button("Top Relevanz hinzufügen", use_container_width=True):
            if "relevance_score" in df.columns:
                top = df.sort_values("relevance_score", ascending=False).head(quick_n)
                st.session_state["selected_dois"] |= set(top["doi"].astype(str).str.lower())
                st.rerun()
            else:
                st.warning("Bitte zuerst Relevanz berechnen.")
    with qa_cols[2]:
        if st.button("Neueste hinzufügen", use_container_width=True):
            temp = df.copy()
            temp["_issued_dt"] = temp.get("issued", "").astype(str).apply(_safe_parse_date)
            top = temp.sort_values("_issued_dt", ascending=False).head(quick_n)
            st.session_state["selected_dois"] |= set(top["doi"].astype(str).str.lower())
            st.rerun()

    collections_open, collections_body = section_card(
        "📁 Collections",
        "Gruppiere ausgewählte Papers in benannten Sammlungen für spätere Arbeit.",
        "exp_collections",
    )
    if collections_open:
        with collections_body:
            col_cols = st.columns([2, 1, 1])
            with col_cols[0]:
                col_name = st.text_input("Collection-Name", value="")
            with col_cols[1]:
                if st.button("Zur Collection hinzufügen", use_container_width=True):
                    if not col_name.strip():
                        st.warning("Bitte einen Collection-Namen angeben.")
                    elif not st.session_state["selected_dois"]:
                        st.warning("Bitte zuerst DOIs auswählen.")
                    else:
                        coll = st.session_state["collections"].get(col_name.strip(), set())
                        coll = set(coll) | set(st.session_state["selected_dois"])
                        st.session_state["collections"][col_name.strip()] = coll
                        st.success(f"{len(st.session_state['selected_dois'])} DOI(s) hinzugefügt.")
            with col_cols[2]:
                if st.session_state["collections"]:
                    if st.button("Alle Collections löschen", use_container_width=True):
                        st.session_state["collections"] = {}
                        st.success("Collections gelöscht.")

            if st.session_state["collections"]:
                for name, doi_set in st.session_state["collections"].items():
                    with st.expander(f"📁 {name} ({len(doi_set)})", expanded=False):
                        sub_df = df[df["doi"].astype(str).str.lower().isin({d.lower() for d in doi_set})]
                        for r_idx, (_, row) in enumerate(sub_df.iterrows()):
                            render_row_ui(row, f"coll_{name}_{r_idx}")

    st.divider()
    # --- NEU: Link "Hoch" und Anker "Unten" ---

    # --- Download & E-Mail (neu gruppiert) ---
    actions_open, actions_body = section_card(
        "🏁 Aktionen: Download & Versand",
        "Exportiere Ergebnisse oder sende DOI-Listen per E-Mail.",
        "exp_actions",
        default_open=True, show_toggle=False,
    )
    if actions_open:
        with actions_body:
            dl_col, mail_col = st.columns(2)

            with dl_col:
                st.markdown("#### ⬇️ Download")
                def df_to_excel_bytes(df_in: pd.DataFrame) -> BytesIO | None: # Moved from data_processing
                    engine = _pick_excel_engine() # Moved from data_processing
                    if engine is None: return None # Moved from data_processing
                    out = BytesIO()
                    with pd.ExcelWriter(out, engine=engine) as writer:
                        df_in.to_excel(writer, index=False, sheet_name="results")
                    out.seek(0)
                    return out

                def _df_to_csv_bytes(df_in: pd.DataFrame) -> BytesIO:
                    b = BytesIO()
                    b.write(df_in.to_csv(index=False).encode("utf-8"))
                    b.seek(0)
                    return b

                x_all = df_to_excel_bytes(df)
                if x_all is not None:
                    st.download_button(
                        "Excel — alle Ergebnisse",
                        data=x_all,
                        file_name="paperscout_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.download_button(
                        "CSV — alle Ergebnisse",
                        data=_df_to_csv_bytes(df),
                        file_name="paperscout_results.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                if st.session_state["selected_dois"]:
                    df_sel = df[df["doi"].astype(str).str.lower().isin(st.session_state["selected_dois"])].copy()
                    x_sel = df_to_excel_bytes(df_sel)
                    if x_sel is not None:
                        st.download_button(
                            f"Excel — {len(st.session_state['selected_dois'])} ausgewählte",
                            data=x_sel,
                            file_name="paperscout_selected.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    else:
                         st.download_button(
                            f"CSV — {len(st.session_state['selected_dois'])} ausgewählte",
                            data=_df_to_csv_bytes(df_sel),
                            file_name="paperscout_selected.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                else:
                    st.button("Excel — nur ausgewählte", disabled=True, use_container_width=True)


            with mail_col:
                st.markdown("#### 📧 DOI-Liste senden")
                with st.container(border=True):
                    sender_display = st.text_input(
                        "Absendername (z.B. Naomi oder Ralf)",
                        value="",
                    )
                    to_email = st.text_input("Empfänger-E-Mail-Adresse", key="doi_email_to")
                    
                    if st.button("DOI-Liste senden", use_container_width=True, type="primary"):
                        if not st.session_state["selected_dois"]:
                            st.warning("Bitte wähle mindestens eine DOI aus.")
                        elif not to_email or "@" not in to_email:
                            st.warning("Bitte gib eine gültige E-Mail-Adresse ein.")
                        else:
                            # Ausgewählte DOIs (lowercase)
                            sel_dois = st.session_state["selected_dois"]
                            df_sel = df[df["doi"].astype(str).str.lower().isin(sel_dois)].copy()
                            records = df_sel.to_dict(orient="records")

                            ok, msg = send_doi_email(
                                to_email,
                                records,
                                sender_display=sender_display.strip() or None
                            )
                            st.success(msg) if ok else st.error(msg)

else:
    st.info("Noch keine Ergebnisse geladen. Wähle Journals im Command Center und starte den Run.")
