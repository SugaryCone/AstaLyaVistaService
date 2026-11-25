import os
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import TaskRecord, Project, Employee, TaskType, TaskStatus
from db_models import Base, TaskDB, ProjectDB, EmployeeDB, StateDB, TaskTypeDB

# Setup DB connection using the environment variable from compose.yaml
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class PostgresTaskRepository:
    def transaction(self):
        return SessionLocal()

    def list_projects(self) -> list[Project]:
        with SessionLocal() as db:
            projects = db.query(ProjectDB).all()
            return [Project(id=str(p.id), code=p.code, name=p.name) for p in projects]

    def list_employees(self) -> list[Employee]:
        with SessionLocal() as db:
            employees = db.query(EmployeeDB).all()
            return [Employee(id=str(e.id), name=e.name) for e in employees]

    def _map_to_task_record(self, task_db: TaskDB, db: Session) -> TaskRecord:
        # Map DB IDs to API Enum strings
        state = db.query(StateDB).filter(StateDB.id == task_db.state_id).first()
        task_type = db.query(TaskTypeDB).filter(TaskTypeDB.id == task_db.type_id).first()
        
        # Fallbacks in case of weird DB data
        status_str = state.name if state else "registered"
        type_str = task_type.name if task_type else "task"

        return TaskRecord(
            id=str(task_db.id),
            number=task_db.number,
            project_id=str(task_db.project_id),
            assignee_id=str(task_db.employee_id) if task_db.employee_id else None,
            description=task_db.description,
            status=TaskStatus(status_str),
            type=TaskType(type_str),
            linked_task_ids=[str(t.id) for t in task_db.links],
            due_date=task_db.deadline_at,
            spent_minutes=task_db.spent_minutes
        )

    def list_tasks(self) -> list[TaskRecord]:
        with SessionLocal() as db:
            tasks = db.query(TaskDB).all()
            return [self._map_to_task_record(t, db) for t in tasks]

    def get_task(self, task_id: str) -> TaskRecord | None:
        with SessionLocal() as db:
            task = db.query(TaskDB).filter(TaskDB.id == int(task_id)).first()
            return self._map_to_task_record(task, db) if task else None

    def save_task(self, task: TaskRecord) -> None:
        with SessionLocal() as db:
            # Check if it's an update or a create
            existing = db.query(TaskDB).filter(TaskDB.id == int(task.id)).first()
            
            # We need to map the string status/type back to IDs
            state = db.query(StateDB).filter(StateDB.name == task.status.value).first()
            task_type = db.query(TaskTypeDB).filter(TaskTypeDB.name == task.type.value).first()
            
            state_id = state.id if state else 1 # Fallback to 1 (registered)
            type_id = task_type.id if task_type else 1 # Fallback to 1 (task)

            if existing:
                existing.project_id = int(task.project_id)
                existing.employee_id = int(task.assignee_id) if task.assignee_id else None
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
                new_task = TaskDB(
                    id=int(task.id) if task.id else None,
                    project_id=int(task.project_id),
                    employee_id=int(task.assignee_id) if task.assignee_id else None,
                    description=task.description,
                    state_id=state_id,
                    type_id=type_id,
                    created_at=str(date.today()),
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
            
            db.commit()

    def delete_task(self, task_id: str) -> None:
        with SessionLocal() as db:
            task = db.query(TaskDB).filter(TaskDB.id == int(task_id)).first()
            if task:
                db.delete(task)
                db.commit()

    def next_number(self, project_id: str) -> str:
        # The PostgreSQL trigger handles this! We just return a dummy string.
        return ""