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


# 숫자와 한글·영어·특수문자가 요청 스키마를 통과하는지 확인한다.
def test_numbers_and_12000_character_messages_are_valid() -> None:
    assert ChatRequest(message="1").message == "1"
    assert len(ChatRequest(message="가" * 12_000).message) == 12_000
    assert len(ChatRequest(message="a" * 12_000).message) == 12_000
    assert ChatRequest(message="!@#$%^&*()_+-=[]{};':\",./<>?\\|").message


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
    assert len(user_content) <= settings.ai_input_max_length
    assert "가" * 1_000 in user_content
    assert "나" * 1_000 in user_content


# 긴 대화 기록과 파일 내용이 함께 있어도 모델 입력 한도를 넘지 않는지 확인한다.
def test_long_history_and_file_content_stay_within_input_budget(tmp_path) -> None:
    from backend.app.services.chat_service import PreparedUpload

    settings = make_settings(tmp_path, ai_input_max_length=12_000, max_file_text_length=40_000)
    service = ChatService(
        settings,
        repository=None,  # type: ignore[arg-type]
        file_service=FileService(settings),
    )
    upload = PreparedUpload(
        file_id="1",
        safe_name="긴문서.txt",
        extension="txt",
        mime_type="text/plain",
        content=b"",
        extracted_text="파일본문" * 20_000,
    )
    user_content = service._build_user_content("요약해줘", [upload])
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "이전대화" * 2_000}
        for index in range(20)
    ]
    trimmed_history = service._trim_history(history, user_content)

    dynamic_input_length = len(user_content) + sum(
        len(message["content"]) for message in trimmed_history
    )
    assert len(user_content) <= settings.ai_input_max_length
    assert dynamic_input_length <= settings.ai_input_max_length


# 기본 모델의 일반 400 오류도 대체 모델로 전환해 502를 막는지 확인한다.
@pytest.mark.asyncio
async def test_primary_model_400_uses_fallback_model(tmp_path) -> None:
    requested_models: list[str] = []

    # 첫 모델의 요청 형식 오류 뒤 대체 모델에서 정상 답변을 반환한다.
    async def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        requested_models.append(request_body["model"])
        if len(requested_models) == 1:
            return httpx.Response(400, json={"error": {"message": "unsupported field"}})
        return httpx.Response(200, json=groq_response("대체 모델 정상 답변이에요."))

    settings = make_settings(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = ChatService(
            settings,
            repository=None,  # type: ignore[arg-type]
            file_service=FileService(settings),
            http_client=client,
        )
        result = await service._request_model([], "특수문자 !@#$와 한글 English 123")

    assert result == "대체 모델 정상 답변이에요."
    assert requested_models == ["qwen/qwen3.6-27b", "groq/compound-mini"]


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


# AI 설정이 없어도 사용자 메시지와 첨부 파일 자체는 정상 저장되는지 확인한다.
@pytest.mark.asyncio
async def test_file_and_special_character_chat_are_saved_without_api_key(tmp_path) -> None:
    from sqlalchemy import create_engine

    settings = make_settings(tmp_path, groq_api_key=None)
    engine = create_engine(settings.database_url)
    repository = WorkspaceRepository(engine)
    repository.create_tables()
    encoded_file = base64.b64encode("한글 English 123 !@#$%^&*()".encode()).decode()
    service = ChatService(settings, repository, FileService(settings))

    conversation_id, assistant_message_id, analysis = await service.chat(
        ChatRequest(
            message="요약해줘: 한글 English 123 !@#$%^&*()",
            files=[
                {
                    "name": "특수문자.txt",
                    "mime_type": "text/plain",
                    "content_base64": encoded_file,
                }
            ],
        )
    )

    stored_messages = repository.list_messages(conversation_id)
    assert [message["role"] for message in stored_messages] == ["user", "assistant"]
    assert repository.list_conversation_files(conversation_id)
    assert assistant_message_id == stored_messages[-1]["id"]
    assert analysis is not None