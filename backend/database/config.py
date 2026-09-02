import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CURRENT_DIR = Path(__file__).resolve().parent

# Turso (libSQL) connection details. If TURSO_DATABASE_URL is not set, we fall
# back to a local SQLite file (handy for local development without a Turso
# account). Set both env vars to switch to the hosted Turso database.
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

# TURSO_DATABASE_URL is given in the "libsql://<db>-<org>.turso.io" form
# (as shown on the Turso dashboard). The SQLAlchemy libsql dialect expects the
# host only, appended after "sqlite+libsql://", so the scheme is stripped here.
_TURSO_HOST = TURSO_DATABASE_URL.removeprefix("libsql://")

USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

if USE_TURSO:
    DATABASE_URL = f"sqlite+libsql://{_TURSO_HOST}?secure=true"
else:
    DB_PATH = CURRENT_DIR / "paperscout.db"
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
