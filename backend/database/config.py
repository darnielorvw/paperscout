from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent

DB_PATH = CURRENT_DIR / "paperscout.db"

DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
