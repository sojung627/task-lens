import base64
import binascii
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.app.core.config import get_settings
from backend.app.schemas.audio import AudioTranscriptionRequest, AudioTranscriptionResponse
from backend.app.services.transcription_service import AudioValidationError, TranscriptionService
from backend.app.services.task_analysis_service import (
    MissingApiKeyError,
    UpstreamAuthenticationError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.post("/transcribe", response_model=AudioTranscriptionResponse)
async def transcribe_audio(request: AudioTranscriptionRequest) -> AudioTranscriptionResponse:
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="녹음 데이터가 올바르지 않아요.") from exc

    filename = Path(request.name).name
    service = TranscriptionService(get_settings())
    try:
        text = await service.transcribe(
            content=content,
            filename=filename,
            mime_type=request.mime_type,
            language=request.language,
        )
    except AudioValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamAuthenticationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except UpstreamRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except UpstreamTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except UpstreamUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AudioTranscriptionResponse(text=text, model=service.settings.groq_audio_model)