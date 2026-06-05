import os
from typing import Optional

import streamlit as st

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
except Exception:
    pass
# ==========================================

# --- SMTP aus Secrets/Env laden (robust) ---
def setup_smtp_from_secrets_or_env():
    # Streamlit secrets object might not be available in all contexts
    secrets_obj = getattr(st, "secrets", None) if "streamlit" in globals() else None

    def read_secret(key: str) -> Optional[str]:
        if secrets_obj is None: return None
        try:
            val = secrets_obj[key]
            val = str(val).strip()
            return val if val else None
        except Exception: return None

    def setdef(key: str, default: Optional[str] = None):
        val = read_secret(key)
        if val is None: val = os.environ.get(key)
        if val is None: val = default
        if val is not None: os.environ[key] = str(val)

    setdef("EMAIL_HOST", "smtp.gmail.com")
    setdef("EMAIL_PORT", "587")
    setdef("EMAIL_USE_TLS", "true")
    setdef("EMAIL_USE_SSL", "false")
    setdef("EMAIL_FROM")
    setdef("EMAIL_USER")
    setdef("EMAIL_PASSWORD")
    setdef("EMAIL_SENDER_NAME", "paperscout")

setup_smtp_from_secrets_or_env()

# Hardcoded values (can be overridden by env vars or st.secrets)
HARDCODED_KEY = ""
HARDCODED_CROSSREF_MAIL = ""
if HARDCODED_KEY:
    os.environ["PAPERSCOUT_OPENAI_API_KEY"] = HARDCODED_KEY
if HARDCODED_CROSSREF_MAIL:
    os.environ["CROSSREF_MAILTO"] = HARDCODED_CROSSREF_MAIL