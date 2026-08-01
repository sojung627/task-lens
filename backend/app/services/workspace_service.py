from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.chat import (
    AttachmentSummary,
    ConversationSummary,
    FileSummary,
    MessageSummary,
    ReminderSummary,
    WorkspaceResponse,
)


def display_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%m.%d %H:%M")
    except (TypeError, ValueError):
        return value


def size_label(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository

    def get_workspace(self, conversation_id: str | None = None) -> WorkspaceResponse:
        conversation_rows = self.repository.list_conversations("active")
        trashed_rows = self.repository.list_conversations("trashed")
        valid_active_ids = {row["id"] for row in conversation_rows}
        active_id = conversation_id if conversation_id in valid_active_ids else None
        if active_id is None and conversation_rows:
            active_id = conversation_rows[0]["id"]

        active_row = self.repository.get_conversation(active_id) if active_id else None
        messages = self.get_messages(active_id) if active_id else []
        source_files = (
            [self._file_summary(row) for row in self.repository.list_conversation_files(active_id)]
            if active_id
            else []
        )
        reminders = (
            [self.reminder_summary(row) for row in self.repository.list_reminders(active_id)]
            if active_id
            else []
        )

        return WorkspaceResponse(
            conversations=[self._conversation_summary(row) for row in conversation_rows],
            trashedConversations=[self._conversation_summary(row) for row in trashed_rows],
            recentFiles=[self._file_summary(row) for row in self.repository.list_files(limit=8)],
            sourceFiles=source_files,
            activeConversationId=active_id,
            messages=messages,
            analysis=self.repository.get_analysis(active_id) if active_id else None,
            notes=(active_row["notes"] or "") if active_row else "",
            reminders=reminders,
        )

    def get_messages(self, conversation_id: str) -> list[MessageSummary]:
        return [self._message_summary(row) for row in self.repository.list_messages(conversation_id)]

    def get_message(self, message_id: str) -> MessageSummary:
        row = self.repository.get_message(message_id)
        if row is None:
            raise KeyError(message_id)
        return self._message_summary(row)

    def get_due_reminders(self) -> list[ReminderSummary]:
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            self.reminder_summary(row)
            for row in self.repository.list_due_reminders(now_iso)
        ]

    def _message_summary(self, row: Mapping[str, Any]) -> MessageSummary:
        attachments = [
            AttachmentSummary(
                id=file_row["id"],
                name=file_row["original_name"],
                extension=file_row["extension"],
                downloadUrl=f"/api/files/{file_row['id']}/download",
                generatedBy=file_row["generated_by"],
            )
            for file_row in self.repository.list_message_files(row["id"])
        ]
        return MessageSummary(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            createdAt=display_time(row["created_at"]),
            attachments=attachments,
        )

    @staticmethod
    def _conversation_summary(row: Mapping[str, Any]) -> ConversationSummary:
        return ConversationSummary(
            id=row["id"],
            title=row["title"],
            preview=row["preview"],
            updatedAt=display_time(row["updated_at"]),
            status=row["status"],
        )

    @staticmethod
    def _file_summary(row: Mapping[str, Any]) -> FileSummary:
        return FileSummary(
            id=row["id"],
            name=row["original_name"],
            extension=row["extension"],
            uploadedAt=display_time(row["created_at"]),
            sizeLabel=size_label(row["size_bytes"]),
            downloadUrl=f"/api/files/{row['id']}/download",
            generatedBy=row["generated_by"],
        )

    @staticmethod
    def reminder_summary(row: Mapping[str, Any]) -> ReminderSummary:
        return ReminderSummary(
            id=row["id"],
            conversationId=row["conversation_id"],
            taskId=row["task_id"],
            message=row["message"],
            remindAt=row["remind_at"],
            status=row["status"],
        )