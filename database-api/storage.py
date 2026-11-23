"""Storage interface and its process-local implementation."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from threading import RLock
from typing import Protocol
from uuid import uuid4

from models import Employee, Project, TaskCreate, TaskRecord


class TaskRepository(Protocol):
    storage_kind: str

    def transaction(self) -> AbstractContextManager[None]: ...

    def check_health(self) -> None: ...

    def close(self) -> None: ...

    def list_projects(self) -> list[Project]: ...

    def list_employees(self) -> list[Employee]: ...

    def list_tasks(self) -> list[TaskRecord]: ...

    def get_task(self, task_id: str, *, for_update: bool = False) -> TaskRecord | None: ...

    def create_task(self, payload: TaskCreate) -> TaskRecord: ...

    def save_task(self, task: TaskRecord) -> TaskRecord: ...

    def delete_task(self, task_id: str) -> None: ...


class MemoryTaskRepository:
    storage_kind = "memory"

    def __init__(
        self, projects: list[Project], employees: list[Employee], tasks: list[TaskRecord]
    ) -> None:
        self._lock = RLock()
        self._projects = {project.id: project.model_copy(deep=True) for project in projects}
        self._employees = [employee.model_copy(deep=True) for employee in employees]
        self._tasks = {task.id: task.model_copy(deep=True) for task in tasks}
        self._counters = {project.id: 0 for project in projects}
        for task in tasks:
            sequence = int(task.number.rsplit("-", 1)[1])
            self._counters[task.project_id] = max(self._counters[task.project_id], sequence)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def check_health(self) -> None:
        pass

    def close(self) -> None:
        pass

    def list_projects(self) -> list[Project]:
        return [project.model_copy(deep=True) for project in self._projects.values()]

    def list_employees(self) -> list[Employee]:
        return [employee.model_copy(deep=True) for employee in self._employees]

    def list_tasks(self) -> list[TaskRecord]:
        return [task.model_copy(deep=True) for task in self._tasks.values()]

    def get_task(self, task_id: str, *, for_update: bool = False) -> TaskRecord | None:
        task = self._tasks.get(task_id)
        return task.model_copy(deep=True) if task is not None else None

    def create_task(self, payload: TaskCreate) -> TaskRecord:
        task = TaskRecord(
            **payload.model_dump(), id=str(uuid4()), number=self._next_number(payload.project_id)
        )
        return self.save_task(task)

    def save_task(self, task: TaskRecord) -> TaskRecord:
        original = self._tasks.get(task.id)
        if original is not None and original.project_id != task.project_id:
            task = task.model_copy(update={"number": self._next_number(task.project_id)})
        self._tasks[task.id] = task.model_copy(deep=True)
        return task.model_copy(deep=True)

    def delete_task(self, task_id: str) -> None:
        del self._tasks[task_id]

    def _next_number(self, project_id: str) -> str:
        self._counters[project_id] += 1
        return f"{self._projects[project_id].code}-{self._counters[project_id]}"
