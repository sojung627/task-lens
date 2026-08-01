from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.app.core.config import get_settings
from backend.app.db.database import engine
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationRenameRequest,
    ConversationSummary,
    NotesUpdateRequest,
    ReminderCreateRequest,
    ReminderStatusRequest,
    ReminderSummary,
    TaskMutationResponse,
    TaskUpdatePayload,
    WorkspaceResponse,
)
from backend.app.schemas.task_analysis import TaskItem
from backend.app.services.chat_service import ChatService, ConversationNotFoundError
from backend.app.services.file_service import FileReadError, FileService, FileValidationError
from backend.app.services.task_analysis_service import (
    MissingApiKeyError,
    UpstreamAuthenticationError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from backend.app.services.transcription_service import AudioValidationError
from backend.app.services.workspace_service import WorkspaceService, display_time

router = APIRouter(prefix="/api", tags=["chat"])

repository = WorkspaceRepository(engine)


def get_chat_service() -> ChatService:
    settings = get_settings()
    return ChatService(settings, repository, FileService(settings))


def get_workspace_service() -> WorkspaceService:
    return WorkspaceService(repository)


def _raise_for_chat_error(exc: Exception) -> None:
    if isinstance(exc, ConversationNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (FileValidationError, AudioValidationError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, FileReadError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, MissingApiKeyError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, UpstreamAuthenticationError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, UpstreamRateLimitError):
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    if isinstance(exc, UpstreamTimeoutError):
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    if isinstance(exc, UpstreamUnavailableError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, UpstreamResponseError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


# -- workspace ------------------------------------------------------------


@router.get("/workspace", response_model=WorkspaceResponse)
def get_workspace(conversation_id: str | None = Query(default=None)) -> WorkspaceResponse:
    return get_workspace_service().get_workspace(conversation_id)


# -- chat -------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest) -> ChatResponse:
    chat_service = get_chat_service()
    try:
        conversation_id, assistant_message_id, analysis = await chat_service.chat(request)
    except Exception as exc:  # noqa: BLE001 - narrowed inside _raise_for_chat_error
        _raise_for_chat_error(exc)
        raise

    message = get_workspace_service().get_message(assistant_message_id)
    return ChatResponse(conversation_id=conversation_id, message=message, analysis=analysis)


# -- conversations ------------------------------------------------------------


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(conversation_id: str, request: ConversationRenameRequest) -> ConversationSummary:
    if not repository.rename_conversation(conversation_id, request.title):
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")
    row = repository.get_conversation(conversation_id)
    return ConversationSummary(
        id=row["id"],
        title=row["title"],
        preview=row["preview"],
        updatedAt=display_time(row["updated_at"]),
        status=row["status"],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def trash_conversation(conversation_id: str) -> None:
    if not repository.set_conversation_status(conversation_id, "trashed"):
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")


@router.post("/conversations/{conversation_id}/restore", status_code=204)
def restore_conversation(conversation_id: str) -> None:
    if not repository.set_conversation_status(conversation_id, "active"):
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")


@router.delete("/conversations/{conversation_id}/permanent", status_code=204)
def delete_conversation_permanently(conversation_id: str) -> None:
    if repository.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")

    settings = get_settings()
    file_service = FileService(settings)
    for file_row in repository.list_conversation_files(conversation_id):
        file_service.delete_stored(file_row["stored_name"])

    repository.delete_conversation(conversation_id)


@router.put("/conversations/{conversation_id}/notes", status_code=204)
def update_conversation_notes(conversation_id: str, request: NotesUpdateRequest) -> None:
    if not repository.update_notes(conversation_id, request.content):
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")


# -- tasks --------------------------------------------------------------------


@router.patch("/conversations/{conversation_id}/tasks/{task_id}", response_model=TaskMutationResponse)
def update_task(conversation_id: str, task_id: str, request: TaskUpdatePayload) -> TaskMutationResponse:
    analysis = repository.get_analysis(conversation_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="대화 또는 분석 결과를 찾을 수 없어요.")

    target_index = next(
        (index for index, task in enumerate(analysis.tasks) if task.id == task_id),
        None,
    )
    if target_index is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없어요.")

    updates = request.model_dump(exclude_unset=True)
    updated_task = analysis.tasks[target_index].model_copy(update=updates)
    updated_tasks = list(analysis.tasks)
    updated_tasks[target_index] = updated_task
    updated_analysis = analysis.model_copy(update={"tasks": updated_tasks})

    repository.save_analysis(conversation_id, updated_analysis)
    return TaskMutationResponse(analysis=updated_analysis, task=updated_task)


@router.delete("/conversations/{conversation_id}/tasks/{task_id}", response_model=TaskMutationResponse)
def delete_task(conversation_id: str, task_id: str) -> TaskMutationResponse:
    analysis = repository.get_analysis(conversation_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="대화 또는 분석 결과를 찾을 수 없어요.")

    if len(analysis.tasks) <= 1:
        raise HTTPException(status_code=409, detail="마지막 남은 작업은 삭제할 수 없어요.")

    remaining = [task for task in analysis.tasks if task.id != task_id]
    if len(remaining) == len(analysis.tasks):
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없어요.")

    reordered: list[TaskItem] = [
        task.model_copy(update={"order": position})
        for position, task in enumerate(remaining, start=1)
    ]
    updated_analysis = analysis.model_copy(update={"tasks": reordered})

    repository.save_analysis(conversation_id, updated_analysis)
    return TaskMutationResponse(analysis=updated_analysis, task=None)


# -- reminders ------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/reminders", response_model=ReminderSummary)
def create_reminder(conversation_id: str, request: ReminderCreateRequest) -> ReminderSummary:
    if not repository.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")

    reminder_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    remind_at = request.remind_at.astimezone(timezone.utc).isoformat()

    repository.add_reminder(
        reminder_id=reminder_id,
        conversation_id=conversation_id,
        task_id=request.task_id,
        message=request.message,
        remind_at=remind_at,
        status="pending",
        created_at=created_at,
    )
    row = repository.get_reminder(reminder_id)
    return WorkspaceService.reminder_summary(row)


@router.get("/reminders/due", response_model=list[ReminderSummary])
def get_due_reminders() -> list[ReminderSummary]:
    return get_workspace_service().get_due_reminders()


@router.patch("/reminders/{reminder_id}", response_model=ReminderSummary)
def update_reminder_status(reminder_id: str, request: ReminderStatusRequest) -> ReminderSummary:
    if not repository.update_reminder_status(reminder_id, request.status):
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없어요.")
    row = repository.get_reminder(reminder_id)
    return WorkspaceService.reminder_summary(row)


# -- files ------------------------------------------------------------------------


@router.get("/files/{file_id}/download")
def download_file(file_id: str) -> Response:
    file_row = repository.get_file(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없어요.")

    settings = get_settings()
    file_service = FileService(settings)
    try:
        content = file_service.read_stored(file_row["stored_name"])
    except FileReadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    encoded_name = quote(file_row["original_name"])
    return Response(
        content=content,
        media_type=file_row["mime_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
        },
    )