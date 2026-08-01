import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.chat import ChatRequest
from backend.app.schemas.task_analysis import TaskAnalysisResult
from backend.app.services.file_service import AUDIO_EXTENSIONS, FileService
from backend.app.services.task_analysis_service import (
    MissingApiKeyError,
    UpstreamAuthenticationError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from backend.app.services.transcription_service import TranscriptionService

logger = logging.getLogger("tasklens.chat")

SYSTEM_PROMPT = """당신은 TaskLens AI 업무 정리 에이전트입니다.
사용자와 자연스럽게 대화하되, 업무 지시·회의 기록·요청 목록이 들어오면 실행 가능한 구조로 정리하세요.
첨부 파일의 텍스트와 음성 인식 결과도 사용자 입력의 일부로 취급하세요.
원문에 없는 기한, 담당자, 제출 대상, 결정 사항은 만들지 마세요.
업무가 아닌 일반 대화라면 analysis는 null이어야 합니다.
회의 내용이면 summary에 전체 요약, key_points에 핵심 논점, decisions에 확정된 결정만 넣으세요.
업무가 있으면 모든 실제 행동을 tasks에 빠짐없이 나누고 선행 관계를 dependencies에 연결하세요.
확인이 필요한 내용은 confirmation_items, 애매하거나 누락된 지시는 ambiguities에 넣으세요.
낯선 전문 용어는 difficult_terms에 쉬운 설명과 함께 넣으세요.
사용자가 파일 생성을 명시적으로 요청한 경우에만 generated_files를 사용하세요.
반드시 JSON 객체 하나만 반환하세요. 마크다운 코드 블록이나 JSON 바깥 설명은 금지합니다.

반환 구조:
{
  "reply": "사용자에게 보여줄 한국어 답변",
  "generated_files": [
    {"name": "파일명.확장자", "content": "파일 전체 내용", "mime_type": "text/plain"}
  ],
  "analysis": null 또는 {
    "summary": "요약 또는 null",
    "core_goal": "핵심 목표",
    "key_points": ["핵심 내용"],
    "decisions": ["확정된 결정"],
    "tasks": [
      {
        "id": "task-1",
        "title": "실행할 작업",
        "description": null,
        "order": 1,
        "priority": "urgent|high|normal|low|unspecified",
        "deadline": null,
        "assignee": null,
        "submission_target": null,
        "dependencies": [],
        "completion_condition": null,
        "status": "todo",
        "completed": false
      }
    ],
    "confirmation_items": [],
    "difficult_terms": [{"term": "용어", "explanation": "쉬운 설명"}],
    "ambiguities": []
  }
}
"""


class ConversationNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class PreparedUpload:
    file_id: str
    safe_name: str
    extension: str
    mime_type: str
    content: bytes
    extracted_text: str


@dataclass(frozen=True)
class PreparedGeneratedFile:
    file_id: str
    safe_name: str
    extension: str
    mime_type: str
    content: bytes


class ChatService:
    def __init__(
            self,
            settings: Settings,
            repository: WorkspaceRepository,
            file_service: FileService,
            transcription_service: TranscriptionService | None = None,
            http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings
        self.repository = repository
        self.file_service = file_service
        self.transcription_service = transcription_service or TranscriptionService(settings)
        self.http_client = http_client

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def chat(self, request: ChatRequest) -> tuple[str, str, TaskAnalysisResult | None]:
        if self.settings.groq_api_key is None:
            raise MissingApiKeyError("AI 분석을 사용하려면 GROQ_API_KEY 설정이 필요해요.")

        is_new_conversation = request.conversation_id is None
        conversation_id = request.conversation_id or str(uuid4())
        if not is_new_conversation and not self.repository.conversation_exists(conversation_id):
            raise ConversationNotFoundError("선택한 대화를 찾을 수 없어요.")

        prepared_uploads = await self._prepare_uploads(request)
        history = self._history(conversation_id) if not is_new_conversation else []
        user_content = self._build_user_content(request.message, prepared_uploads)
        model_output = await self._request_model(history, user_content, correction=None)

        try:
            reply, generated_files, analysis = self._validate_output(model_output)
        except UpstreamResponseError as first_error:
            if self.settings.ai_max_retries == 0:
                raise
            logger.warning("chat_schema_correction_requested reason=%s", first_error)
            corrected_output = await self._request_model(
                history,
                user_content,
                correction=str(first_error),
            )
            reply, generated_files, analysis = self._validate_output(corrected_output)

        prepared_generated_files = self._prepare_generated_files(generated_files)
        stored_names: list[str] = []
        try:
            user_timestamp = self._timestamp()
            user_message_id = str(uuid4())
            user_file_rows = []
            for upload in prepared_uploads:
                stored_name = self.file_service.save(upload.content, upload.extension)
                stored_names.append(stored_name)
                user_file_rows.append(
                    (
                        upload.file_id,
                        conversation_id,
                        user_message_id,
                        upload.safe_name,
                        stored_name,
                        upload.extension,
                        upload.mime_type,
                        len(upload.content),
                        "user",
                        user_timestamp,
                    )
                )

            assistant_message_id = str(uuid4())
            assistant_timestamp = self._timestamp()
            assistant_file_rows = []
            for generated in prepared_generated_files:
                stored_name = self.file_service.save(generated.content, generated.extension)
                stored_names.append(stored_name)
                assistant_file_rows.append(
                    (
                        generated.file_id,
                        conversation_id,
                        assistant_message_id,
                        generated.safe_name,
                        stored_name,
                        generated.extension,
                        generated.mime_type,
                        len(generated.content),
                        "assistant",
                        assistant_timestamp,
                    )
                )

            self.repository.persist_chat_exchange(
                conversation_id=conversation_id,
                is_new_conversation=is_new_conversation,
                title=self._make_title(request, prepared_uploads),
                initial_preview=(request.message or prepared_uploads[0].safe_name)[:80],
                user_message=(user_message_id, request.message, user_timestamp),
                user_files=user_file_rows,
                assistant_message=(assistant_message_id, reply, assistant_timestamp),
                assistant_files=assistant_file_rows,
                analysis=analysis,
            )
            if analysis is not None:
                analysis = self.repository.get_analysis(conversation_id)
            return conversation_id, assistant_message_id, analysis
        except Exception:
            for stored_name in stored_names:
                self.file_service.delete_stored(stored_name)
            raise

    async def _prepare_uploads(self, request: ChatRequest) -> list[PreparedUpload]:
        prepared: list[PreparedUpload] = []
        for upload in request.files:
            content, safe_name, extension = self.file_service.decode_upload(upload)
            if extension in AUDIO_EXTENSIONS:
                extracted_text = await self.transcription_service.transcribe(
                    content=content,
                    filename=safe_name,
                    mime_type=upload.mime_type,
                    language="ko",
                )
            else:
                extracted_text = self.file_service.extract_text(content, extension)
            prepared.append(
                PreparedUpload(
                    file_id=str(uuid4()),
                    safe_name=safe_name,
                    extension=extension,
                    mime_type=upload.mime_type,
                    content=content,
                    extracted_text=extracted_text,
                )
            )
        return prepared

    def _prepare_generated_files(
            self,
            generated_files: list[dict[str, str]],
    ) -> list[PreparedGeneratedFile]:
        prepared: list[PreparedGeneratedFile] = []
        for generated in generated_files:
            safe_name, extension, content = self.file_service.validate_generated_file(
                generated["name"], generated["content"]
            )
            prepared.append(
                PreparedGeneratedFile(
                    file_id=str(uuid4()),
                    safe_name=safe_name,
                    extension=extension,
                    mime_type=generated.get("mime_type", "text/plain"),
                    content=content,
                )
            )
        return prepared

    @staticmethod
    def _make_title(request: ChatRequest, uploads: list[PreparedUpload]) -> str:
        source = request.message or (Path(uploads[0].safe_name).stem if uploads else "새 대화")
        normalized = re.sub(r"\s+", " ", source).strip()
        return normalized[:40] or "새 대화"

    def _history(self, conversation_id: str) -> list[dict[str, str]]:
        rows = self.repository.list_messages(conversation_id)[-12:]
        return [
            {"role": row["role"], "content": row["content"]}
            for row in rows
            if row["content"]
        ]

    @staticmethod
    def _build_user_content(message: str, uploads: list[PreparedUpload]) -> str:
        user_content = message or "첨부한 내용을 읽고 핵심과 실행할 업무를 정리해 주세요."
        if uploads:
            file_contexts = [
                f"파일명: {upload.safe_name}\n추출 내용:\n{upload.extracted_text}"
                for upload in uploads
            ]
            user_content += "\n\n첨부 파일 내용:\n" + "\n\n".join(file_contexts)
        return user_content

    async def _request_model(
            self,
            history: list[dict[str, str]],
            user_content: str,
            correction: str | None,
    ) -> str:
        final_user_content = user_content
        if correction:
            final_user_content = (
                f"원래 입력:\n{user_content}\n\n"
                f"이전 응답 오류:\n{correction}\n\n"
                "오류를 수정하고 지정된 JSON 객체 하나만 다시 반환하세요."
            )

        endpoint = f"{self.settings.groq_api_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *history,
                {"role": "user", "content": final_user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        client = self.http_client or httpx.AsyncClient()
        should_close = self.http_client is None
        try:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.settings.ai_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("AI 분석 시간이 초과됐어요. 다시 시도해 주세요.") from exc
        except httpx.RequestError as exc:
            raise UpstreamUnavailableError("AI 서비스에 연결할 수 없어요.") from exc
        finally:
            if should_close:
                await client.aclose()

        if response.status_code in {401, 403}:
            raise UpstreamAuthenticationError("AI 서비스 인증에 실패했어요.")
        if response.status_code == 429:
            raise UpstreamRateLimitError("현재 AI 요청이 많아요. 잠시 후 다시 시도해 주세요.")
        if response.status_code >= 500:
            raise UpstreamUnavailableError("AI 서비스를 잠시 사용할 수 없어요.")
        if response.status_code >= 400:
            logger.warning("chat_request_rejected status=%s body=%s", response.status_code, response.text[:500])
            raise UpstreamResponseError("AI가 요청을 처리하지 못했어요. 입력 내용을 확인해 주세요.")

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise UpstreamResponseError("AI 응답 형식이 올바르지 않아요.") from exc
        if not isinstance(content, str) or not content.strip():
            raise UpstreamResponseError("AI 답변이 비어 있어요.")
        return content.strip()

    @staticmethod
    def _validate_output(
            content: str,
    ) -> tuple[str, list[dict[str, str]], TaskAnalysisResult | None]:
        try:
            body: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            raise UpstreamResponseError(
                f"AI 응답 JSON 해석 실패: {exc.lineno}행 {exc.colno}열"
            ) from exc

        reply = body.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            raise UpstreamResponseError("AI 답변의 reply가 비어 있어요.")

        generated_files = body.get("generated_files", [])
        if not isinstance(generated_files, list):
            raise UpstreamResponseError("AI 생성 파일 목록 형식이 올바르지 않아요.")

        normalized_files: list[dict[str, str]] = []
        for item in generated_files:
            if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("name"), str)
                    or not isinstance(item.get("content"), str)
            ):
                raise UpstreamResponseError("AI 생성 파일 정보가 올바르지 않아요.")
            normalized_files.append(
                {
                    "name": item["name"],
                    "content": item["content"],
                    "mime_type": str(item.get("mime_type", "text/plain")),
                }
            )

        analysis_data = body.get("analysis")
        if analysis_data is None:
            analysis = None
        else:
            try:
                analysis = TaskAnalysisResult.model_validate(analysis_data)
            except ValidationError as exc:
                first_error = exc.errors()[0]
                location = ".".join(str(part) for part in first_error.get("loc", []))
                raise UpstreamResponseError(
                    f"AI 업무 분석 형식 오류: {location} - {first_error.get('msg', '검증 실패')}"
                ) from exc

        return reply.strip(), normalized_files, analysis