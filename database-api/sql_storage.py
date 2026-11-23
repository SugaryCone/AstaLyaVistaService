"""SQLAlchemy storage for the PostgreSQL schema in database/init/."""

from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date

from sqlalchemy import (
    BigInteger, Column, Date, FetchedValue, ForeignKey, Identity, Integer,
    Table, Text, create_engine, delete, insert, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from models import Employee, Project, TaskCreate, TaskRecord, TaskStatus, TaskType


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str]
    code: Mapped[str]


class EmployeeRow(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str]
    surname: Mapped[str]


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    number: Mapped[str] = mapped_column(Text, server_default=FetchedValue(), server_onupdate=FetchedValue())
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    description: Mapped[str]
    state_id: Mapped[int] = mapped_column(Integer)
    type_id: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column("deadline_at", Date)
    spent_minutes: Mapped[int] = mapped_column(Integer)


task_links = Table(
    "task_links", Base.metadata,
    Column("task_id", BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("linked_task_id", BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)

# IDs of the read-only dictionaries seeded by 01.sql.
TASK_TYPES = {TaskType.TASK: 1, TaskType.BUG: 2, TaskType.REQUIREMENT: 3}
TASK_STATUSES = {
    TaskStatus.REGISTERED: 1, TaskStatus.IN_PROGRESS: 2, TaskStatus.IN_REVIEW: 3,
    TaskStatus.REWORK: 4, TaskStatus.CLOSED: 5,
}
TYPES_BY_ID = {value: key for key, value in TASK_TYPES.items()}
STATUSES_BY_ID = {value: key for key, value in TASK_STATUSES.items()}


def _database_id(value: str) -> int | None:
    # API IDs remain strings; PostgreSQL uses positive BIGINT identifiers.
    if not value.isascii() or not value.isdecimal() or len(value) > 19:
        return None
    parsed = int(value)
    return parsed if 0 < parsed <= 2**63 - 1 and str(parsed) == value else None


class SQLTaskRepository:
    storage_kind = "postgresql"

    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(
            database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3},
        )
        self.sessions = sessionmaker(self.engine)
        # Each request owns a session; concurrent requests never share one.
        self._session: ContextVar[Session] = ContextVar("database_session")

    @property
    def session(self) -> Session:
        return self._session.get()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self.sessions.begin() as session:
            token = self._session.set(session)
            try:
                yield
            finally:
                self._session.reset(token)

    def check_health(self) -> None:
        # Also detects a missing SQL update before serving requests.
        self.session.execute(select(TaskRow).limit(0))
        self.session.execute(select(task_links).limit(0))

    def close(self) -> None:
        self.engine.dispose()

    def list_projects(self) -> list[Project]:
        return [
            Project(id=str(row.id), code=row.code, name=row.name)
            for row in self.session.scalars(select(ProjectRow).order_by(ProjectRow.id))
        ]

    def list_employees(self) -> list[Employee]:
        return [
            Employee(id=str(row.id), name=f"{row.name} {row.surname}")
            for row in self.session.scalars(select(EmployeeRow).order_by(EmployeeRow.id))
        ]

    def _records(self, rows: Sequence[TaskRow]) -> list[TaskRecord]:
        if not rows:
            return []
        links: dict[int, list[str]] = defaultdict(list)
        query = select(task_links).where(task_links.c.task_id.in_([row.id for row in rows]))
        for task_id, linked_id in self.session.execute(query.order_by(task_links.c.linked_task_id)):
            links[task_id].append(str(linked_id))
        return [
            TaskRecord(
                id=str(row.id), number=row.number, project_id=str(row.project_id),
                assignee_id=str(row.employee_id) if row.employee_id is not None else None,
                description=row.description, type=TYPES_BY_ID[row.type_id],
                status=STATUSES_BY_ID[row.state_id], due_date=row.due_date,
                spent_minutes=row.spent_minutes, linked_task_ids=links[row.id],
            )
            for row in rows
        ]

    def list_tasks(self) -> list[TaskRecord]:
        return self._records(self.session.scalars(select(TaskRow).order_by(TaskRow.id)).all())

    def get_task(self, task_id: str, *, for_update: bool = False) -> TaskRecord | None:
        identifier = _database_id(task_id)
        if identifier is None:
            return None
        query = select(TaskRow).where(TaskRow.id == identifier)
        if for_update:
            query = query.with_for_update()
        row = self.session.scalar(query)
        return self._records([row])[0] if row is not None else None

    @staticmethod
    def _set_fields(row: TaskRow, payload: TaskCreate) -> None:
        row.project_id = int(payload.project_id)
        row.employee_id = int(payload.assignee_id) if payload.assignee_id is not None else None
        row.description = payload.description
        row.type_id = TASK_TYPES[payload.type]
        row.state_id = TASK_STATUSES[payload.status]
        row.due_date = payload.due_date
        row.spent_minutes = payload.spent_minutes

    def _save_links(self, task_id: int, links: list[str]) -> None:
        self.session.execute(delete(task_links).where(task_links.c.task_id == task_id))
        if links:
            self.session.execute(insert(task_links), [
                {"task_id": task_id, "linked_task_id": int(linked_id)} for linked_id in links
            ])

    def create_task(self, payload: TaskCreate) -> TaskRecord:
        row = TaskRow()
        self._set_fields(row, payload)
        self.session.add(row)
        self.session.flush()  # INSERT RETURNING fetches the ID and trigger-generated number.
        self._save_links(row.id, payload.linked_task_ids)
        return self._records([row])[0]

    def save_task(self, task: TaskRecord) -> TaskRecord:
        row = self.session.get(TaskRow, int(task.id))
        self._set_fields(row, task)
        self.session.flush()
        self.session.refresh(row)  # A project change can assign a new number in PostgreSQL.
        self._save_links(row.id, task.linked_task_ids)
        return self._records([row])[0]

    def delete_task(self, task_id: str) -> None:
        self.session.execute(delete(TaskRow).where(TaskRow.id == int(task_id)))
