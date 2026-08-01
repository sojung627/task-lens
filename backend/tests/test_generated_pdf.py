from pathlib import Path

from backend.app.core.config import Settings
from backend.app.schemas.chat import ChatRequest
from backend.app.services.chat_service import ChatService, PreparedUpload
from backend.app.services.file_service import FileService


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        groq_api_key="test-key",
        groq_model="qwen/qwen3.6-27b",
        groq_api_base_url="https://api.groq.test/openai/v1",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        storage_directory=tmp_path / "storage",
    )


def test_generated_pdf_is_rendered_as_real_pdf(tmp_path: Path) -> None:
    service = FileService(make_settings(tmp_path))
    name, extension, content = service.validate_generated_file(
        "자기소개서_요약.pdf",
        "지원자는 AI 서비스 개발 경험이 있습니다.",
    )

    assert name == "자기소개서_요약.pdf"
    assert extension == "pdf"
    assert content.startswith(b"%PDF-")


def test_existing_generated_text_formats_are_preserved(tmp_path: Path) -> None:
    service = FileService(make_settings(tmp_path))
    name, extension, content = service.validate_generated_file("summary.md", "# 요약")

    assert name == "summary.md"
    assert extension == "md"
    assert content == "# 요약".encode()


def test_summary_request_adds_pdf_when_model_omits_file(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = ChatService(settings, repository=None, file_service=FileService(settings))  # type: ignore[arg-type]
    upload = PreparedUpload(
        file_id="file-1",
        safe_name="자기소개서.pdf",
        extension="pdf",
        mime_type="application/pdf",
        content=b"pdf",
        extracted_text="자기소개서 내용",
    )

    files = service._ensure_generated_file(
        request=ChatRequest(message="이 자기소개서를 요약해줘", files=[]),
        uploads=[upload],
        reply="지원자의 핵심 경험 요약",
        generated_files=[],
    )

    assert files == [
        {
            "name": "자기소개서_요약.pdf",
            "content": "지원자의 핵심 경험 요약",
            "mime_type": "application/pdf",
        }
    ]