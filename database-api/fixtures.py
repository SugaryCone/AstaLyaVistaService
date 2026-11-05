"""Predictable examples; deadline scenarios are relative to the app's start date."""

from datetime import date, timedelta

from models import Employee, Project, TaskRecord, TaskStatus, TaskType
from storage import MemoryTaskRepository


def create_demo_repository(today: date) -> MemoryTaskRepository:
    projects = [
        Project(id="project-asta", code="ASTA", name="Система ведения задач"),
        Project(id="project-web", code="WEB", name="Клиент приложения"),
    ]
    employees = [
        Employee(id="employee-anna", name="Анна Иванова"),
        Employee(id="employee-ivan", name="Иван Петров"),
        Employee(id="employee-maria", name="Мария Смирнова"),
    ]
    tasks = [
        TaskRecord(
            id="task-1",
            number="ASTA-1",
            type=TaskType.REQUIREMENT,
            project_id="project-asta",
            assignee_id="employee-anna",
            description="Описать контракт API задач",
            status=TaskStatus.REGISTERED,
            due_date=today + timedelta(days=7),
            linked_task_ids=["task-2", "task-3"],
        ),
        TaskRecord(
            id="task-2",
            number="ASTA-2",
            type=TaskType.TASK,
            project_id="project-asta",
            assignee_id="employee-ivan",
            description="Подготовить мок хранилища",
            status=TaskStatus.IN_PROGRESS,
            due_date=today - timedelta(days=1),
            spent_minutes=90,
        ),
        TaskRecord(
            id="task-3",
            number="ASTA-3",
            type=TaskType.BUG,
            project_id="project-asta",
            assignee_id="employee-maria",
            description="Проверить фильтр задач со сроком сегодня",
            status=TaskStatus.IN_REVIEW,
            due_date=today,
            spent_minutes=30,
        ),
        TaskRecord(
            id="task-4",
            number="ASTA-4",
            type=TaskType.TASK,
            project_id="project-asta",
            assignee_id="employee-ivan",
            description="Уточнить обработку неверных связей",
            status=TaskStatus.REWORK,
            due_date=today + timedelta(days=2),
            spent_minutes=45,
        ),
        TaskRecord(
            id="task-5",
            number="WEB-1",
            type=TaskType.BUG,
            project_id="project-web",
            assignee_id="employee-maria",
            description="Исправить отображение статуса",
            status=TaskStatus.CLOSED,
            due_date=today - timedelta(days=3),
            spent_minutes=60,
        ),
        TaskRecord(
            id="task-6",
            number="WEB-2",
            type=TaskType.REQUIREMENT,
            project_id="project-web",
            description="Выбрать интерфейс будущего клиента",
        ),
    ]
    return MemoryTaskRepository(projects, employees, tasks)
