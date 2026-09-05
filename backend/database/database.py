from sqlmodel import Session, create_engine

from database.config import DATABASE_URL, TURSO_AUTH_TOKEN, USE_TURSO

if USE_TURSO:
    # The libsql dialect talks to Turso over HTTP(S), so no sqlite3-specific
    # connect_args (like check_same_thread) are needed here - only the auth token.
    engine = create_engine(DATABASE_URL, connect_args={"auth_token": TURSO_AUTH_TOKEN})
else:
    # check_same_thread=False is a SQLite quirk required for FastAPI
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def get_session():
    """Dependency for API routes to access the DB"""
    with Session(engine) as session:
        yield session
