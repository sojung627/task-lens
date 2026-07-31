from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.core.config import get_settings

Priority = Literal["urgent", "high", "normal", "low", "unspecified"]


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
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    order: int = Field(ge=1)
    priority: Priority
    deadline: str | None = None
    assignee: str | None = None
    submission_target: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    completion_condition: str | None = None


class DifficultTerm(BaseModel):
    term: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class TaskAnalysisResult(BaseModel):
    core_goal: str = Field(min_length=1)
    tasks: list[TaskItem] = Field(min_length=1)
    confirmation_items: list[str] = Field(default_factory=list)
    difficult_terms: list[DifficultTerm] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)

    @field_validator("tasks")
    @classmethod
    def validate_unique_order(cls, tasks: list[TaskItem]) -> list[TaskItem]:
        orders = [task.order for task in tasks]
        if len(orders) != len(set(orders)):
            raise ValueError("작업 순서(order)는 중복될 수 없습니다.")
        return sorted(tasks, key=lambda task: task.order)


class AnalyzeTaskResponse(BaseModel):
    request_id: str
    model: str
    analysis: TaskAnalysisResult
