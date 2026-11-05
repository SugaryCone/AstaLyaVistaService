"""Application setup and HTTP endpoints."""

import os
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse

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


def create_app(*, today: Callable[[], date] | None = None) -> FastAPI:
    if today is None:
        timezone = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Moscow"))

        def today() -> date:
            return datetime.now(timezone).date()

    app = FastAPI(
        title="AstaLaVista — мок-API задач",
        version="0.1.0",
        description=(
            "Демонстрационный API с хранилищем в памяти. "
            "Данные сбрасываются при перезапуске процесса. "
            "Проекты и сотрудники — тестовые справочники. "
            "Типы и статусы перечислены в схемах; запросы выполняются без авторизации."
        ),
    )
    service = TaskService(create_demo_repository(today()), today)
    app.state.task_service = service
    router = APIRouter(
        prefix="/api/v1",
        responses={
            404: {"model": ErrorResponse, "description": "Задача не найдена"},
            422: {"model": ErrorResponse, "description": "Неверные данные или ссылки"},
        },
    )

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/health", tags=["Служебное"], summary="Проверка работоспособности")
    def health() -> HealthResponse:
        return HealthResponse()

    @router.get("/projects", tags=["Справочники"], summary="Список тестовых проектов")
    def list_projects() -> list[Project]:
        return service.list_projects()

    @router.get("/employees", tags=["Справочники"], summary="Список тестовых сотрудников")
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
