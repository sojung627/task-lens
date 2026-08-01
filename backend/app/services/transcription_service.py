import logging
from pathlib import Path

import httpx

from backend.app.core.config import Settings
from backend.app.services.task_analysis_service import (
    MissingApiKeyError,
    UpstreamAuthenticationError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

logger = logging.getLogger("tasklens.transcription")


class AudioValidationError(Exception):
    pass


class TranscriptionService:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.http_client = http_client

    async def transcribe(
            self,
            *,
            content: bytes,
            filename: str,
            mime_type: str,
            language: str = "ko",
    ) -> str:
        if self.settings.groq_api_key is None:
            raise MissingApiKeyError("음성 인식을 사용하려면 GROQ_API_KEY 설정이 필요해요.")
        if not content:
            raise AudioValidationError("녹음된 음성이 비어 있어요.")
        if len(content) > self.settings.max_audio_bytes:
            raise AudioValidationError("음성 파일이 업로드 제한 용량을 초과했어요.")

        safe_name = Path(filename).name
        if safe_name != filename or not safe_name:
            raise AudioValidationError("음성 파일명이 올바르지 않아요.")

        endpoint = f"{self.settings.groq_api_base_url.rstrip('/')}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.settings.groq_api_key.get_secret_value()}"}
        files = {"file": (safe_name, content, mime_type or "application/octet-stream")}
        data = {
            "model": self.settings.groq_audio_model,
            "language": language,
            "response_format": "json",
            "temperature": "0",
        }

        client = self.http_client or httpx.AsyncClient()
        should_close = self.http_client is None
        try:
            response = await client.post(
                endpoint,
                headers=headers,
                files=files,
                data=data,
                timeout=self.settings.ai_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("음성 인식 시간이 초과됐어요. 다시 시도해 주세요.") from exc
        except httpx.RequestError as exc:
            raise UpstreamUnavailableError("음성 인식 서비스에 연결할 수 없어요.") from exc
        finally:
            if should_close:
                await client.aclose()

        if response.status_code in {401, 403}:
            raise UpstreamAuthenticationError("음성 인식 서비스 인증에 실패했어요.")
        if response.status_code == 429:
            raise UpstreamRateLimitError("현재 음성 인식 요청이 많아요. 잠시 후 다시 시도해 주세요.")
        if response.status_code >= 500:
            raise UpstreamUnavailableError("음성 인식 서비스를 잠시 사용할 수 없어요.")
        if response.status_code >= 400:
            logger.warning("transcription_rejected status=%s body=%s", response.status_code, response.text[:500])
            raise UpstreamResponseError("음성 파일을 인식하지 못했어요. 녹음 상태를 확인해 주세요.")

        try:
            body = response.json()
        except ValueError as exc:
            raise UpstreamResponseError("음성 인식 응답 형식이 올바르지 않아요.") from exc
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise UpstreamResponseError("음성에서 인식된 문장이 없어요.")
        return text.strip()