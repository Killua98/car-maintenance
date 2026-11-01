# backend/database.py
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

SQLITE_FILE_NAME = "garage.db"
DATABASE_DIR = Path("data")
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_URL = f"sqlite:///{DATABASE_DIR / SQLITE_FILE_NAME}"

engine = create_engine(
    SQLITE_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True
)


def create_db_and_tables():
    """Crea il file database e tutte le tabelle per i modelli registrati."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency di FastAPI per aprire e chiudere una sessione di database per ogni richiesta."""
    with Session(engine) as session:
        yield session
