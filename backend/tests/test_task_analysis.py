import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.services.task_analysis_service import (
    MissingApiKeyError,
    TaskAnalysisService,
    UpstreamAuthenticationError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
)


VALID_ANALYSIS = {
    "core_goal": "MCP 서버 예외 처리 테스트 완료",
    "tasks": [
        {
            "id": "task-1",
            "title": "허용되지 않은 Tool 호출 차단 확인",
            "description": None,
            "order": 1,
            "priority": "high",
            "deadline": "오늘 오후 5시까지",
            "assignee": None,
            "submission_target": None,
            "dependencies": [],
            "completion_condition": "허용되지 않은 Tool 호출이 차단됨",
        }
    ],
    "confirmation_items": ["제출 파일 형식을 윤 연구원님께 확인"],
    "difficult_terms": [
        {"term": "Tool", "explanation": "AI가 호출할 수 있는 기능"}
    ],
    "ambiguities": [],
}


def make_settings(**overrides: object) -> Settings:
    values = {
        "groq_api_key": "test-key",
        "groq_model": "qwen/qwen3.6-27b",
        "groq_api_base_url": "https://api.groq.test/openai/v1",
        "ai_timeout_seconds": 60,
        "ai_max_retries": 1,
        "ai_input_max_length": 12000,
        "frontend_origin": "http://localhost:5173",
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def groq_response(content: str | None = None, *, choices: object | None = None) -> dict:
    if choices is not None:
        return {"choices": choices}
    return {"choices": [{"message": {"content": content}}]}


@pytest.mark.asyncio
async def test_normal_long_instruction_succeeds() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=groq_response(json.dumps(VALID_ANALYSIS)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        result = await service.analyze("장문의 정상 업무 지시", "request-normal")

    assert result.core_goal == VALID_ANALYSIS["core_goal"]
    assert len(result.tasks) == 1


@pytest.mark.asyncio
async def test_invalid_json_is_corrected_once() -> None:
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        content = "not-json" if call_count == 1 else json.dumps(VALID_ANALYSIS)
        return httpx.Response(200, json=groq_response(content))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        result = await service.analyze("수정 요청이 필요한 지시", "request-retry")

    assert result.tasks
    assert call_count == 2


@pytest.mark.asyncio
async def test_missing_required_field_fails_after_one_retry() -> None:
    invalid = {"core_goal": "목표", "tasks": []}

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=groq_response(json.dumps(invalid)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        with pytest.raises(UpstreamResponseError):
            await service.analyze("업무", "request-invalid-schema")


@pytest.mark.asyncio
async def test_empty_content_is_upstream_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=groq_response(""))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        with pytest.raises(UpstreamResponseError):
            await service.analyze("업무", "request-empty")


@pytest.mark.asyncio
async def test_missing_choices_is_upstream_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        with pytest.raises(UpstreamResponseError):
            await service.analyze("업무", "request-no-choices")


@pytest.mark.asyncio
async def test_authentication_error_is_not_retried() -> None:
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        with pytest.raises(UpstreamAuthenticationError):
            await service.analyze("업무", "request-auth")

    assert call_count == 1


@pytest.mark.asyncio
async def test_rate_limit_is_not_retried() -> None:
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, json={"error": "rate limit"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        with pytest.raises(UpstreamRateLimitError):
            await service.analyze("업무", "request-rate-limit")

    assert call_count == 1


@pytest.mark.asyncio
async def test_timeout_is_raised_as_timeout_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TaskAnalysisService(make_settings(), client)
        with pytest.raises(UpstreamTimeoutError):
            await service.analyze("업무", "request-timeout")


@pytest.mark.asyncio
async def test_missing_api_key_stops_before_request() -> None:
    service = TaskAnalysisService(make_settings(groq_api_key=None))
    with pytest.raises(MissingApiKeyError):
        await service.analyze("업무", "request-no-key")


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": True}


@pytest.mark.parametrize("message", ["", "   "])
def test_blank_input_returns_422(message: str) -> None:
    response = TestClient(app).post("/api/tasks/analyze", json={"message": message})
    assert response.status_code == 422


def test_too_long_input_returns_422() -> None:
    response = TestClient(app).post(
        "/api/tasks/analyze",
        json={"message": "가" * 12001},
    )
    assert response.status_code == 422


def test_ai_service_failure_returns_503() -> None:
    response = TestClient(app).post(
        "/api/tasks/analyze",
        json={"message": "정상 길이의 업무 지시입니다."},
    )
    assert response.status_code == 503
    assert response.json()["detail"]