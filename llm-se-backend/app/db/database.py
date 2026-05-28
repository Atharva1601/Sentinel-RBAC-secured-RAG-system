import os
import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

log = structlog.get_logger()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Local SQLite fallback
DB_PATH = os.path.join(BASE_DIR, "data", "users.db")
SQLITE_URL = f"sqlite:///{DB_PATH}"

# Production Postgres (Render)
DATABASE_URL = os.getenv("DATABASE_URL", SQLITE_URL)
log.info("database_url_resolved", url=DATABASE_URL[:40] if DATABASE_URL else "None")
# Ensure Postgres URLs work with SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
