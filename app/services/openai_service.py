import json
import os
import random
from typing import Any, Dict, List, Optional

import pandas as pd

from app.utils.data_processing import _clean_text, _cosine_sim, parse_date_any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

def _get_openai_key() -> Optional[str]:
    return os.getenv("PAPERSCOUT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def ai_extract_metadata_from_html(html_text:str,model:str)->Optional[Dict[str, Any]]:
    key = _get_openai_key()
    if not key or OpenAI is None: return None
    try:
        client=OpenAI(api_key=key)
        prompt=("Extract JSON with keys {title,doi,authors,issued,journal,abstract}. "
                "Abstract only from given HTML, no guessing. HTML:\n\n")
        resp=client.chat.completions.create(
            model=model,
            messages=[
                {"role":"system","content":"You extract clean metadata from article HTML."},
                {"role":"user","content":prompt+html_text[:100000]}
            ],
            temperature=0,
            response_format={"type":"json_object"}
        )
        data=json.loads(resp.choices[0].message.content)
        for k,v in data.items():
            data[k]=_clean_text(str(v))
        data["issued"]=parse_date_any(data.get("issued","")) or ""
        return data
    except Exception:return None

# =========================
# Themencluster mit OpenAI-Embeddings (ohne sklearn)
# =========================
def _get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    key = _get_openai_key()
    if not key or OpenAI is None: return []
    try:
        client = OpenAI(api_key=key)
        # Text etwas begrenzen
        text_short = text[:4000]
        resp = client.embeddings.create(
            model=model,
            input=text_short
        )
        return list(resp.data[0].embedding)
    except Exception: return []

def _kmeans(vectors: List[List[float]], k: int, max_iter: int = 20) -> List[int]:
    if not vectors or k <= 0: return []

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

        if not changed: break

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
    key = _get_openai_key()
    if not key or OpenAI is None: return None

    # Nur ein paar Beispiele und pro Text begrenzen, damit der Prompt klein bleibt
    snippets = [(t or "").strip()[:600] for t in examples[:5] if t and t.strip()]
    if not snippets: return None

    try:
        client = OpenAI(api_key=key)
        joined = "\n\n---\n\n".join(snippets)
        system_msg = ("Du bist eine wissenschaftliche Assistentin, die Themencluster aus "
                      "Forschungsartikeln benennt. "
                      "Deine Aufgabe ist es, einen sehr kurzen, prägnanten Titel (3–6 Wörter) "
                      "für das Thema zu vergeben. Schreibe auf Deutsch, ohne Anführungszeichen.")
        user_msg = ("Hier sind einige Abstracts oder Titel von Artikeln, die zum selben Themencluster gehören:\n\n"
                    f"{joined}\n\n"
                    "Gib mir bitte NUR einen kurzen, sprechenden Namen für das Thema (3–6 Wörter, Deutsch), "
                    "ohne Anführungszeichen, ohne zusätzliche Erklärung.")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            temperature=0.2,
        )
        label = (resp.choices[0].message.content or "").strip()
        label = re.sub(r'^[\"“”]+|[\"“”]+$', '', label).strip()
        return label or None
    except Exception: return None

def ai_generate_digest(records: List[Dict[str, Any]], model: str = "gpt-4o-mini", lang: str = "Deutsch") -> Optional[str]:
    key = _get_openai_key()
    if not key or not records or OpenAI is None: return None
    try:
        client = OpenAI(api_key=key)
        items = []
        for r in records[:12]:
            title = _clean_text(str(r.get("title","")))
            journal = _clean_text(str(r.get("journal","")))
            issued = _clean_text(str(r.get("issued","")))
            abstract = _clean_text(str(r.get("abstract","")))[:900]
            items.append(f"TITLE: {title}\nJOURNAL: {journal}\nDATE: {issued}\nABSTRACT: {abstract}")
        payload = "\n\n---\n\n".join(items)
        system_msg = ("You are a research analyst who produces concise, high-signal digests of recent papers.")
        user_msg = (f"Language: {lang}. Create a digest with these sections:\n"
                    "1) Executive summary (4-6 bullets)\n"
                    "2) Emerging themes (3 bullets)\n"
                    "3) Open questions (3 bullets)\n"
                    "4) Recommended papers (5 bullets, include title + one-line why)\n\n"
                    f"PAPERS:\n{payload}")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception: return None

