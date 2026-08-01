from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    groq_api_key: SecretStr | None = None
    groq_model: str = "qwen/qwen3.6-27b"
    groq_fallback_model: str = "groq/compound-mini"
    groq_audio_model: str = "whisper-large-v3-turbo"
    groq_api_base_url: str = "https://api.groq.com/openai/v1"
    ai_timeout_seconds: float = Field(default=180, gt=0, le=300)
    ai_max_retries: int = Field(default=1, ge=0, le=1)
    ai_input_max_length: int = Field(default=12_000, ge=100, le=100_000)
    frontend_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
    storage_directory: Path = PROJECT_ROOT / "storage"
    database_url: str = f"sqlite+pysqlite:///{(PROJECT_ROOT / 'storage' / 'tasklens.db').as_posix()}"
    max_upload_bytes: int = Field(default=10_485_760, ge=1_024, le=52_428_800)
    max_audio_bytes: int = Field(default=20_971_520, ge=1_024, le=26_214_400)
    max_file_text_length: int = Field(default=40_000, ge=1_000, le=200_000)
    max_generated_file_bytes: int = Field(default=2_097_152, ge=1_024, le=10_485_760)
    log_level: str = "INFO"
    allow_degraded_startup: bool = True
    testing: bool = False

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 빈 API 키 문자열을 설정되지 않은 값으로 정규화한다.
    @field_validator("groq_api_key", mode="before")
    @classmethod
    def empty_api_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # SQLite 이외의 데이터베이스 URL이 들어오지 않도록 검증한다.
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()
        supported_prefixes = ("sqlite+pysqlite://", "sqlite:///")
        if not normalized.startswith(supported_prefixes):
            raise ValueError("DATABASE_URL은 SQLite 형식이어야 합니다.")
        return normalized

    # 쉼표로 구분된 프론트엔드 출처 문자열을 CORS 목록으로 변환한다.
    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    # 로그 레벨 문자열을 대문자로 정규화한다.
    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()


# 환경변수를 읽고 저장 폴더를 준비한 설정 객체를 캐시해 반환한다.
@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_directory.mkdir(parents=True, exist_ok=True)
    return settings