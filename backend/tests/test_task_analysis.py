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
@pytest.mark.asyncio
async def test_uploaded_file_analysis_returns_checklist(tmp_path) -> None:
    import base64
    from sqlalchemy import create_engine

    from backend.app.repositories.workspace_repository import WorkspaceRepository
    from backend.app.schemas.chat import ChatRequest
    from backend.app.services.chat_service import ChatService
    from backend.app.services.file_service import FileService

    response_body = {
        "reply": "파일 분석을 완료했어요. 체크리스트를 확인해 주세요.",
        "generated_files": [],
        "analysis": VALID_ANALYSIS,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        assert "첨부 파일이 있으면 reply와 analysis를 반드시 함께 생성" in request_body["messages"][0]["content"]
        assert "response_format" not in request_body
        return httpx.Response(200, json=groq_response(json.dumps(response_body)))

    database_path = tmp_path / "analysis.db"
    settings = make_settings(
        storage_directory=tmp_path / "storage",
        database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
    )
    engine = create_engine(settings.database_url)
    repository = WorkspaceRepository(engine)
    repository.create_tables()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = ChatService(settings, repository, FileService(settings), http_client=client)
        conversation_id, _, analysis = await service.chat(
            ChatRequest(
                message="이 파일을 분석해줘",
                files=[
                    {
                        "name": "업무.txt",
                        "mime_type": "text/plain",
                        "content_base64": base64.b64encode("업무 내용".encode()).decode(),
                    }
                ],
            )
        )

    assert conversation_id
    assert analysis is not None
    assert analysis.tasks[0].title == "허용되지 않은 Tool 호출 차단 확인"


@pytest.mark.asyncio
async def test_uploaded_file_summary_creates_downloadable_markdown(tmp_path) -> None:
    import base64
    from sqlalchemy import create_engine

    from backend.app.repositories.workspace_repository import WorkspaceRepository
    from backend.app.schemas.chat import ChatRequest
    from backend.app.services.chat_service import ChatService
    from backend.app.services.file_service import FileService

    response_body = {
        "reply": "문서의 핵심 내용을 요약했어요.",
        "generated_files": [],
        "analysis": None,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        assert "요약 요청" in request_body["messages"][0]["content"]
        assert "response_format" not in request_body
        return httpx.Response(200, json=groq_response(json.dumps(response_body)))

    database_path = tmp_path / "summary.db"
    settings = make_settings(
        storage_directory=tmp_path / "storage",
        database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
    )
    engine = create_engine(settings.database_url)
    repository = WorkspaceRepository(engine)
    repository.create_tables()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = ChatService(settings, repository, FileService(settings), http_client=client)
        conversation_id, assistant_message_id, analysis = await service.chat(
            ChatRequest(
                message="이 파일을 요약해줘",
                files=[
                    {
                        "name": "이력서.txt",
                        "mime_type": "text/plain",
                        "content_base64": base64.b64encode("경력과 기술 내용".encode()).decode(),
                    }
                ],
            )
        )

    generated_files = repository.list_message_files(assistant_message_id)
    assert conversation_id
    assert analysis is not None
    assert len(generated_files) == 1
    assert generated_files[0]["original_name"] == "이력서_요약.txt"
    stored_content = FileService(settings).read_stored(generated_files[0]["stored_name"]).decode()
    assert "문서의 핵심 내용을 요약했어요." in stored_content