def build_clusters_openai(df: pd.DataFrame, k: int = 5, min_docs: int = 5) -> Optional[List[Dict[str, Any]]]:
    if df.empty: return None

    texts: List[str] = []; indices: List[int] = []
    for idx, row in df.iterrows():
        abstract = str(row.get("abstract", "") or "").strip()
        title = str(row.get("title", "") or "").strip()
        text = abstract if len(abstract) > 40 else title
        if len(text) < 20: continue
        texts.append(text); indices.append(idx)

    if len(texts) < min_docs: return None

    embeddings: List[List[float]] = []; clean_indices: List[int] = []; clean_texts: List[str] = []
    for txt, idx in zip(texts, indices):
        emb = _get_embedding(txt)
        if emb: embeddings.append(emb); clean_indices.append(idx); clean_texts.append(txt)

    if len(embeddings) < min_docs: return None

    k = max(2, min(k, len(embeddings)))
    labels = _kmeans(embeddings, k=k)

    clusters: List[Dict[str, Any]] = []
    for cluster_id in range(k):
        member_positions = [i for i, lab in enumerate(labels) if lab == cluster_id]
        if not member_positions: continue
        member_indices = [clean_indices[i] for i in member_positions]
        sample_text = clean_texts[member_positions[0]]
        clusters.append({"cluster_id": cluster_id, "label": f"Cluster {cluster_id+1}", "sample_text": (sample_text[:240] + "...") if len(sample_text) > 240 else sample_text, "indices": member_indices})

    if not clusters: return None

    key = _get_openai_key()
    if key:
        idx_to_text = {idx: txt for idx, txt in zip(clean_indices, clean_texts)}
        for cluster in clusters:
            ex_texts = [idx_to_text.get(i, "") for i in cluster.get("indices", [])]; ex_texts = [t for t in ex_texts if t]
            if not ex_texts: continue
            ai_label = _ai_name_cluster(ex_texts)
            if ai_label: cluster["label"] = f"Cluster {cluster['cluster_id']+1}: {ai_label}"
    return clusters

def compute_relevance_scores(df: pd.DataFrame, query_text: str, min_text_len: int = 30, model: str = "text-embedding-3-small") -> Optional[pd.Series]:
    query_text = (query_text or "").strip()
    if not query_text: return None
    q_emb = _get_embedding(query_text, model=model)
    if not q_emb: return None
    scores: Dict[int, float] = {}
    for idx, row in df.iterrows():
        abstract = str(row.get("abstract", "") or "").strip(); title = str(row.get("title", "") or "").strip()
        text = abstract if len(abstract) >= min_text_len else title
        if len(text) < min_text_len: scores[idx] = 0.0; continue
        emb = _get_embedding(text, model=model)
        if not emb: scores[idx] = 0.0; continue
        sim = _cosine_sim(q_emb, emb); sim = max(sim, 0.0)
        scores[idx] = round(sim * 100, 1)
    return pd.Series(scores, name="relevance_score") if scores else None

def compute_relevance_scores_multi(df: pd.DataFrame, queries: List[Dict[str, Any]], min_text_len: int = 30, model: str = "text-embedding-3-small") -> Optional[pd.Series]:
    clean = [(q.get("text","").strip(), float(q.get("weight", 1.0))) for q in queries if q.get("text","").strip()]
    if not clean: return None
    emb_sum = None; weight_sum = 0.0
    for text, w in clean:
        emb = _get_embedding(text, model=model)
        if not emb: continue
        if emb_sum is None: emb_sum = [0.0] * len(emb)
        for i, v in enumerate(emb): emb_sum[i] += v * w
        weight_sum += w
    if not emb_sum or weight_sum == 0: return None
    q_emb = [v / weight_sum for v in emb_sum]

    scores: Dict[int, float] = {}
    for idx, row in df.iterrows():
        abstract = str(row.get("abstract", "") or "").strip(); title = str(row.get("title", "") or "").strip()
        text = abstract if len(abstract) >= min_text_len else title
        if len(text) < min_text_len: scores[idx] = 0.0; continue
        emb = _get_embedding(text, model=model)
        if not emb: scores[idx] = 0.0; continue
        sim = _cosine_sim(q_emb, emb); sim = max(sim, 0.0)
        scores[idx] = round(sim * 100, 1)
    return pd.Series(scores, name="relevance_score") if scores else None