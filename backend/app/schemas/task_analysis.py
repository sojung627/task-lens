from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.core.config import get_settings

Priority = Literal["urgent", "high", "normal", "low", "unspecified"]
TaskStatus = Literal["todo", "in_progress", "done"]


class AnalyzeTaskRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("업무 지시를 입력해 주세요.")

        max_length = get_settings().ai_input_max_length
        if len(normalized) > max_length:
            raise ValueError(f"업무 지시는 {max_length}자 이하여야 합니다.")
        return normalized


class TaskItem(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=4_000)
    order: int = Field(ge=1)
    priority: Priority = "unspecified"
    deadline: str | None = Field(default=None, max_length=500)
    assignee: str | None = Field(default=None, max_length=200)
    submission_target: str | None = Field(default=None, max_length=500)
    dependencies: list[str] = Field(default_factory=list, max_length=50)
    completion_condition: str | None = Field(default=None, max_length=2_000)
    status: TaskStatus = "todo"
    completed: bool = False

    @model_validator(mode="after")
    def synchronize_status_and_completed(self) -> "TaskItem":
        if self.completed or self.status == "done":
            self.completed = True
            self.status = "done"
        elif self.status == "in_progress":
            self.completed = False
        else:
            self.status = "todo"
            self.completed = False
        return self


class DifficultTerm(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1, max_length=2_000)


class TaskAnalysisResult(BaseModel):
    summary: str | None = Field(default=None, max_length=4_000)
    core_goal: str = Field(min_length=1, max_length=2_000)
    key_points: list[str] = Field(default_factory=list, max_length=50)
    decisions: list[str] = Field(default_factory=list, max_length=50)
    tasks: list[TaskItem] = Field(min_length=1, max_length=100)
    confirmation_items: list[str] = Field(default_factory=list, max_length=50)
    difficult_terms: list[DifficultTerm] = Field(default_factory=list, max_length=50)
    ambiguities: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("tasks")
    @classmethod
    def validate_unique_task_fields(cls, tasks: list[TaskItem]) -> list[TaskItem]:
        orders = [task.order for task in tasks]
        if len(orders) != len(set(orders)):
            raise ValueError("작업 순서(order)는 중복될 수 없습니다.")

        identifiers = [task.id for task in tasks]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("작업 id는 중복될 수 없습니다.")

        known_identifiers = set(identifiers)
        for task in tasks:
            task.dependencies = [
                dependency
                for dependency in dict.fromkeys(task.dependencies)
                if dependency in known_identifiers and dependency != task.id
            ]
        return sorted(tasks, key=lambda task: task.order)


class AnalyzeTaskResponse(BaseModel):
    request_id: str
    model: str
    analysis: TaskAnalysisResult


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=4_000)
    priority: Priority | None = None
    deadline: str | None = Field(default=None, max_length=500)
    assignee: str | None = Field(default=None, max_length=200)
    submission_target: str | None = Field(default=None, max_length=500)
    dependencies: list[str] | None = Field(default=None, max_length=50)
    completion_condition: str | None = Field(default=None, max_length=2_000)
    status: TaskStatus | None = None
    order: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_changes(self) -> "TaskUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("수정할 작업 정보를 입력해 주세요.")

        non_nullable_fields = {"title", "priority", "dependencies", "status", "order"}
        for field_name in non_nullable_fields & self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 값은 null일 수 없습니다.")

        if "title" in self.model_fields_set and self.title is not None:
            self.title = self.title.strip()
            if not self.title:
                raise ValueError("작업 제목을 입력해 주세요.")
        return self