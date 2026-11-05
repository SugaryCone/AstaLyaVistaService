"""HTTP models and storage records; no database schema is defined here."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema


class TaskType(StrEnum):
    TASK = "task"
    BUG = "bug"
    REQUIREMENT = "requirement"


class TaskStatus(StrEnum):
    REGISTERED = "registered"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    REWORK = "rework"
    CLOSED = "closed"


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Project(BaseModel):
    id: str
    code: str
    name: str


class Employee(BaseModel):
    id: str
    name: str


class TaskCreate(InputModel):
    type: TaskType = Field(description="task — задача; bug — ошибка; requirement — требование")
    project_id: str = Field(min_length=1, examples=["project-asta"])
    assignee_id: str | None = Field(default=None, min_length=1, examples=["employee-anna"])
    description: str = Field(min_length=1, examples=["Подготовить описание API"])
    status: TaskStatus = TaskStatus.REGISTERED
    linked_task_ids: list[str] = Field(default_factory=list, description="ID связанных задач")
    due_date: date | None = Field(default=None, description="Выполнить до, включительно")
    spent_minutes: int = Field(default=0, ge=0, strict=True)

    @field_validator("linked_task_ids")
    @classmethod
    def unique_links(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Список связей содержит повторяющиеся ID")
        return value


def _patch_schema(schema: dict[str, Any]) -> None:
    # Omitted fields use None internally, but only these two accept explicit null.
    for name, field_schema in schema.get("properties", {}).items():
        if name not in {"assignee_id", "due_date"}:
            field_schema.pop("default", None)


class TaskUpdate(InputModel):
    model_config = ConfigDict(json_schema_extra=_patch_schema)

    type: TaskType | SkipJsonSchema[None] = None
    project_id: str | SkipJsonSchema[None] = Field(default=None, min_length=1)
    assignee_id: str | None = Field(default=None, min_length=1)
    description: str | SkipJsonSchema[None] = Field(default=None, min_length=1)
    status: TaskStatus | SkipJsonSchema[None] = None
    linked_task_ids: list[str] | SkipJsonSchema[None] = None
    due_date: date | None = None
    spent_minutes: Annotated[int, Field(ge=0, strict=True)] | SkipJsonSchema[None] = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_required_fields(cls, value: Any) -> Any:
        if isinstance(value, dict):
            nullable = {"assignee_id", "due_date"}
            for name, item in value.items():
                if name in cls.model_fields and name not in nullable and item is None:
                    raise ValueError(f"Поле {name} не может быть null")
        return value

    @field_validator("linked_task_ids")
    @classmethod
    def unique_links(cls, value: list[str] | None) -> list[str] | None:
        return TaskCreate.unique_links(value) if value is not None else value


class StatusUpdate(InputModel):
    status: TaskStatus


class TaskRecord(TaskCreate):
    """Validated task stored by a repository, without time-dependent flags."""

    id: str
    number: str


class TaskRead(TaskRecord):
    is_open: bool
    is_overdue: bool


class ErrorResponse(BaseModel):
    detail: str | list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str = "ok"
    storage: str = "memory"
