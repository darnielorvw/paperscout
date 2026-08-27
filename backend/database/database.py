from database.config import DATABASE_URL
from sqlmodel import Session, create_engine

# check_same_thread=False is a SQLite quirk required for FastAPI
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def get_session():
    """Dependency for API routes to access the DB"""
    with Session(engine) as session:
        yield session