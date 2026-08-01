from pydantic import BaseModel, Field, field_validator


class AudioTranscriptionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="audio/webm", max_length=100)
    content_base64: str = Field(min_length=1)
    language: str = Field(default="ko", min_length=2, max_length=10)

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return value.strip().lower()


class AudioTranscriptionResponse(BaseModel):
    text: str
    model: str