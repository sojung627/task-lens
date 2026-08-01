import base64
import json

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.chat import ChatRequest
from backend.app.services.chat_service import ChatService
from backend.app.services.file_service import FileService


# 테스트용 설정을 실제 환경 파일과 분리해 생성한다.
def make_settings(tmp_path, **overrides: object) -> Settings:
    values = {
        "groq_api_key": "test-key",
        "groq_model": "qwen/qwen3.6-27b",
        "groq_fallback_model": "groq/compound-mini",
        "groq_api_base_url": "https://api.groq.test/openai/v1",
        "ai_timeout_seconds": 60,
        "ai_input_max_length": 12_000,
        "storage_directory": tmp_path / "storage",
        "database_url": f"sqlite+pysqlite:///{(tmp_path / 'tasklens.db').as_posix()}",
        "max_file_text_length": 40_000,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


# Groq 성공 응답 형식을 간단히 생성한다.
def groq_response(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


# 기본 모델의 TPM 413을 받으면 고용량 대체 모델로 전환하는지 확인한다.
@pytest.mark.asyncio
async def test_tpm_413_falls_back_without_reserving_8192_output_tokens(tmp_path) -> None:
    requested_models: list[str] = []

    # 첫 요청에는 TPM 413을 반환하고 두 번째 대체 모델 요청에는 성공 응답을 반환한다.
    async def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        requested_models.append(request_body["model"])
        assert "max_completion_tokens" not in request_body
        if len(requested_models) == 1:
            assert request_body["reasoning_format"] == "hidden"
            return httpx.Response(
                413,
                json={
                    "error": {
                        "message": "Limit 8000, Requested 9594 on tokens per minute (TPM)",
                        "type": "tokens",
                        "code": "rate_limit_exceeded",
                    }
                },
            )
        assert "reasoning_format" not in request_body
        return httpx.Response(200, json=groq_response("정상 답변이에요."))

    settings = make_settings(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = ChatService(
            settings,
            repository=None,  # type: ignore[arg-type]
            file_service=FileService(settings),
            http_client=client,
        )
        result = await service._request_model([], "1")

    assert result == "정상 답변이에요."
    assert requested_models == ["qwen/qwen3.6-27b", "groq/compound-mini"]


# 숫자와 한글·영어 12000자가 요청 스키마를 통과하는지 확인한다.
def test_numbers_and_12000_character_messages_are_valid() -> None:
    assert ChatRequest(message="1").message == "1"
    assert len(ChatRequest(message="가" * 12_000).message) == 12_000
    assert len(ChatRequest(message="a" * 12_000).message) == 12_000


# 한글과 영어 12000자가 기본 모델 413 후 대체 모델에서 정상 처리되는지 확인한다.
@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["가" * 12_000, "a" * 12_000])
async def test_12000_character_message_succeeds_through_fallback(tmp_path, message: str) -> None:
    call_count = 0

    # 긴 입력의 기본 모델 요청을 거절하고 대체 모델 요청에는 성공 응답을 반환한다.
    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        request_body = json.loads(request.content)
        assert request_body["messages"][-1]["content"] == message
        assert "max_completion_tokens" not in request_body
        if call_count == 1:
            return httpx.Response(
                413,
                json={
                    "error": {
                        "message": "tokens per minute (TPM) limit exceeded",
                        "type": "tokens",
                        "code": "rate_limit_exceeded",
                    }
                },
            )
        return httpx.Response(200, json=groq_response("긴 입력도 정상 처리했어요."))

    settings = make_settings(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = ChatService(
            settings,
            repository=None,  # type: ignore[arg-type]
            file_service=FileService(settings),
            http_client=client,
        )
        result = await service._request_model([], message)

    assert result == "긴 입력도 정상 처리했어요."
    assert call_count == 2


# 여러 파일의 추출 내용이 총 파일 입력 한도 안에서 모두 포함되는지 확인한다.
def test_file_context_uses_total_budget_across_all_files(tmp_path) -> None:
    from backend.app.services.chat_service import PreparedUpload

    settings = make_settings(tmp_path, max_file_text_length=4_000)
    service = ChatService(
        settings,
        repository=None,  # type: ignore[arg-type]
        file_service=FileService(settings),
    )
    uploads = [
        PreparedUpload(
            file_id="1",
            safe_name="첫째.txt",
            extension="txt",
            mime_type="text/plain",
            content=b"",
            extracted_text="가" * 5_000,
        ),
        PreparedUpload(
            file_id="2",
            safe_name="둘째.txt",
            extension="txt",
            mime_type="text/plain",
            content=b"",
            extracted_text="나" * 5_000,
        ),
    ]

    user_content = service._build_user_content("파일을 요약해줘", uploads)

    assert "첫째.txt" in user_content
    assert "둘째.txt" in user_content
    assert "가" * 2_000 in user_content
    assert "가" * 2_001 not in user_content
    assert "나" * 2_000 in user_content
    assert "나" * 2_001 not in user_content


# 실제 파일 요청이 413 후 대체 모델에서 성공해 저장까지 완료되는지 확인한다.
@pytest.mark.asyncio
async def test_file_chat_succeeds_after_tpm_fallback(tmp_path) -> None:
    from sqlalchemy import create_engine

    call_count = 0

    # 파일 채팅의 첫 요청에는 TPM 413을 반환하고 대체 모델 요청에는 성공 응답을 반환한다.
    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        request_body = json.loads(request.content)
        assert "max_completion_tokens" not in request_body
        if call_count == 1:
            return httpx.Response(
                413,
                json={
                    "error": {
                        "message": "tokens per minute (TPM) limit exceeded",
                        "type": "tokens",
                        "code": "rate_limit_exceeded",
                    }
                },
            )
        assert request_body["model"] == "groq/compound-mini"
        return httpx.Response(200, json=groq_response("파일의 핵심 내용을 정리했어요."))

    settings = make_settings(tmp_path)
    engine = create_engine(settings.database_url)
    repository = WorkspaceRepository(engine)
    repository.create_tables()
    encoded_file = base64.b64encode("파일 안의 숫자 123과 한글 내용".encode()).decode()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = ChatService(
            settings,
            repository,
            FileService(settings),
            http_client=client,
        )
        conversation_id, assistant_message_id, _ = await service.chat(
            ChatRequest(
                message="이 파일을 요약해줘 123",
                files=[
                    {
                        "name": "업무.txt",
                        "mime_type": "text/plain",
                        "content_base64": encoded_file,
                    }
                ],
            )
        )

    assert conversation_id
    assert assistant_message_id
    assert call_count == 2
    assert repository.list_message_files(assistant_message_id)