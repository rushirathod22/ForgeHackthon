from __future__ import annotations

from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

try:
    from db.models import Base
except ModuleNotFoundError:
    from backend.db.models import Base

DB_PATH = Path(__file__).resolve().parents[1] / "cctv_metadata.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables and ensure schema migrations."""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for table, col in [
            ("tracks", "embedding_json TEXT"),
            ("tracks", "visual_attributes_json TEXT"),
            ("events", "embedding_json TEXT"),
            ("events", "visual_attributes_json TEXT"),
        ]:
            try:
                col_name = col.split()[0]
                res = conn.exec_driver_sql(f"PRAGMA table_info({table});").fetchall()
                existing_cols = [row[1] for row in res]
                if col_name not in existing_cols:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col};")
                    conn.commit()
            except Exception:
                pass


def get_db() -> Generator[Session, None, None]:
    """Dependency generator for DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
