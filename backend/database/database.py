from database.config import DATABASE_URL
from sqlmodel import Session, create_engine

# check_same_thread=False ist eine SQLite-Besonderheit für FastAPI
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def get_session():
    """Dependency für API-Routen, um auf die DB zuzugreifen"""
    with Session(engine) as session:
        yield session