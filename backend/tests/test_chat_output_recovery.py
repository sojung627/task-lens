import json

from backend.app.services.chat_service import ChatService


# 일반 자연어 응답이 502 없이 그대로 반환되는지 확인한다.
def test_plain_text_model_response_is_returned_without_502() -> None:
    reply, generated_files, analysis = ChatService._validate_output(
        "이력서의 핵심 경력과 기술을 정리했어요."
    )

    assert reply == "이력서의 핵심 경력과 기술을 정리했어요."
    assert generated_files == []
    assert analysis is None


# reply가 비어 있을 때 분석 요약에서 사용자 답변을 복구하는지 확인한다.
def test_empty_reply_is_recovered_from_analysis_summary() -> None:
    model_output = json.dumps(
        {
            "reply": "",
            "generated_files": [],
            "analysis": {
                "summary": "지원자의 AI 서비스 개발 경험이 핵심이에요.",
                "core_goal": "이력서 분석",
                "key_points": [],
                "decisions": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "이력서 핵심 내용 확인",
                        "description": None,
                        "order": 1,
                        "priority": "normal",
                        "deadline": None,
                        "assignee": None,
                        "submission_target": None,
                        "dependencies": [],
                        "completion_condition": None,
                        "status": "todo",
                        "completed": False,
                    }
                ],
                "confirmation_items": [],
                "difficult_terms": [],
                "ambiguities": [],
            },
        },
        ensure_ascii=False,
    )

    reply, generated_files, analysis = ChatService._validate_output(model_output)

    assert reply == "지원자의 AI 서비스 개발 경험이 핵심이에요."
    assert generated_files == []
    assert analysis is not None


# 닫힌 추론 태그 뒤의 JSON 답변만 사용자에게 전달되는지 확인한다.
def test_thinking_tag_before_json_is_removed() -> None:
    model_output = (
        "<think>내부 추론</think>\n"
        '{"reply":"분석을 완료했어요.","generated_files":[],"analysis":null}'
    )

    reply, generated_files, analysis = ChatService._validate_output(model_output)

    assert reply == "분석을 완료했어요."
    assert generated_files == []
    assert analysis is None

# 닫히지 않은 추론 태그 뒤의 JSON 답변을 복구하는지 확인한다.
def test_unclosed_thinking_tag_before_json_is_removed() -> None:
    # 닫히지 않은 추론 태그 뒤의 정상 JSON 응답만 사용자 답변으로 복구하는지 확인한다.
    model_output = (
        "<think>내부 추론이 길게 이어짐\n"
        '{"reply":"이력서의 강점과 보완점을 정리했어요.","generated_files":[],"analysis":null}'
    )

    reply, generated_files, analysis = ChatService._validate_output(model_output)

    assert reply == "이력서의 강점과 보완점을 정리했어요."
    assert generated_files == []
    assert analysis is None


# 추론 내용만 존재할 때 내부 사고 과정이 노출되지 않는지 확인한다.
def test_unclosed_thinking_only_is_not_exposed() -> None:
    # 최종 답변 없이 추론 내용만 온 경우 내부 사고 과정이 사용자에게 노출되지 않는지 확인한다.
    reply, generated_files, analysis = ChatService._validate_output(
        "<think>사용자 입력을 분석하는 내부 과정만 존재함"
    )

    assert reply == ""
    assert generated_files == []
    assert analysis is None
# 생성 파일 내용 때문에 전체 JSON이 깨져도 reply 문장만 복구하는지 확인한다.
def test_reply_is_recovered_when_generated_file_json_is_malformed() -> None:
    model_output = '''{
      "reply": "요청하신 고양이 하루 일과를 정리했어요.",
      "generated_files": [
        {"name": "고양이.pdf", "content": "%PDF-1.4
깨진 줄바꿈"}
      ]
    }'''

    reply, generated_files, analysis = ChatService._validate_output(model_output)

    assert reply == "요청하신 고양이 하루 일과를 정리했어요."
    assert generated_files == []
    assert analysis is None
# 두 번의 모델 응답이 모두 구조 오류여도 첨부 파일 요청을 안전한 결과로 복구하는지 확인한다.
def test_safe_fallback_creates_downloadable_file_for_attachment_request(tmp_path) -> None:
    from unittest.mock import Mock

    from backend.app.schemas.chat import ChatRequest, FileUploadPayload
    from backend.app.services.file_service import FileService

    settings = Mock()
    settings.storage_directory = tmp_path
    settings.max_upload_bytes = 5_000_000
    settings.max_generated_file_bytes = 5_000_000
    service = ChatService(settings, Mock(), FileService(settings))
    request = ChatRequest(
        message="짧게 간추려",
        files=[
            FileUploadPayload(
                name="과제01.txt",
                mime_type="text/plain",
                content_base64="7JWI64WV7ZWY7IS47JqU",
            )
        ],
    )
    upload = Mock(
        safe_name="과제01.txt",
        extension="txt",
        extracted_text="첫 번째 핵심 내용\n두 번째 핵심 내용",
    )

    reply, generated_files, analysis = service._safe_fallback_output(request, [upload])

    assert "첫 번째 핵심 내용" in reply
    assert generated_files[0]["name"] == "과제01_요약.txt"
    assert generated_files[0]["content"] == reply
    assert analysis is not None