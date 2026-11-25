from contextlib import contextmanager
from contextvars import ContextVar
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import TaskCreate, TaskRecord, Project, Employee, TaskType, TaskStatus
from db_models import TaskDB, ProjectDB, EmployeeDB, task_links

# IDs of the read-only dictionaries seeded by 01.sql.
TASK_TYPES = {TaskType.TASK: 1, TaskType.BUG: 2, TaskType.REQUIREMENT: 3}
TASK_STATUSES = {
    TaskStatus.REGISTERED: 1, TaskStatus.IN_PROGRESS: 2, TaskStatus.IN_REVIEW: 3,
    TaskStatus.REWORK: 4, TaskStatus.CLOSED: 5,
}
TYPES_BY_ID = {value: key for key, value in TASK_TYPES.items()}
STATUSES_BY_ID = {value: key for key, value in TASK_STATUSES.items()}

class PostgresTaskRepository:
    storage_kind = "postgresql"

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._session: ContextVar[Session] = ContextVar("database_session")

    @contextmanager
    def transaction(self):
        if self._session.get(None) is not None:
            yield
            return
        with self.SessionLocal.begin() as db:
            token = self._session.set(db)
            try:
                yield
            finally:
                self._session.reset(token)

    def check_health(self) -> None:
        with self.transaction():
            db = self._session.get()
            db.query(TaskDB).limit(0).all()
            db.query(task_links).limit(0).all()

    def close(self) -> None:
        self.engine.dispose()

    def list_projects(self) -> list[Project]:
        with self.transaction():
            db = self._session.get()
            projects = db.query(ProjectDB).order_by(ProjectDB.id).all()
            return [Project(id=str(p.id), code=p.code, name=p.name) for p in projects]

    def list_employees(self) -> list[Employee]:
        with self.transaction():
            db = self._session.get()
            employees = db.query(EmployeeDB).order_by(EmployeeDB.id).all()
            return [Employee(id=str(e.id), name=f"{e.name} {e.surname}") for e in employees]

    def _map_to_task_record(self, task_db: TaskDB, db: Session) -> TaskRecord:
        # Map DB IDs to API Enum strings
        state = STATUSES_BY_ID[task_db.state_id]
        task_type = TYPES_BY_ID[task_db.type_id]
        
        status_str = state.value
        type_str = task_type.value

        return TaskRecord(
            id=str(task_db.id),
            number=task_db.number,
            project_id=str(task_db.project_id),
            assignee_id=str(task_db.employee_id) if task_db.employee_id is not None else None,
            description=task_db.description,
            status=TaskStatus(status_str),
            type=TaskType(type_str),
            linked_task_ids=[str(t.id) for t in sorted(task_db.links, key=lambda t: t.id)],
            due_date=task_db.deadline_at,
            spent_minutes=task_db.spent_minutes
        )

    def list_tasks(self) -> list[TaskRecord]:
        with self.transaction():
            db = self._session.get()
            tasks = db.query(TaskDB).order_by(TaskDB.id).all()
            return [self._map_to_task_record(t, db) for t in tasks]

    def get_task(self, task_id: str, *, for_update: bool = False) -> TaskRecord | None:
        if not task_id.isascii() or not task_id.isdecimal() or len(task_id) > 19:
            return None
        identifier = int(task_id)
        if not 0 < identifier <= 2**63 - 1 or str(identifier) != task_id:
            return None
        with self.transaction():
            db = self._session.get()
            query = db.query(TaskDB).filter(TaskDB.id == identifier)
            if for_update:
                query = query.with_for_update()
            task = query.first()
            return self._map_to_task_record(task, db) if task else None

    def create_task(self, payload: TaskCreate) -> TaskRecord:
        return self._save_task(payload)

    def save_task(self, task: TaskRecord) -> TaskRecord:
        return self._save_task(task, task.id)

    def _save_task(self, task: TaskCreate, task_id: str | None = None) -> TaskRecord:
        with self.transaction():
            db = self._session.get()
            # Check if it's an update or a create
            existing = db.query(TaskDB).filter(TaskDB.id == int(task_id)).one() if task_id is not None else None
            
            # We need to map the string status/type back to IDs
            state_id = TASK_STATUSES[task.status]
            type_id = TASK_TYPES[task.type]

            if existing:
                existing.project_id = int(task.project_id)
                existing.employee_id = int(task.assignee_id) if task.assignee_id is not None else None
                existing.description = task.description
                existing.state_id = state_id
                existing.type_id = type_id
                existing.deadline_at = task.due_date
                existing.spent_minutes = task.spent_minutes
                
                # Handle links (delete old, add new)
                existing.links = []
                for link_id in task.linked_task_ids:
                    linked_task = db.query(TaskDB).filter(TaskDB.id == int(link_id)).first()
                    if linked_task:
                        existing.links.append(linked_task)
                    else:
                        db.execute(task_links.insert().values(task_id=existing.id, linked_task_id=int(link_id)))
            else:
                new_task = TaskDB(
                    project_id=int(task.project_id),
                    employee_id=int(task.assignee_id) if task.assignee_id is not None else None,
                    description=task.description,
                    state_id=state_id,
                    type_id=type_id,
                    deadline_at=task.due_date,
                    spent_minutes=task.spent_minutes
                )
                db.add(new_task)
                # We flush here so the DB trigger assigns the number and ID
                db.flush() 
                
                for link_id in task.linked_task_ids:
                    linked_task = db.query(TaskDB).filter(TaskDB.id == int(link_id)).first()
                    if linked_task:
                        new_task.links.append(linked_task)
                    else:
                        db.execute(task_links.insert().values(task_id=new_task.id, linked_task_id=int(link_id)))
            
            saved_task = existing or new_task
            db.flush()
            db.refresh(saved_task)
            return self._map_to_task_record(saved_task, db)

    def delete_task(self, task_id: str) -> None:
        with self.transaction():
            db = self._session.get()
            task = db.query(TaskDB).filter(TaskDB.id == int(task_id)).first()
            if task:
                db.delete(task)
                db.flush()
                db.expire_all()