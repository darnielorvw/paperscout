import streamlit as st
import streamlit.components.v1 as components


def apply_custom_styles():
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

    CARD_STYLE_V3 = """
    <style>
        /*
        NEUE THEME-AWARE KARTEN (v3)
        Verwendet Streamlit CSS-Variablen, um sich an Light/Dark-Mode anzupassen.
        */
        .result-card {
            background: var(--ps-card);
            border: 1px solid var(--ps-card-border);
            border-left: 8px solid var(--ps-accent-2);
            border-radius: 16px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            box-shadow: var(--ps-shadow);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            backdrop-filter: blur(6px);
        }
        .result-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 18px 35px rgba(6,34,88,0.32);
        }
        .result-card h3 {
            color: var(--ps-ink);
            margin-top: 0;
            margin-bottom: 0.25rem;
            font-weight: 700;
        }
        .result-card .meta {
            color: var(--ps-ink-3);
            font-size: 0.9rem;
            margin-bottom: 0.6rem;
        }
        .result-card .authors {
            color: var(--ps-ink-2);
            font-size: 0.95rem;
            font-weight: 600;
        }
        .result-card details {
            margin-top: 1rem;
        }
        .result-card details summary {
            cursor: pointer;
            font-weight: 700;
            color: var(--ps-accent-text);
            font-size: 0.95rem;
            list-style-type: '✦ ';
        }
        .result-card details[open] summary {
            list-style-type: '▾ ';
        }
        .result-card details > div {
            background: var(--ps-detail-bg);
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin-top: 0.6rem;
            border: 1px solid var(--ps-card-border);
        }
        .result-card details .abstract {
            color: var(--ps-ink-2);
            white-space: pre-wrap;
            font-size: 0.92rem;
            line-height: 1.6;
        }
        .result-card details a {
            color: var(--ps-accent-2);
            text-decoration: underline;
            font-weight: 600;
        }
        .result-card details a:hover {
            text-decoration: underline;
        }

        .cluster-card {
            background: var(--ps-detail-bg);
            padding: 12px;
            border-radius: 12px;
            margin-bottom: 10px;
            border: 1px solid var(--ps-card-border);
            box-shadow: 0 8px 16px rgba(6,34,88,0.2);
        }
        .ps-chip {
            display: inline-block;
            padding: 0.12rem 0.5rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            background: var(--ps-accent-2);
            color: var(--ps-on-accent-2);
            margin-left: 0.35rem;
        }
        .ps-chip.hot {
            background: var(--ps-accent);
            color: var(--ps-on-accent-2);
        }
        .ps-callout {
            display: inline-block;
            padding: 0.18rem 0.6rem;
            border-radius: 999px;
            background: linear-gradient(135deg, var(--ps-accent), var(--ps-accent-2));
            color: var(--ps-on-accent);
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
        }
    </style>
    """
    st.markdown(CARD_STYLE_V3, unsafe_allow_html=True)

    # --- NEU: Anker für "Hoch" ---
    st.markdown("<a id='results_top'></a>", unsafe_allow_html=True) 

    # --- NEU: Link für "Runter" ---
    st.markdown(
        """
        <style>
            .link-container {
                text-align: right;
                margin-top: -2.5rem; 
                margin-bottom: 1rem;
            }
            .link-container a {
                text-decoration: underline;
                text-decoration-thickness: 1.5px;
                text-underline-offset: 2px;
                color: var(--ps-link);
                font-weight: 700;
                font-size: 0.9rem;
            }
        </style>
        <div class="link-container">
            <a href='#actions_bottom'>⬇️ Zum E-Mail Versand springen</a>
        </div>
        """, 
        unsafe_allow_html=True
    )

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

    # --- NEU: Link "Hoch" und Anker "Unten" ---
    st.markdown(
        """
        <style>
            .link-container-bottom {
                text-align: right;
                margin-bottom: -1.5rem;
            }
            .link-container-bottom a {
                text-decoration: underline;
                text-decoration-thickness: 1.5px;
                text-underline-offset: 2px;
                color: var(--ps-link);
                font-weight: 700;
                font-size: 0.9rem;
            }
        </style>
        <div class="link-container-bottom">
            <a href='#results_top'>⬆️ Zum Anfang der Liste springen</a>
        </div>
        """, 
        unsafe_allow_html=True
    )
    # Der Anker, zu dem der "Runter"-Link springt
    st.markdown("<a id='actions_bottom'></a>", unsafe_allow_html=True)