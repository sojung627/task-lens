import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.db.database import create_database_if_missing, engine, ping_database
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.routers.audio import router as audio_router
from backend.app.routers.chat import router as chat_router
from backend.app.routers.task_analysis import router as task_analysis_router

configure_logging()
logger = logging.getLogger("tasklens.startup")
settings = get_settings()
startup_repository = WorkspaceRepository(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_ready = False
    try:
        create_database_if_missing()
        startup_repository.create_tables()
        app.state.database_ready = ping_database()
        logger.info("database_initialized ready=%s", app.state.database_ready)
    except (SQLAlchemyError, OSError, ValueError) as exc:
        logger.exception("database_initialization_failed error_type=%s", type(exc).__name__)
        if not settings.allow_degraded_startup:
            raise
    yield


app = FastAPI(
    title="TaskLens API",
    description="음성·문서·장문 업무 지시를 실행 가능한 체크리스트로 자동 정리하는 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(task_analysis_router)
app.include_router(chat_router)
app.include_router(audio_router)


@app.get("/health")
def health_check() -> dict[str, str | bool]:
    database_ready = ping_database()
    return {
        "status": "ok" if database_ready else "degraded",
        "database": database_ready,
    }


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "TaskLens backend is running"}