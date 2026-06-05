import html
from typing import Any, Dict

import pandas as pd
import streamlit as st

from app.utils.data_processing import _stable_sel_key, _to_http


# --- KORREKTUR 1 (Sync-Fix): Angepasste Callback-Funktion ---
def toggle_doi(doi: str, key: str):
    # Diese Funktion wird *nach* dem Klick ausgeführt.
    # st.session_state[key] enthält jetzt den *neuen* Status.
    is_checked = st.session_state.get(key, False)
    if is_checked:
        st.session_state["selected_dois"].add(doi)
    else:
        st.session_state["selected_dois"].discard(doi)
# --- ENDE KORREKTUR 1 ---

# --- Helper Funktion zum Rendern einer Artikel-Karte mit Checkbox ---
def render_row_ui(row: pd.Series, unique_suffix: str):
    """
    Rendert eine einzelne Zeile bestehend aus Checkbox (links) und Karte (rechts).
    Die Karte enthält Details und Abstract als Klapptext.
    """
    doi_val = str(row.get("doi", "") or "")
    doi_norm = doi_val.lower()
    link_val = _to_http(row.get("link", "") or doi_val)
    title = row.get("title", "") or "(ohne Titel)"
    journal = row.get("journal", "") or ""
    issued = row.get("issued", "") or ""
    authors = row.get("authors", "") or ""
    relevance = row.get("relevance_score", None)
    signal_score = row.get("signal_score", None)
    days_ago = row.get("days_ago", None)
    why = row.get("relevance_why", "") or ""
    abstract = row.get("abstract", "") or ""
    
    left, right = st.columns([0.07, 0.93])
    
    # Checkbox links
    with left:
        sel_key = _stable_sel_key(row.to_dict(), unique_suffix)
        if doi_norm:
            # Value wird berechnet aus dem globalen State, um Sync zu garantieren
            is_selected = doi_norm in st.session_state["selected_dois"]
            st.checkbox(
                " ",
                value=is_selected,
                key=sel_key,
                label_visibility="hidden",
                on_change=toggle_doi,
                args=(doi_norm, sel_key)
            )

    # Karte rechts
    with right:
        title_safe = html.escape(title)
        authors_safe = html.escape(authors)
        
        meta_parts = [journal, issued]
        # NEU: Relevanz prominent in der Meta-Zeile
        if relevance is not None and relevance != "" and not pd.isna(relevance):
            meta_parts.append(f"<b>Relevanz: {relevance}/100</b>")
        if signal_score is not None and signal_score != "" and not pd.isna(signal_score):
            meta_parts.append(f"<b>Signal: {signal_score}/100</b>")
        
        meta_text = " · ".join([x for x in meta_parts if x])
        
        # HTML-Sichere Links
        doi_safe = _to_http(doi_val)
        link_safe = link_val
        doi_val_safe = html.escape(doi_val)
        link_val_safe = html.escape(link_val)

        doi_html = ""
        if doi_val:
            doi_html = '<b>DOI:</b> <a href="' + doi_safe + '" target="_blank">' + doi_val_safe + '</a><br>'
            
        link_html = ""
        if link_val and link_val != doi_safe:
            link_html = '<b>URL:</b> <a href="' + link_safe + '" target="_blank">' + link_val_safe + '</a><br>'

        src = row.get("abstract_source", "") or ""
        src_html = ""
        if src:
            src_html = "<b>Abstract-Quelle:</b> " + html.escape(str(src)) + "<br>"
        
        if why and relevance is not None and not pd.isna(relevance):
            why_html = f"<div class='meta'><b>Warum relevant:</b> {html.escape(str(why))}</div>"
        else:
            why_html = ""

        if abstract:
            abstract_safe = html.escape(abstract)
            abstract_html = '<b>Abstract</b><br><p class="abstract">' + abstract_safe + '</p>'
        else:
            abstract_html = "<i>Kein Abstract vorhanden.</i>"

        chip_html = ""
        if days_ago is not None and not pd.isna(days_ago) and isinstance(days_ago, (int, float)):
            if days_ago <= 7:
                chip_html += "<span class='ps-chip'>NEW</span>"
        if relevance is not None and not pd.isna(relevance) and float(relevance) >= 80:
            chip_html += "<span class='ps-chip hot'>HOT</span>"

        card_html = (
            '<div class="result-card">'
            f'<h3>{title_safe}{chip_html}</h3>'
            f'<div class="meta">{meta_text}</div>'
            f'<div class="authors">{authors_safe}</div>'
            f'{why_html}'
            '<details>'
            '<summary>Details anzeigen</summary>'
            '<div>' +
            doi_html +
            link_html +
            src_html +
            '<br>' +
            abstract_html +
            '</div>'
            '</details>'
            '</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

def section_card(title: str, desc: str, key: str, default_open: bool = False, accent: bool = False, show_toggle: bool = True):
    if key not in st.session_state:
        st.session_state[key] = default_open
    with st.container(border=True):
        if accent:
            st.markdown("<div class='ps-callout'>Empfohlen</div>", unsafe_allow_html=True)
        st.markdown(f"### {title}")
        st.caption(desc)
        if show_toggle:
            st.toggle("Optionen anzeigen", key=key)
        else:
            st.session_state[key] = True
        body = st.container()
    return st.session_state[key], body