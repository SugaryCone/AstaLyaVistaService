"""Task behavior and validation, independent of HTTP and storage implementation."""

from collections.abc import Callable
from datetime import date
from uuid import uuid4

from models import (
    Employee,
    Project,
    TaskCreate,
    TaskRead,
    TaskRecord,
    TaskStatus,
    TaskUpdate,
)
from storage import TaskRepository


class ServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class TaskService:
    def __init__(self, repository: TaskRepository, today: Callable[[], date]) -> None:
        self.repository = repository
        self.today = today

    def list_projects(self) -> list[Project]:
        with self.repository.transaction():
            return self.repository.list_projects()

    def list_employees(self) -> list[Employee]:
        with self.repository.transaction():
            return self.repository.list_employees()

    def _read(self, task: TaskRecord, today: date) -> TaskRead:
        is_open = task.status != TaskStatus.CLOSED
        return TaskRead(
            **task.model_dump(),
            is_open=is_open,
            is_overdue=is_open and task.due_date is not None and today > task.due_date,
        )

    def _get(self, task_id: str) -> TaskRecord:
        task = self.repository.get_task(task_id)
        if task is None:
            raise ServiceError(404, f"Задача {task_id} не найдена")
        return task

    def _validate_references(self, task: TaskCreate, task_id: str | None = None) -> None:
        if task.project_id not in {project.id for project in self.repository.list_projects()}:
            raise ServiceError(422, f"Проект {task.project_id} не найден")
        if task.assignee_id is not None and task.assignee_id not in {
            employee.id for employee in self.repository.list_employees()
        }:
            raise ServiceError(422, f"Сотрудник {task.assignee_id} не найден")
        for linked_id in task.linked_task_ids:
            if linked_id == task_id:
                raise ServiceError(422, "Задача не может ссылаться на себя")
            if self.repository.get_task(linked_id) is None:
                raise ServiceError(422, f"Связанная задача {linked_id} не найдена")

    def list_tasks(
        self,
        *,
        assignee_id: str | None = None,
        project_id: str | None = None,
        status: TaskStatus | None = None,
        overdue: bool | None = None,
        open_only: bool = False,
    ) -> list[TaskRead]:
        with self.repository.transaction():
            today = self.today()
            result = []
            for task in self.repository.list_tasks():
                if assignee_id is not None and task.assignee_id != assignee_id:
                    continue
                if project_id is not None and task.project_id != project_id:
                    continue
                if status is not None and task.status != status:
                    continue
                item = self._read(task, today)
                if open_only and not item.is_open:
                    continue
                if overdue is not None and item.is_overdue != overdue:
                    continue
                result.append(item)
            return result

    def get_task(self, task_id: str) -> TaskRead:
        with self.repository.transaction():
            return self._read(self._get(task_id), self.today())

    def create_task(self, payload: TaskCreate) -> TaskRead:
        with self.repository.transaction():
            self._validate_references(payload)
            task = TaskRecord(
                **payload.model_dump(),
                id=str(uuid4()),
                number=self.repository.next_number(payload.project_id),
            )
            self.repository.save_task(task)
            return self._read(task, self.today())

    def update_task(self, task_id: str, payload: TaskUpdate) -> TaskRead:
        with self.repository.transaction():
            original = self._get(task_id)
            values = original.model_dump()
            values.update(payload.model_dump(exclude_unset=True))
            task = TaskRecord.model_validate(values)
            self._validate_references(task, task_id)
            if task.project_id != original.project_id:
                task.number = self.repository.next_number(task.project_id)
            self.repository.save_task(task)
            return self._read(task, self.today())

    def change_status(self, task_id: str, status: TaskStatus) -> TaskRead:
        return self.update_task(task_id, TaskUpdate(status=status))

    def delete_task(self, task_id: str) -> None:
        with self.repository.transaction():
            self._get(task_id)
            self.repository.delete_task(task_id)
            for task in self.repository.list_tasks():
                if task_id in task.linked_task_ids:
                    task.linked_task_ids.remove(task_id)
                    self.repository.save_task(task)
