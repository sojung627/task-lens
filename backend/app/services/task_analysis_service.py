import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.schemas.task_analysis import TaskAnalysisResult

logger = logging.getLogger("tasklens.ai")


class TaskAnalysisError(Exception):
    pass


class MissingApiKeyError(TaskAnalysisError):
    pass


class UpstreamAuthenticationError(TaskAnalysisError):
    pass


class UpstreamRateLimitError(TaskAnalysisError):
    pass


class UpstreamTimeoutError(TaskAnalysisError):
    pass


class UpstreamUnavailableError(TaskAnalysisError):
    pass


class UpstreamResponseError(TaskAnalysisError):
    pass


@dataclass(frozen=True)
class InvalidModelOutput:
    reason: str


SYSTEM_PROMPT = """당신은 한국어 업무 지시와 회의 기록을 실행 가능한 작업으로 구조화하는 분석기입니다.
반드시 JSON 객체 하나만 반환하세요. 마크다운 코드 블록과 설명문은 금지합니다.
원문에 없는 기한, 담당자, 제출 대상, 결정 사항을 만들지 말고 정보가 없으면 null 또는 빈 배열을 사용하세요.
확인이 필요한 대상은 담당자로 확정하지 말고 confirmation_items에 넣으세요.
조건부 작업과 선행 관계를 보존하고, 모든 실제 업무를 빠짐없이 tasks로 분리하세요.
회의 기록이면 summary에 전체 요약, key_points에 핵심 논점, decisions에 확정된 결정만 넣으세요.
어려운 용어가 없으면 difficult_terms는 빈 배열로 반환하세요.
애매하거나 누락된 지시는 ambiguities에 넣으세요.

반환 구조:
{
  "summary": "전체 요약 또는 null",
  "core_goal": "string",
  "key_points": ["string"],
  "decisions": ["string"],
  "tasks": [
    {
      "id": "task-1",
      "title": "string",
      "description": "string 또는 null",
      "order": 1,
      "priority": "urgent|high|normal|low|unspecified",
      "deadline": "원문 표현 또는 null",
      "assignee": "string 또는 null",
      "submission_target": "string 또는 null",
      "dependencies": ["선행 작업 id"],
      "completion_condition": "string 또는 null",
      "status": "todo",
      "completed": false
    }
  ],
  "confirmation_items": ["string"],
  "difficult_terms": [{"term": "string", "explanation": "string"}],
  "ambiguities": ["string"]
}
"""


class TaskAnalysisService:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.http_client = http_client

    async def analyze(self, message: str, request_id: str) -> TaskAnalysisResult:
        if self.settings.groq_api_key is None:
            raise MissingApiKeyError("GROQ_API_KEY가 설정되지 않았습니다.")

        first_content = await self._request_model(message, request_id, correction=None)
        first_result = self._parse_and_validate(first_content, request_id)
        if isinstance(first_result, TaskAnalysisResult):
            return first_result

        if self.settings.ai_max_retries == 0:
            raise UpstreamResponseError(first_result.reason)

        logger.warning(
            "schema_correction_requested request_id=%s reason=%s retry=1",
            request_id,
            first_result.reason,
        )
        corrected_content = await self._request_model(
            message,
            request_id,
            correction=first_result.reason,
        )
        corrected_result = self._parse_and_validate(corrected_content, request_id)
        if isinstance(corrected_result, TaskAnalysisResult):
            return corrected_result

        raise UpstreamResponseError(corrected_result.reason)

    async def _request_model(
            self,
            message: str,
            request_id: str,
            correction: str | None,
    ) -> str:
        user_content = message
        if correction:
            user_content = (
                f"원래 업무 지시:\n{message}\n\n"
                f"이전 응답 오류:\n{correction}\n\n"
                "오류를 수정하여 지정된 JSON 객체만 다시 반환하세요."
            )

        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.settings.groq_api_base_url.rstrip('/')}/chat/completions"
        started_at = time.perf_counter()
        logger.info(
            "ai_request_started request_id=%s model=%s correction=%s",
            request_id,
            self.settings.groq_model,
            bool(correction),
        )

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
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.error(
                "ai_request_failed request_id=%s error_type=timeout elapsed_ms=%s",
                request_id,
                elapsed_ms,
            )
            raise UpstreamTimeoutError("Groq API 요청 시간이 초과되었습니다.") from exc
        except httpx.RequestError as exc:
            logger.error(
                "ai_request_failed request_id=%s error_type=network reason=%s",
                request_id,
                type(exc).__name__,
            )
            raise UpstreamUnavailableError("Groq API에 연결할 수 없습니다.") from exc
        finally:
            if should_close:
                await client.aclose()

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "ai_response_received request_id=%s upstream_status=%s elapsed_ms=%s",
            request_id,
            response.status_code,
            elapsed_ms,
        )

        if response.status_code in {401, 403}:
            raise UpstreamAuthenticationError("Groq API 인증에 실패했습니다.")
        if response.status_code == 429:
            raise UpstreamRateLimitError("Groq API 호출 한도를 초과했습니다.")
        if response.status_code >= 500:
            raise UpstreamUnavailableError("Groq API 서비스를 사용할 수 없습니다.")
        if response.status_code >= 400:
            raise UpstreamResponseError(
                f"Groq API가 요청을 거부했습니다. status={response.status_code}"
            )

        return self._extract_content(response, request_id)

    @staticmethod
    def _extract_content(response: httpx.Response, request_id: str) -> str:
        try:
            body: dict[str, Any] = response.json()
        except ValueError as exc:
            logger.error(
                "ai_response_invalid request_id=%s error_type=non_json_body",
                request_id,
            )
            raise UpstreamResponseError("Groq API 응답 본문이 JSON이 아닙니다.") from exc

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            logger.error("empty_ai_response request_id=%s field=choices", request_id)
            raise UpstreamResponseError("Groq API 응답에 choices가 없습니다.")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            logger.error("empty_ai_response request_id=%s field=message", request_id)
            raise UpstreamResponseError("Groq API 응답에 message가 없습니다.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            logger.error("empty_ai_response request_id=%s field=content", request_id)
            raise UpstreamResponseError("Groq API 응답 content가 비어 있습니다.")

        logger.info("ai_content_received request_id=%s content_present=true", request_id)
        return content.strip()

    @staticmethod
    def _parse_and_validate(
            content: str,
            request_id: str,
    ) -> TaskAnalysisResult | InvalidModelOutput:
        try:
            parsed = json.loads(content)
            logger.info("json_parse_succeeded request_id=%s", request_id)
        except json.JSONDecodeError as exc:
            logger.error(
                "json_parse_failed request_id=%s error_type=invalid_json line=%s column=%s",
                request_id,
                exc.lineno,
                exc.colno,
            )
            return InvalidModelOutput(
                reason=f"JSON 파싱 실패: line={exc.lineno}, column={exc.colno}"
            )

        try:
            result = TaskAnalysisResult.model_validate(parsed)
        except ValidationError as exc:
            first_error = exc.errors()[0]
            field = ".".join(str(part) for part in first_error.get("loc", []))
            reason = first_error.get("msg", "스키마 검증 실패")
            logger.error(
                "schema_validation_failed request_id=%s field=%s error_type=%s",
                request_id,
                field,
                first_error.get("type", "validation_error"),
            )
            return InvalidModelOutput(reason=f"스키마 검증 실패: {field} - {reason}")

        logger.info("schema_validation_succeeded request_id=%s", request_id)
        return result