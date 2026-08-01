from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.schemas.task_analysis import (
    Priority,
    TaskAnalysisResult,
    TaskItem,
    TaskStatus,
)


class FileUploadPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="application/octet-stream", max_length=150)
    content_base64: str = Field(min_length=1)


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=36)
    message: str = Field(default="", max_length=12_000)
    files: list[FileUploadPayload] = Field(default_factory=list, max_length=10)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_message_or_file(self) -> "ChatRequest":
        if not self.message and not self.files:
            raise ValueError("메시지 또는 파일을 입력해 주세요.")
        return self


class FileSummary(BaseModel):
    id: str
    name: str
    extension: str
    uploadedAt: str
    sizeLabel: str
    downloadUrl: str
    generatedBy: str


class AttachmentSummary(BaseModel):
    id: str
    name: str
    extension: str
    downloadUrl: str
    generatedBy: str


class MessageSummary(BaseModel):
    id: str
    role: str
    content: str
    createdAt: str
    attachments: list[AttachmentSummary]


class ConversationSummary(BaseModel):
    id: str
    title: str
    updatedAt: str
    preview: str | None = None
    status: str = "active"


class ReminderSummary(BaseModel):
    id: str
    conversationId: str
    taskId: str | None = None
    message: str
    remindAt: str
    status: str


class WorkspaceResponse(BaseModel):
    conversations: list[ConversationSummary] = Field(default_factory=list)
    trashedConversations: list[ConversationSummary] = Field(default_factory=list)
    recentFiles: list[FileSummary] = Field(default_factory=list)
    sourceFiles: list[FileSummary] = Field(default_factory=list)
    activeConversationId: str | None = None
    messages: list[MessageSummary] = Field(default_factory=list)
    analysis: TaskAnalysisResult | None = None
    notes: str = ""
    reminders: list[ReminderSummary] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageSummary
    analysis: TaskAnalysisResult | None = None


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("대화 제목을 입력해 주세요.")
        return normalized


class NotesUpdateRequest(BaseModel):
    content: str = Field(default="", max_length=50_000)


class ReminderCreateRequest(BaseModel):
    task_id: str | None = Field(default=None, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    remind_at: datetime

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("알림 내용을 입력해 주세요.")
        return normalized


class ReminderStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"pending", "delivered", "dismissed"}:
            raise ValueError("올바르지 않은 알림 상태입니다.")
        return value


class TaskUpdatePayload(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: Priority | None = None
    deadline: str | None = None
    assignee: str | None = None
    submission_target: str | None = None
    completion_condition: str | None = None
    status: TaskStatus | None = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "TaskUpdatePayload":
        if all(
                value is None
                for value in (
                        self.title,
                        self.description,
                        self.priority,
                        self.deadline,
                        self.assignee,
                        self.submission_target,
                        self.completion_condition,
                        self.status,
                )
        ):
            raise ValueError("변경할 항목을 하나 이상 입력해 주세요.")
        return self


class TaskMutationResponse(BaseModel):
    analysis: TaskAnalysisResult
    task: TaskItem | None = None