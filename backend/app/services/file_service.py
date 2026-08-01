import base64
import binascii
import io
from pathlib import Path
from uuid import uuid4

from backend.app.core.config import Settings
from backend.app.schemas.chat import FileUploadPayload


class FileValidationError(Exception):
    pass


class FileReadError(Exception):
    pass


TEXT_EXTENSIONS = {
    "txt",
    "md",
    "csv",
    "json",
    "xml",
    "yaml",
    "yml",
    "py",
    "js",
    "jsx",
    "ts",
    "tsx",
    "html",
    "css",
    "sql",
    "java",
    "c",
    "cpp",
    "h",
    "log",
}
DOCUMENT_EXTENSIONS = TEXT_EXTENSIONS | {"pdf", "docx"}
AUDIO_EXTENSIONS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "ogg", "wav", "webm", "flac"}
UPLOAD_EXTENSIONS = DOCUMENT_EXTENSIONS | AUDIO_EXTENSIONS
GENERATED_EXTENSIONS = {"txt", "md", "csv", "json", "xml", "html", "css", "js", "ts", "py", "sql"}


class FileService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.upload_directory = settings.storage_directory / "files"
        self.upload_directory.mkdir(parents=True, exist_ok=True)

    def decode_upload(self, upload: FileUploadPayload) -> tuple[bytes, str, str]:
        safe_name = Path(upload.name).name
        if safe_name != upload.name or not safe_name:
            raise FileValidationError("올바르지 않은 파일명이에요.")

        extension = Path(safe_name).suffix.lower().lstrip(".")
        if extension not in UPLOAD_EXTENSIONS:
            supported = ", ".join(sorted(UPLOAD_EXTENSIONS))
            raise FileValidationError(
                f"{safe_name} 파일 형식은 지원하지 않아요. 지원 형식: {supported}"
            )

        try:
            content = base64.b64decode(upload.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise FileValidationError(f"{safe_name} 파일 데이터가 올바르지 않아요.") from exc

        if not content:
            raise FileValidationError(f"{safe_name} 파일이 비어 있어요.")
        if len(content) > self.settings.max_upload_bytes:
            raise FileValidationError(f"{safe_name} 파일은 업로드 제한 용량을 초과했어요.")
        return content, safe_name, extension

    def validate_generated_file(self, name: str, content: str) -> tuple[str, str, bytes]:
        safe_name = Path(name).name
        if safe_name != name or not safe_name:
            raise FileValidationError("AI가 생성한 파일명이 올바르지 않아요.")
        extension = Path(safe_name).suffix.lower().lstrip(".")
        if extension not in GENERATED_EXTENSIONS:
            raise FileValidationError(
                "생성 파일은 TXT, MD, CSV, JSON, XML, HTML, CSS, JS, TS, PY, SQL 형식만 지원해요."
            )
        encoded = content.encode("utf-8")
        if len(encoded) > self.settings.max_generated_file_bytes:
            raise FileValidationError("AI가 생성한 파일이 허용 용량을 초과했어요.")
        return safe_name, extension, encoded

    def save(self, content: bytes, extension: str) -> str:
        stored_name = f"{uuid4().hex}.{extension}"
        target = self.upload_directory / stored_name
        target.write_bytes(content)
        return stored_name

    def delete_stored(self, stored_name: str) -> None:
        path = self.upload_directory / Path(stored_name).name
        if path.is_file():
            path.unlink()

    def read_stored(self, stored_name: str) -> bytes:
        path = self.upload_directory / Path(stored_name).name
        if not path.is_file():
            raise FileReadError("파일을 찾을 수 없어요.")
        return path.read_bytes()

    def extract_text(self, content: bytes, extension: str) -> str:
        try:
            if extension in TEXT_EXTENSIONS:
                text = content.decode("utf-8-sig")
            elif extension == "pdf":
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(content))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            elif extension == "docx":
                from docx import Document

                document = Document(io.BytesIO(content))
                text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            elif extension in AUDIO_EXTENSIONS:
                return "[음성 파일은 음성 인식 단계에서 텍스트로 변환됩니다.]"
            else:
                raise FileValidationError("지원하지 않는 파일 형식이에요.")
        except UnicodeDecodeError as exc:
            raise FileReadError(f"{extension.upper()} 파일의 문자 인코딩을 읽지 못했어요.") from exc
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileReadError(f"{extension.upper()} 파일을 읽지 못했어요.") from exc

        normalized = text.strip()
        if not normalized:
            return "[파일에 읽을 수 있는 텍스트가 없음]"
        if len(normalized) > self.settings.max_file_text_length:
            return normalized[: self.settings.max_file_text_length] + "\n[이후 내용은 길이 제한으로 생략됨]"
        return normalized