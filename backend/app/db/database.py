from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings

settings = get_settings()
database_url = make_url(settings.database_url)
def create_database_if_missing() -> None:
    """SQLite 데이터베이스 파일을 저장할 폴더를 준비합니다."""
    if database_url.get_backend_name() != "sqlite":
        raise ValueError("TaskLens는 SQLite DATABASE_URL만 지원합니다.")

    database_path = database_url.database
    if database_path and database_path != ":memory:":
        from pathlib import Path

        Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def build_engine(url: URL | None = None) -> Engine:
    target_url = url or database_url
    options: dict[str, object] = {"pool_pre_ping": True}
    if target_url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        options["pool_recycle"] = 3600

    target_engine = create_engine(target_url, **options)
    if target_url.get_backend_name() == "sqlite":

        @event.listens_for(target_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return target_engine


engine = build_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def ping_database(target_engine: Engine = engine) -> bool:
    try:
        with target_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def get_database_session() -> Iterator[Session]:
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()