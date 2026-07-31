import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from backend.app.core.config import get_settings
from backend.app.schemas.task_analysis import AnalyzeTaskRequest, AnalyzeTaskResponse
from backend.app.services.task_analysis_service import (
    MissingApiKeyError,
    TaskAnalysisService,
    UpstreamAuthenticationError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

router = APIRouter(prefix="/api/tasks", tags=["task-analysis"])
logger = logging.getLogger("tasklens.api")


def get_task_analysis_service() -> TaskAnalysisService:
    return TaskAnalysisService(get_settings())


@router.post("/analyze", response_model=AnalyzeTaskResponse)
async def analyze_task(request: AnalyzeTaskRequest) -> AnalyzeTaskResponse:
    request_id = str(uuid4())
    path = "/api/tasks/analyze"
    logger.info(
        "request_received request_id=%s path=%s input_length=%s",
        request_id,
        path,
        len(request.message),
    )

    try:
        service = get_task_analysis_service()
        analysis = await service.analyze(request.message, request_id)
        response = AnalyzeTaskResponse(
            request_id=request_id,
            model=service.settings.groq_model,
            analysis=analysis,
        )
    except MissingApiKeyError as exc:
        _log_failure(request_id, 503, "missing_api_key", "configuration")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamAuthenticationError as exc:
        _log_failure(request_id, 502, "authentication_failed", "ai_request")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except UpstreamRateLimitError as exc:
        _log_failure(request_id, 429, "rate_limit", "ai_request")
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except UpstreamTimeoutError as exc:
        _log_failure(request_id, 504, "timeout", "ai_request")
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except UpstreamUnavailableError as exc:
        _log_failure(request_id, 503, "upstream_unavailable", "ai_request")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamResponseError as exc:
        _log_failure(request_id, 502, "invalid_upstream_response", "validation")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "unexpected_error request_id=%s stage=internal error_type=%s",
            request_id,
            type(exc).__name__,
        )
        _log_failure(request_id, 500, "internal_error", "internal")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 내부 오류가 발생했습니다.",
        ) from exc

    logger.info("response_completed request_id=%s status_code=200", request_id)
    return response


def _log_failure(request_id: str, status_code: int, error_type: str, stage: str) -> None:
    logger.error(
        "response_completed request_id=%s status_code=%s error_type=%s stage=%s",
        request_id,
        status_code,
        error_type,
        stage,
    )
