import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from backend.app.schemas.task_analysis import TaskAnalysisResult

metadata = MetaData()

conversations = Table(
    "conversations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("title", String(200), nullable=False),
    Column("preview", String(500), nullable=True),
    Column("status", String(20), nullable=False, default="active", index=True),
    Column("notes", Text, nullable=False, default=""),
    Column("analysis_json", Text, nullable=True),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False, index=True),
)

messages = Table(
    "messages",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "conversation_id",
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("role", String(20), nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", String(40), nullable=False, index=True),
)

files = Table(
    "files",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "conversation_id",
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "message_id",
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("original_name", String(255), nullable=False),
    Column("stored_name", String(255), nullable=False, unique=True),
    Column("extension", String(30), nullable=False),
    Column("mime_type", String(150), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("generated_by", String(20), nullable=False),
    Column("created_at", String(40), nullable=False, index=True),
)

reminders = Table(
    "reminders",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "conversation_id",
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("task_id", String(80), nullable=True),
    Column("message", String(500), nullable=False),
    Column("remind_at", String(40), nullable=False, index=True),
    Column("status", String(20), nullable=False, default="pending", index=True),
    Column("created_at", String(40), nullable=False),
)


class WorkspaceRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create_tables(self) -> None:
        metadata.create_all(self.engine)

    # -- conversations --------------------------------------------------

    def conversation_exists(self, conversation_id: str) -> bool:
        statement = select(conversations.c.id).where(conversations.c.id == conversation_id)
        with self.engine.connect() as connection:
            return connection.execute(statement).scalar_one_or_none() is not None

    def get_conversation(self, conversation_id: str) -> Mapping[str, Any] | None:
        statement = select(conversations).where(conversations.c.id == conversation_id)
        with self.engine.connect() as connection:
            return connection.execute(statement).mappings().one_or_none()

    def list_conversations(self, status: str) -> list[Mapping[str, Any]]:
        statement = (
            select(conversations)
            .where(conversations.c.status == status)
            .order_by(conversations.c.updated_at.desc())
        )
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(conversations)
                .where(conversations.c.id == conversation_id)
                .values(title=title)
            )
            return result.rowcount > 0

    def set_conversation_status(self, conversation_id: str, status: str) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(conversations)
                .where(conversations.c.id == conversation_id)
                .values(status=status)
            )
            return result.rowcount > 0

    def update_notes(self, conversation_id: str, content: str) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(conversations)
                .where(conversations.c.id == conversation_id)
                .values(notes=content)
            )
            return result.rowcount > 0

    def delete_conversation(self, conversation_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(conversations).where(conversations.c.id == conversation_id))

    # -- chat exchange (atomic write) ------------------------------------

    def persist_chat_exchange(
            self,
            conversation_id: str,
            is_new_conversation: bool,
            title: str,
            initial_preview: str,
            user_message: tuple[str, str, str],
            user_files: list[tuple[str, str, str, str, str, str, str, int, str, str]],
            assistant_message: tuple[str, str, str],
            assistant_files: list[tuple[str, str, str, str, str, str, str, int, str, str]],
            analysis: TaskAnalysisResult | None,
    ) -> None:
        _, _, assistant_timestamp = assistant_message
        analysis_json = analysis.model_dump_json() if analysis is not None else None

        with self.engine.begin() as connection:
            if is_new_conversation:
                connection.execute(
                    insert(conversations).values(
                        id=conversation_id,
                        title=title,
                        preview=initial_preview,
                        status="active",
                        notes="",
                        analysis_json=analysis_json,
                        created_at=assistant_timestamp,
                        updated_at=assistant_timestamp,
                    )
                )
            else:
                values: dict[str, Any] = {
                    "preview": initial_preview,
                    "updated_at": assistant_timestamp,
                }
                if analysis is not None:
                    values["analysis_json"] = analysis_json
                connection.execute(
                    update(conversations)
                    .where(conversations.c.id == conversation_id)
                    .values(**values)
                )

            user_message_id, user_content, user_timestamp = user_message
            connection.execute(
                insert(messages).values(
                    id=user_message_id,
                    conversation_id=conversation_id,
                    role="user",
                    content=user_content,
                    created_at=user_timestamp,
                )
            )
            for file_values in user_files:
                connection.execute(insert(files).values(**self._file_values(conversation_id, file_values)))

            assistant_message_id, assistant_content, _ = assistant_message
            connection.execute(
                insert(messages).values(
                    id=assistant_message_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_content,
                    created_at=assistant_timestamp,
                )
            )
            for file_values in assistant_files:
                connection.execute(insert(files).values(**self._file_values(conversation_id, file_values)))

    @staticmethod
    def _file_values(
            conversation_id: str,
            values: tuple[str, str, str, str, str, str, str, int, str, str],
    ) -> dict[str, Any]:
        (
            file_id,
            _conversation_id,
            message_id,
            original_name,
            stored_name,
            extension,
            mime_type,
            size_bytes,
            generated_by,
            created_at,
        ) = values
        return {
            "id": file_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "original_name": original_name,
            "stored_name": stored_name,
            "extension": extension,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "generated_by": generated_by,
            "created_at": created_at,
        }

    # -- messages / files -------------------------------------------------

    def list_messages(self, conversation_id: str) -> list[Mapping[str, Any]]:
        statement = (
            select(messages)
            .where(messages.c.conversation_id == conversation_id)
            .order_by(messages.c.created_at.asc())
        )
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    def get_message(self, message_id: str) -> Mapping[str, Any] | None:
        statement = select(messages).where(messages.c.id == message_id)
        with self.engine.connect() as connection:
            return connection.execute(statement).mappings().one_or_none()

    def list_files(self, limit: int = 8) -> list[Mapping[str, Any]]:
        statement = select(files).order_by(files.c.created_at.desc()).limit(limit)
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    def list_conversation_files(self, conversation_id: str) -> list[Mapping[str, Any]]:
        statement = (
            select(files)
            .where(files.c.conversation_id == conversation_id)
            .order_by(files.c.created_at.desc())
        )
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    def list_message_files(self, message_id: str) -> list[Mapping[str, Any]]:
        statement = (
            select(files)
            .where(files.c.message_id == message_id)
            .order_by(files.c.created_at.asc())
        )
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    def get_file(self, file_id: str) -> Mapping[str, Any] | None:
        statement = select(files).where(files.c.id == file_id)
        with self.engine.connect() as connection:
            return connection.execute(statement).mappings().one_or_none()

    # -- analysis (stored as JSON on the conversation row) -----------------

    def get_analysis(self, conversation_id: str) -> TaskAnalysisResult | None:
        statement = select(conversations.c.analysis_json).where(conversations.c.id == conversation_id)
        with self.engine.connect() as connection:
            raw = connection.execute(statement).scalar_one_or_none()
        if not raw:
            return None
        return TaskAnalysisResult.model_validate(json.loads(raw))

    def save_analysis(self, conversation_id: str, analysis: TaskAnalysisResult | None) -> None:
        analysis_json = analysis.model_dump_json() if analysis is not None else None
        with self.engine.begin() as connection:
            connection.execute(
                update(conversations)
                .where(conversations.c.id == conversation_id)
                .values(analysis_json=analysis_json)
            )

    # -- reminders ----------------------------------------------------------

    def add_reminder(
            self,
            reminder_id: str,
            conversation_id: str,
            task_id: str | None,
            message: str,
            remind_at: str,
            status: str,
            created_at: str,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(reminders).values(
                    id=reminder_id,
                    conversation_id=conversation_id,
                    task_id=task_id,
                    message=message,
                    remind_at=remind_at,
                    status=status,
                    created_at=created_at,
                )
            )

    def list_reminders(self, conversation_id: str) -> list[Mapping[str, Any]]:
        statement = (
            select(reminders)
            .where(reminders.c.conversation_id == conversation_id)
            .order_by(reminders.c.remind_at.asc())
        )
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    def list_due_reminders(self, now_iso: str) -> list[Mapping[str, Any]]:
        statement = (
            select(reminders)
            .where(reminders.c.status == "pending")
            .where(reminders.c.remind_at <= now_iso)
            .order_by(reminders.c.remind_at.asc())
        )
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    def update_reminder_status(self, reminder_id: str, status: str) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(reminders)
                .where(reminders.c.id == reminder_id)
                .values(status=status)
            )
            return result.rowcount > 0

    def get_reminder(self, reminder_id: str) -> Mapping[str, Any] | None:
        statement = select(reminders).where(reminders.c.id == reminder_id)
        with self.engine.connect() as connection:
            return connection.execute(statement).mappings().one_or_none()