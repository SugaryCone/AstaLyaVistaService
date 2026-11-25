"""Application setup and HTTP endpoints."""

import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from fixtures import create_demo_repository
from models import (
    Employee,
    ErrorResponse,
    HealthResponse,
    Project,
    StatusUpdate,
    TaskCreate,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from service import ServiceError, TaskService
from db_storage import PostgresTaskRepository
from storage import TaskRepository


def create_app(
    *, today: Callable[[], date] | None = None, database_url: str | None = None,
) -> FastAPI:
    if today is None:
        timezone = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Moscow"))

        def today() -> date:
            return datetime.now(timezone).date()

    database_url = os.getenv("DATABASE_URL") if database_url is None else database_url
    repository: TaskRepository = (
        PostgresTaskRepository(database_url) if database_url else create_demo_repository(today())
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            with repository.transaction():
                repository.check_health()
            yield
        finally:
            repository.close()

    storage_description = (
        "Данные сохраняются в PostgreSQL. " if database_url
        else "Тестовое хранилище в памяти; данные сбрасываются при перезапуске. "
    )
    app = FastAPI(
        title="AstaLaVista — API задач",
        version="0.2.0",
        description=storage_description + (
            "Проекты и сотрудники доступны как справочники. "
            "Типы и статусы перечислены в схемах; запросы выполняются без авторизации."
        ),
        lifespan=lifespan,
    )
    service = TaskService(repository, today)
    app.state.task_service = service
    router = APIRouter(
        prefix="/api/v1",
        responses={
            404: {"model": ErrorResponse, "description": "Задача не найдена"},
            422: {"model": ErrorResponse, "description": "Неверные данные или ссылки"},
            503: {"model": ErrorResponse, "description": "База данных недоступна"},
        },
    )

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(status_code=422, content={
            "detail": "Невозможно сохранить данные: нарушено ограничение БД или удалена связанная запись",
        })

    @app.exception_handler(OperationalError)
    async def database_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "База данных недоступна"})

    @app.get("/health", tags=["Служебное"], summary="Проверка работоспособности")
    def health() -> HealthResponse:
        with repository.transaction():
            repository.check_health()
        return HealthResponse(storage=repository.storage_kind)

    @router.get("/projects", tags=["Справочники"], summary="Список проектов")
    def list_projects() -> list[Project]:
        return service.list_projects()

    @router.get("/employees", tags=["Справочники"], summary="Список сотрудников")
    def list_employees() -> list[Employee]:
        return service.list_employees()

    @router.get("/tasks", tags=["Задачи"], summary="Задачи с фильтрами")
    def list_tasks(
        assignee_id: str | None = None,
        project_id: str | None = None,
        status: TaskStatus | None = None,
        overdue: Annotated[bool | None, Query(description="Просрочена ли открытая задача")] = None,
        open_only: Annotated[bool, Query(description="Показывать только незакрытые задачи")] = False,
    ) -> list[TaskRead]:
        return service.list_tasks(
            assignee_id=assignee_id,
            project_id=project_id,
            status=status,
            overdue=overdue,
            open_only=open_only,
        )

    @router.post(
        "/tasks", tags=["Задачи"], status_code=status.HTTP_201_CREATED, summary="Создать задачу"
    )
    def create_task(payload: TaskCreate) -> TaskRead:
        return service.create_task(payload)

    @router.get("/tasks/{task_id}", tags=["Задачи"], summary="Получить задачу")
    def get_task(task_id: str) -> TaskRead:
        return service.get_task(task_id)

    @router.patch("/tasks/{task_id}", tags=["Задачи"], summary="Изменить переданные поля задачи")
    def update_task(task_id: str, payload: TaskUpdate) -> TaskRead:
        return service.update_task(task_id, payload)

    @router.patch("/tasks/{task_id}/status", tags=["Задачи"], summary="Изменить статус задачи")
    def change_status(task_id: str, payload: StatusUpdate) -> TaskRead:
        return service.change_status(task_id, payload.status)

    @router.delete(
        "/tasks/{task_id}",
        tags=["Задачи"],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Удалить задачу и ссылки на неё",
    )
    def delete_task(task_id: str) -> Response:
        service.delete_task(task_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    app.include_router(router)
    return app


app = create_app()
