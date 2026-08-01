import base64

import pytest

from backend.app.core.config import Settings
from backend.app.schemas.chat import FileUploadPayload
from backend.app.services.file_service import FileService, FileSizeLimitError


def make_file_service(tmp_path) -> FileService:
    settings = Settings(
        _env_file=None,
        storage_directory=tmp_path,
        max_chat_file_bytes=10_240,
    )
    return FileService(settings)


def make_upload(size: int) -> FileUploadPayload:
    return FileUploadPayload(
        name="sample.txt",
        mime_type="text/plain",
        content_base64=base64.b64encode(b"a" * size).decode("ascii"),
    )


# 10KB 파일은 채팅 첨부 파일로 허용되는지 확인한다.
def test_chat_file_at_limit_is_allowed(tmp_path) -> None:
    service = make_file_service(tmp_path)

    content, safe_name, extension = service.decode_upload(make_upload(10_240))

    assert len(content) == 10_240
    assert safe_name == "sample.txt"
    assert extension == "txt"


# 10KB를 1바이트라도 초과하면 사용자용 안내와 함께 차단되는지 확인한다.
def test_chat_file_over_limit_is_rejected(tmp_path) -> None:
    service = make_file_service(tmp_path)

    with pytest.raises(FileSizeLimitError, match="10KB 이하만 첨부"):
        service.decode_upload(make_upload(10_241))