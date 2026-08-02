import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
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
사용자의 입력을 빠짐없이 읽고 자연스러운 최종 답변만 작성하세요.
숫자, 한글, 영어, 긴 문장과 첨부 파일의 추출 내용을 모두 정상적인 사용자 입력으로 취급하세요.
내부 추론 과정, 사고 과정, JSON, XML, 태그, 코드 블록 껍데기는 출력하지 마세요.
첨부 파일이 있으면 파일 내용을 바탕으로 사용자가 요청한 분석·요약·질문 답변을 수행하세요.
첨부 파일이 있으면 반드시 아래 구조의 JSON 객체 하나만 반환하고 코드 블록은 사용하지 마세요.
reply에는 사용자에게 보여 줄 자연스러운 최종 답변을 넣고 analysis에는 실제 분석 결과를 넣으세요.
analysis.tasks는 파일에 포함된 서로 다른 실행 업무를 각각 분리해 모두 생성하세요.
서로 다른 업무를 한 항목으로 합치지 말고 "AI 분석 결과 검토" 같은 공통 임시 제목은 절대 사용하지 마세요.
첨부 파일이 없는 일반 대화만 JSON이 아닌 자연스러운 최종 답변을 허용합니다.
{
  "reply": "사용자에게 보여 줄 답변",
  "generated_files": [],
  "analysis": {
    "summary": "전체 요약 또는 null",
    "core_goal": "핵심 목표",
    "key_points": ["핵심 내용"],
    "decisions": [],
    "tasks": [
      {
        "id": "task-1",
        "title": "실제 업무 제목",
        "description": "세부 설명 또는 null",
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
    "difficult_terms": [],
    "ambiguities": []
  }
}
요약 요청에서는 원문의 핵심을 빠뜨리지 말고 간결하게 정리하세요.
원문에 없는 사실, 기한, 담당자, 제출 대상, 결정 사항은 만들지 마세요.
사용자가 파일 생성을 요청해도 실제 파일 저장은 TaskLens 서버가 담당합니다.
생성할 파일의 최종 본문만 답변으로 작성하세요.
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
    # 채팅 처리에 필요한 설정·저장소·파일·음성·HTTP 의존성을 초기화한다.
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

    # 현재 UTC 시각을 ISO 문자열로 반환한다.
    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    # 사용자 메시지와 첨부 파일을 AI에 전달하고 대화·분석·생성 파일을 저장한다.
    async def chat(self, request: ChatRequest) -> tuple[str, str, TaskAnalysisResult | None]:
        is_new_conversation = request.conversation_id is None
        conversation_id = request.conversation_id or str(uuid4())
        if not is_new_conversation and not self.repository.conversation_exists(conversation_id):
            raise ConversationNotFoundError("선택한 대화를 찾을 수 없어요.")

        prepared_uploads = await self._prepare_uploads(request)
        history = self._history(conversation_id) if not is_new_conversation else []
        try:
            if self.settings.groq_api_key is None:
                raise MissingApiKeyError("AI 분석을 사용하려면 GROQ_API_KEY 설정이 필요해요.")
            user_content = self._build_user_content(request.message, prepared_uploads)
            model_output = await self._request_model(history, user_content)
            reply, generated_files, analysis = self._validate_output(model_output)
        except (
                MissingApiKeyError,
                UpstreamAuthenticationError,
                UpstreamRateLimitError,
                UpstreamResponseError,
                UpstreamTimeoutError,
                UpstreamUnavailableError,
        ) as exc:
            logger.warning("chat_safe_fallback reason=%s", type(exc).__name__)
            reply, generated_files, analysis = self._safe_fallback_output(
                request,
                prepared_uploads,
            )

        analysis = self._ensure_analysis(request, prepared_uploads, reply, analysis)
        generated_files = self._ensure_generated_file(
            request=request,
            uploads=prepared_uploads,
            reply=reply,
            generated_files=generated_files,
        )
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

    # 업로드 파일을 검증하고 텍스트 또는 음성 인식 결과로 변환한다.
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


    # 요청 문구 비교를 위해 공백을 제거하고 소문자로 정규화한다.
    @staticmethod
    def _normalized_message(message: str) -> str:
        return re.sub(r"\s+", "", message).lower()

    # 사용자 문구가 파일 요약 요청인지 판별한다.
    @classmethod
    def _is_summary_request(cls, message: str) -> bool:
        normalized = cls._normalized_message(message)
        return any(
            keyword in normalized
            for keyword in ("요약", "핵심정리", "간단히정리", "간추려", "간추림")
        )

    # 사용자 문구가 다운로드 가능한 파일 생성 요청인지 판별한다.
    @classmethod
    def _is_file_generation_request(cls, message: str) -> bool:
        normalized = cls._normalized_message(message)
        return any(
            keyword in normalized
            for keyword in ("파일로", "파일생성", "만들어줘", "작성해줘", "저장해줘", "다운로드")
        ) or cls._is_summary_request(message)

    # 사용자 문구에서 명시된 출력 파일 확장자를 추출한다.
    @staticmethod
    def _requested_extension(message: str) -> str | None:
        matches = re.findall(
            r"(?<![a-z0-9])\.?(docx|json|yaml|html|jsx|tsx|cpp|txt|md|csv|xml|yml|css|js|ts|py|sql|java|c|h|log|pdf)(?![a-z0-9])",
            message.lower(),
        )
        return matches[-1] if matches else None

    # 요청과 원본 파일 형식에 맞는 기본 출력 확장자를 결정한다.
    def _default_output_extension(self, message: str, upload: PreparedUpload) -> str:
        requested = self._requested_extension(message)
        if requested:
            return requested
        if upload.extension in AUDIO_EXTENSIONS:
            return "txt"
        if upload.extension in self.file_service.generated_extensions:
            return upload.extension
        return "md"

    # 모델이 파일을 누락해도 파일 생성 요청에는 다운로드 결과를 보장한다.
    def _ensure_generated_file(
            self,
            request: ChatRequest,
            uploads: list[PreparedUpload],
            reply: str,
            generated_files: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """파일 생성 요청에서는 모델 누락과 관계없이 다운로드 파일을 보장한다."""
        if not uploads or not self._is_file_generation_request(request.message):
            return generated_files
        requested_extension = self._requested_extension(request.message)
        if generated_files:
            if not requested_extension:
                return generated_files
            return [
                {
                    **generated,
                    "name": f"{Path(generated['name']).stem}.{requested_extension}",
                    "mime_type": self.file_service.mime_type_for_extension(requested_extension),
                }
                for generated in generated_files
            ]

        upload = uploads[0]
        extension = self._default_output_extension(request.message, upload)
        suffix = "요약" if self._is_summary_request(request.message) else "결과"
        output_name = f"{Path(upload.safe_name).stem}_{suffix}.{extension}"
        return [
            {
                "name": output_name,
                "content": reply,
                "mime_type": self.file_service.mime_type_for_extension(extension),
            }
        ]

    # 구조화 분석이 누락됐을 때 AI 답변과 파일 내용에서 실제 체크리스트 제목을 복구한다.
    @staticmethod
    def _fallback_task_titles(
            uploads: list[PreparedUpload],
            reply: str,
    ) -> list[str]:
        sources = [reply, *(upload.extracted_text for upload in uploads)]
        marked_candidates: list[str] = []
        plain_candidates: list[str] = []
        ignored_sentences = {
            "파일을 정상적으로 받았어요.",
            "파일 분석을 완료했어요.",
            "분석을 완료했어요.",
            "체크리스트를 확인해 주세요.",
        }

        for source_index, source in enumerate(sources):
            for raw_line in source.splitlines():
                compact_line = re.sub(r"\s+", " ", raw_line).strip()
                if not compact_line:
                    continue

                has_list_marker = bool(
                    re.match(r"^(?:[-*•]+|\d+[.)]|[가-힣][.)])\s*", compact_line)
                )
                normalized_line = re.sub(
                    r"^(?:[-*•]+|\d+[.)]|[가-힣][.)])\s*",
                    "",
                    compact_line,
                ).strip()
                if (
                        len(normalized_line) < 4
                        or normalized_line in ignored_sentences
                        or normalized_line.startswith("[") and normalized_line.endswith("]")
                ):
                    continue

                title = normalized_line[:160].rstrip()
                if has_list_marker:
                    marked_candidates.append(title)
                elif source_index > 0:
                    plain_candidates.append(title)

        candidates = marked_candidates if marked_candidates else plain_candidates
        unique_titles: list[str] = []
        seen_titles: set[str] = set()
        for candidate in candidates:
            comparison_key = candidate.casefold()
            if comparison_key in seen_titles:
                continue
            seen_titles.add(comparison_key)
            unique_titles.append(candidate)
            if len(unique_titles) == 12:
                break

        if unique_titles:
            return unique_titles

        source_stem = Path(uploads[0].safe_name).stem if uploads else "첨부 파일"
        return [f"{source_stem} 내용 확인"]

    # 첨부 파일 요청에서 분석 구조가 빠졌을 때 파일 내용 기반 분석 결과를 생성한다.
    @staticmethod
    def _ensure_analysis(
            request: ChatRequest,
            uploads: list[PreparedUpload],
            reply: str,
            analysis: TaskAnalysisResult | None,
    ) -> TaskAnalysisResult | None:
        if analysis is not None or not uploads:
            return analysis

        source_name = uploads[0].safe_name
        key_points = [line.strip(" -•") for line in reply.splitlines() if line.strip()][:10]
        task_titles = ChatService._fallback_task_titles(uploads, reply)
        return TaskAnalysisResult.model_validate(
            {
                "summary": reply[:4000],
                "core_goal": f"{source_name} 요청 결과 확인",
                "key_points": key_points or [reply[:500]],
                "decisions": [],
                "tasks": [
                    {
                        "id": f"task-{index}",
                        "title": title,
                        "description": f"{source_name}에서 확인한 실행 항목입니다.",
                        "order": index,
                        "priority": "unspecified",
                        "deadline": None,
                        "assignee": None,
                        "submission_target": None,
                        "dependencies": [],
                        "completion_condition": None,
                        "status": "todo",
                        "completed": False,
                    }
                    for index, title in enumerate(task_titles, start=1)
                ],
                "confirmation_items": [],
                "difficult_terms": [],
                "ambiguities": [],
            }
        )

    # 외부 AI가 응답하지 못해도 사용자 입력과 첨부 파일을 저장할 안전한 결과를 만든다.
    def _safe_fallback_output(
            self,
            request: ChatRequest,
            uploads: list[PreparedUpload],
    ) -> tuple[str, list[dict[str, str]], TaskAnalysisResult | None]:
        if not uploads:
            return (
                "메시지를 정상적으로 받았어요. "
                "AI 답변 생성이 지연되고 있어 잠시 후 다시 질문해 주세요.",
                [],
                None,
            )

        readable_sections: list[str] = []
        per_file_limit = max(500, min(4_000, self.settings.ai_input_max_length // len(uploads)))
        for upload in uploads:
            extracted_text = upload.extracted_text.strip()
            if len(extracted_text) > per_file_limit:
                extracted_text = extracted_text[:per_file_limit].rstrip() + "\n[이후 내용 생략]"
            readable_sections.append(f"[{upload.safe_name}]\n{extracted_text}")

        reply = "파일을 정상적으로 받았어요.\n\n" + "\n\n".join(readable_sections)
        generated_files = self._ensure_generated_file(request, uploads, reply, [])
        analysis = self._ensure_analysis(request, uploads, reply, None)
        return reply, generated_files, analysis

    # 모델이 생성한 파일 정보를 검증하고 저장 가능한 바이트 데이터로 변환한다.
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

    # 사용자 메시지 또는 첨부 파일명을 바탕으로 대화 제목을 만든다.
    @staticmethod
    def _make_title(request: ChatRequest, uploads: list[PreparedUpload]) -> str:
        source = request.message or (Path(uploads[0].safe_name).stem if uploads else "새 대화")
        normalized = re.sub(r"\s+", " ", source).strip()
        return normalized[:40] or "새 대화"

    # 최근 대화 기록을 AI API 메시지 형식으로 조회한다.
    def _history(self, conversation_id: str) -> list[dict[str, str]]:
        rows = self.repository.list_messages(conversation_id)[-12:]
        return [
            {"role": row["role"], "content": row["content"]}
            for row in rows
            if row["content"]
        ]

    # 사용자 문구와 모든 첨부 파일의 추출 텍스트를 설정된 총량 안에서 결합한다.
    def _build_user_content(self, message: str, uploads: list[PreparedUpload]) -> str:
        total_input_budget = self.settings.ai_input_max_length
        user_content = message or "첨부한 내용을 읽고 핵심과 실행할 업무를 정리해 주세요."
        if not uploads:
            return user_content[:total_input_budget]

        message_budget = max(256, total_input_budget // 3)
        if len(user_content) > message_budget:
            user_content = user_content[:message_budget].rstrip() + "\n[요청 일부 생략]"

        section_header = "\n\n첨부 파일 내용:\n"
        file_labels = [f"파일명: {upload.safe_name}\n추출 내용:\n" for upload in uploads]
        structural_length = len(user_content) + len(section_header) + sum(map(len, file_labels))
        total_file_budget = min(
            self.settings.max_file_text_length,
            max(0, total_input_budget - structural_length),
        )
        per_file_budget = total_file_budget // len(uploads)
        file_contexts: list[str] = []
        for upload, file_label in zip(uploads, file_labels, strict=True):
            extracted_text = upload.extracted_text[:per_file_budget]
            if len(upload.extracted_text) > per_file_budget:
                omission_notice = "\n[파일 내용 일부 생략]"
                notice_budget = max(0, per_file_budget - len(omission_notice))
                extracted_text = upload.extracted_text[:notice_budget] + omission_notice
            file_contexts.append(file_label + extracted_text)
        combined_content = user_content + section_header + "\n\n".join(file_contexts)
        return combined_content[:total_input_budget]

    # 현재 요청 크기에 맞춰 가장 최근 대화 기록만 모델 입력에 포함한다.
    def _trim_history(
            self,
            history: list[dict[str, str]],
            user_content: str,
    ) -> list[dict[str, str]]:
        total_input_budget = self.settings.ai_input_max_length
        remaining_budget = max(0, total_input_budget - len(user_content))
        selected_reversed: list[dict[str, str]] = []
        for message in reversed(history):
            content = message.get("content", "")
            if len(content) > remaining_budget:
                break
            selected_reversed.append(message)
            remaining_budget -= len(content)
        return list(reversed(selected_reversed))

    # 지정 모델에 맞는 Groq 요청 본문을 구성한다.
    @staticmethod
    def _build_model_payload(
            model: str,
            history: list[dict[str, str]],
            user_content: str,
            include_reasoning_format: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *history,
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
        }
        if include_reasoning_format:
            payload["reasoning_format"] = "hidden"
        return payload

    # Groq에 한 번 요청하고 네트워크 계층의 예외를 서비스 예외로 변환한다.
    async def _send_model_request(
            self,
            client: httpx.AsyncClient,
            endpoint: str,
            headers: dict[str, str],
            payload: dict[str, Any],
    ) -> httpx.Response:
        try:
            return await client.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.settings.ai_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("AI 분석 시간이 초과됐어요. 다시 시도해 주세요.") from exc
        except httpx.RequestError as exc:
            raise UpstreamUnavailableError("AI 서비스에 연결할 수 없어요.") from exc

    # Groq의 413 응답이 모델 TPM 한도 초과인지 확인한다.
    @staticmethod
    def _is_tpm_rejection(response: httpx.Response) -> bool:
        if response.status_code != 413:
            return False
        try:
            error = response.json().get("error", {})
        except ValueError:
            return False
        error_code = str(error.get("code", "")).lower()
        error_type = str(error.get("type", "")).lower()
        error_message = str(error.get("message", "")).lower()
        return (
                error_code == "rate_limit_exceeded"
                or error_type == "tokens"
                or "tokens per minute" in error_message
                or "tpm" in error_message
        )

    # 모델별 입력 형식·용량·일시 장애이면 설정된 대체 모델을 사용할지 결정한다.
    @staticmethod
    def _should_use_fallback(response: httpx.Response) -> bool:
        if response.status_code in {401, 403, 429}:
            return False
        return response.status_code >= 400

    # Groq HTTP 응답을 사용자용 모델 문자열로 검증해 반환한다.
    @staticmethod
    def _extract_model_content(response: httpx.Response) -> str:
        if response.status_code in {401, 403}:
            raise UpstreamAuthenticationError("AI 서비스 인증에 실패했어요.")
        if response.status_code == 429:
            raise UpstreamRateLimitError("현재 AI 요청이 많아요. 잠시 후 다시 시도해 주세요.")
        if response.status_code == 413:
            logger.warning(
                "chat_request_rejected status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            if ChatService._is_tpm_rejection(response):
                raise UpstreamRateLimitError(
                    "현재 모델의 처리 가능한 토큰 한도를 초과했어요. 잠시 후 다시 시도해 주세요."
                )
            raise UpstreamResponseError("AI에 전달할 내용이 너무 커요.")
        if response.status_code >= 500:
            raise UpstreamUnavailableError("AI 서비스를 잠시 사용할 수 없어요.")
        if response.status_code >= 400:
            logger.warning(
                "chat_request_rejected status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            raise UpstreamResponseError("AI가 요청을 처리하지 못했어요. 입력 내용을 확인해 주세요.")

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise UpstreamResponseError("AI 응답 형식이 올바르지 않아요.") from exc
        if not isinstance(content, str) or not content.strip():
            raise UpstreamResponseError("AI 답변이 비어 있어요.")
        return content.strip()

    # 기본 모델이 TPM 한도를 넘으면 고용량 대체 모델로 한 번 전환해 최종 답변을 받는다.
    async def _request_model(
            self,
            history: list[dict[str, str]],
            user_content: str,
    ) -> str:
        endpoint = f"{self.settings.groq_api_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        trimmed_history = self._trim_history(history, user_content)
        primary_payload = self._build_model_payload(
            model=self.settings.groq_model,
            history=trimmed_history,
            user_content=user_content,
            include_reasoning_format=True,
        )

        client = self.http_client or httpx.AsyncClient()
        should_close = self.http_client is None
        try:
            response = await self._send_model_request(
                client=client,
                endpoint=endpoint,
                headers=headers,
                payload=primary_payload,
            )
            fallback_model = self.settings.groq_fallback_model.strip()
            should_fallback = (
                    self._should_use_fallback(response)
                    and fallback_model
                    and fallback_model != self.settings.groq_model
            )
            if should_fallback:
                logger.warning(
                    "chat_model_fallback primary_model=%s fallback_model=%s status=%s",
                    self.settings.groq_model,
                    fallback_model,
                    response.status_code,
                )
                fallback_payload = self._build_model_payload(
                    model=fallback_model,
                    history=trimmed_history,
                    user_content=user_content,
                    include_reasoning_format=False,
                )
                response = await self._send_model_request(
                    client=client,
                    endpoint=endpoint,
                    headers=headers,
                    payload=fallback_payload,
                )
            return self._extract_model_content(response)
        finally:
            if should_close:
                await client.aclose()

    # 모델 응답에서 코드 블록과 추론 태그를 제거해 최종 답변만 남긴다.
    @staticmethod
    def _clean_model_text(content: str) -> str:
        """모델 응답에서 코드 블록과 노출된 추론 영역을 제거하고 최종 답변만 남긴다."""
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.I | re.S)

        # 닫히지 않은 <think> 뒤에 정상 JSON이 이어진 경우 JSON 답변부터 복구한다.
        if re.search(r"<think>", cleaned, flags=re.I):
            json_start = cleaned.find("{")
            if json_start >= 0:
                candidate = cleaned[json_start:].strip()
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    cleaned = candidate
                else:
                    cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.I | re.S)
            else:
                cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.I | re.S)

        return cleaned.strip()

    # JSON 전체가 깨져도 reply 문자열 값만 안전하게 추출한다.
    @staticmethod
    def _extract_reply_from_malformed_json(content: str) -> str:
        reply_key_match = re.search(r'["\']reply["\']\s*:\s*', content, flags=re.I)
        if reply_key_match is None:
            return ""

        value_start = reply_key_match.end()
        while value_start < len(content) and content[value_start].isspace():
            value_start += 1
        if value_start >= len(content) or content[value_start] not in {'"', "'"}:
            return ""

        quote = content[value_start]
        escaped = False
        value_end = value_start + 1
        while value_end < len(content):
            current = content[value_end]
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == quote:
                raw_value = content[value_start:value_end + 1]
                if quote == '"':
                    try:
                        decoded = json.loads(raw_value)
                        return decoded.strip() if isinstance(decoded, str) else ""
                    except json.JSONDecodeError:
                        pass
                return bytes(raw_value[1:-1], "utf-8").decode("unicode_escape").strip()
            value_end += 1
        return ""

    # 사용자 화면에 노출되면 안 되는 추론 태그와 구조화 응답 껍데기를 제거한다.
    @classmethod
    def _sanitize_reply(cls, reply: str) -> str:
        cleaned = cls._clean_model_text(reply)
        cleaned = re.sub(
            r"<(?:think|thinking|analysis|reasoning|reflection|scratchpad)[^>]*>.*?</(?:think|thinking|analysis|reasoning|reflection|scratchpad)>",
            "",
            cleaned,
            flags=re.I | re.S,
        )
        cleaned = re.sub(
            r"</?(?:think|thinking|analysis|reasoning|reflection|scratchpad)[^>]*>",
            "",
            cleaned,
            flags=re.I,
        )
        cleaned = re.sub(r"^\s*(?:최종\s*답변|final\s*answer)\s*[:：]\s*", "", cleaned, flags=re.I)
        return cleaned.strip()

    # JSON 응답의 reply가 비었을 때 분석이나 생성 파일 내용에서 답변을 복구한다.
    @staticmethod
    def _reply_from_body(body: dict[str, Any]) -> str:
        """reply가 비어 있어도 모델이 만든 유효한 내용에서 답변을 복구한다."""
        reply = body.get("reply")
        if isinstance(reply, str) and reply.strip():
            return reply.strip()

        analysis_data = body.get("analysis")
        if isinstance(analysis_data, dict):
            for key in ("summary", "core_goal"):
                value = analysis_data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            key_points = analysis_data.get("key_points")
            if isinstance(key_points, list):
                points = [str(item).strip() for item in key_points if str(item).strip()]
                if points:
                    return "\n".join(f"- {point}" for point in points)

        generated_files = body.get("generated_files")
        if isinstance(generated_files, list):
            for item in generated_files:
                if not isinstance(item, dict):
                    continue
                file_content = item.get("content")
                if isinstance(file_content, str) and file_content.strip():
                    return file_content.strip()

        return ""

    # 모델 응답을 JSON 또는 자연어로 해석하고 화면 표시용 결과로 정규화한다.
    @classmethod
    def _validate_output(
            cls,
            content: str,
    ) -> tuple[str, list[dict[str, str]], TaskAnalysisResult | None]:
        normalized_content = cls._clean_model_text(content)
        try:
            parsed = json.loads(normalized_content)
            body: dict[str, Any] = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            start_index = normalized_content.find("{")
            end_index = normalized_content.rfind("}")
            if start_index >= 0 and end_index > start_index:
                try:
                    parsed = json.loads(normalized_content[start_index:end_index + 1])
                    body = parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    recovered_reply = cls._extract_reply_from_malformed_json(normalized_content)
                    if recovered_reply:
                        return cls._sanitize_reply(recovered_reply), [], None
                    # JSON이 아닌 정상 자연어 응답만 화면에 전달하고 구조 문자열은 숨긴다.
                    if normalized_content.lstrip().startswith(("{", "[")):
                        raise UpstreamResponseError(
                            "AI 답변을 화면용 문장으로 변환하지 못했어요."
                        ) from None
                    return cls._sanitize_reply(normalized_content), [], None
            else:
                # JSON이 아닌 정상 자연어 응답을 그대로 사용자에게 전달한다.
                return cls._sanitize_reply(normalized_content), [], None

        reply = cls._reply_from_body(body)
        if not reply:
            recovered_reply = cls._extract_reply_from_malformed_json(normalized_content)
            if recovered_reply:
                reply = recovered_reply
            else:
                raise UpstreamResponseError("AI 답변에서 사용자용 문장을 찾지 못했어요.")
        reply = cls._sanitize_reply(reply)

        generated_files = body.get("generated_files", [])
        normalized_files: list[dict[str, str]] = []
        if isinstance(generated_files, list):
            for item in generated_files:
                if (
                        not isinstance(item, dict)
                        or not isinstance(item.get("name"), str)
                        or not isinstance(item.get("content"), str)
                ):
                    continue
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
                logger.warning("chat_analysis_validation_skipped reason=%s", exc.errors()[0])
                analysis = None

        return reply.strip(), normalized_files, analysis