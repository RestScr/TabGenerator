from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings

settings = get_settings()
database_url = URL.create(
    "mysql+pymysql",
    username=settings.mysql_user,
    password=settings.mysql_password.get_secret_value(),
    host=settings.mysql_host,
    port=settings.mysql_port,
    database=settings.mysql_database,
)

engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
