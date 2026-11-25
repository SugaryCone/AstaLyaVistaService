from sqlalchemy import Column, BigInteger, String, Text, Date, Integer, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Many-to-many association table for linked tasks
task_links = Table(
    "task_links",
    Base.metadata,
    Column("task_id", BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("linked_task_id", BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)

class ProjectDB(Base):
    __tablename__ = "projects"
    id = Column(BigInteger, primary_key=True)
    code = Column(String(32), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    last_task_number = Column(BigInteger, nullable=False, default=0)

class EmployeeDB(Base):
    __tablename__ = "employees"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    surname = Column(String(255))

class StateDB(Base):
    __tablename__ = "states"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)

class TaskTypeDB(Base):
    __tablename__ = "task_types"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)

class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(BigInteger, primary_key=True)
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("employees.id"), nullable=True)
    description = Column(Text, nullable=False)
    state_id = Column(BigInteger, ForeignKey("states.id"), nullable=False)
    type_id = Column(BigInteger, ForeignKey("task_types.id"), nullable=False)
    created_at = Column(Text, nullable=False) 
    deadline_at = Column(Date, nullable=True)
    spent_minutes = Column(Integer, nullable=False, default=0)
    number = Column(String, nullable=False, unique=True)

    # Relationship to handle the linked tasks
    links = relationship(
        "TaskDB",
        secondary=task_links,
        primaryjoin=id == task_links.c.task_id,
        secondaryjoin=id == task_links.c.linked_task_id,
        lazy="selectin"
    )