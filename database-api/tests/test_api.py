from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from main import create_app
from models import TaskCreate, TaskStatus, TaskType

TASKS = "/api/v1/tasks"
CREATE_BODY = {
    "type": "task",
    "project_id": "project-asta",
    "assignee_id": "employee-anna",
    "description": "Новая задача",
}


def create_task(client: TestClient, **overrides: object) -> dict:
    response = client.post(TASKS, json={**CREATE_BODY, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_health_docs_and_openapi(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "storage": "memory"}
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "/openapi.json" in docs.text
    schema = client.get("/openapi.json").json()
    assert set(schema["components"]["schemas"]["TaskStatus"]["enum"]) == {
        status.value for status in TaskStatus
    }
    assert set(schema["components"]["schemas"]["TaskType"]["enum"]) == {
        task_type.value for task_type in TaskType
    }
    assert set(schema["paths"][TASKS]) == {"get", "post"}
    assert set(schema["paths"][f"{TASKS}/{{task_id}}"]) == {"get", "patch", "delete"}
    assert "patch" in schema["paths"][f"{TASKS}/{{task_id}}/status"]
    patch_fields = schema["components"]["schemas"]["TaskUpdate"]["properties"]
    assert "default" not in patch_fields["status"]
    assert {item.get("type") for item in patch_fields["due_date"]["anyOf"]} == {"string", "null"}


def test_seed_covers_the_demo_scenarios(client: TestClient, today: date) -> None:
    tasks = client.get(TASKS).json()
    assert len(tasks) == 6
    assert {task["type"] for task in tasks} == {"task", "bug", "requirement"}
    assert {task["status"] for task in tasks} == {status.value for status in TaskStatus}
    assert len(client.get("/api/v1/projects").json()) == 2
    assert len(client.get("/api/v1/employees").json()) == 3
    assert next(task for task in tasks if task["id"] == "task-3")["due_date"] == today.isoformat()
    assert next(task for task in tasks if task["id"] == "task-1")["linked_task_ids"]


def test_create_read_and_partial_update(client: TestClient) -> None:
    created = create_task(client, linked_task_ids=["task-1"], spent_minutes=15)
    assert created["number"] == "ASTA-5"
    assert created["status"] == "registered"
    assert created["id"] != "task-1"
    assert client.get(f"{TASKS}/{created['id']}").json() == created

    response = client.patch(
        f"{TASKS}/{created['id']}",
        json={"description": "Изменённое описание", "assignee_id": None, "spent_minutes": 0},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["description"] == "Изменённое описание"
    assert updated["assignee_id"] is None
    assert updated["spent_minutes"] == 0
    assert updated["number"] == created["number"]
    assert updated["linked_task_ids"] == ["task-1"]
    assert client.get(f"{TASKS}/{created['id']}").json() == updated


def test_status_change_is_visible_to_reads_and_filters(client: TestClient) -> None:
    response = client.patch(f"{TASKS}/task-2/status", json={"status": "closed"})
    assert response.status_code == 200
    assert response.json()["is_open"] is False
    assert response.json()["is_overdue"] is False
    assert client.get(f"{TASKS}/task-2").json()["status"] == "closed"
    assert client.get(TASKS, params={"overdue": "true"}).json() == []
    reopened = client.patch(f"{TASKS}/task-2/status", json={"status": "registered"})
    assert reopened.json()["is_overdue"] is True


@pytest.mark.parametrize(
    ("params", "ids"),
    [
        ({"assignee_id": "employee-ivan"}, {"task-2", "task-4"}),
        ({"project_id": "project-web"}, {"task-5", "task-6"}),
        ({"status": "registered"}, {"task-1", "task-6"}),
        ({"overdue": "true"}, {"task-2"}),
        ({"overdue": "false"}, {"task-1", "task-3", "task-4", "task-5", "task-6"}),
        ({"open_only": "true"}, {"task-1", "task-2", "task-3", "task-4", "task-6"}),
        (
            {
                "project_id": "project-asta",
                "assignee_id": "employee-ivan",
                "status": "in_progress",
                "overdue": "true",
                "open_only": "true",
            },
            {"task-2"},
        ),
        ({"open_only": "true", "status": "closed"}, set()),
        ({"project_id": "missing"}, set()),
    ],
)
def test_filters_combine_with_and(client: TestClient, params: dict, ids: set[str]) -> None:
    response = client.get(TASKS, params=params)
    assert response.status_code == 200
    assert {task["id"] for task in response.json()} == ids


def test_deadline_boundary_and_clock_progression(today: date) -> None:
    clock = [today]
    with TestClient(create_app(today=lambda: clock[0])) as client:
        assert client.get(f"{TASKS}/task-3").json()["is_overdue"] is False
        assert client.get(f"{TASKS}/task-5").json()["is_overdue"] is False
        assert client.get(f"{TASKS}/task-6").json()["is_overdue"] is False
        clock[0] += timedelta(days=1)
        assert client.get(f"{TASKS}/task-3").json()["is_overdue"] is True
        assert client.get(f"{TASKS}/task-5").json()["is_overdue"] is False


def test_numbers_are_per_project_and_never_reused(client: TestClient) -> None:
    first = create_task(client)
    assert first["number"] == "ASTA-5"
    assert client.delete(f"{TASKS}/{first['id']}").status_code == 204
    assert create_task(client)["number"] == "ASTA-6"
    assert create_task(client, project_id="project-web")["number"] == "WEB-3"


def test_moving_project_assigns_a_new_number_and_keeps_id(client: TestClient) -> None:
    response = client.patch(f"{TASKS}/task-2", json={"project_id": "project-web"})
    assert response.status_code == 200
    assert response.json()["id"] == "task-2"
    assert response.json()["number"] == "WEB-3"
    assert create_task(client)["number"] == "ASTA-5"


def test_delete_removes_inbound_links(client: TestClient) -> None:
    response = client.delete(f"{TASKS}/task-2")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"{TASKS}/task-2").status_code == 404
    assert client.get(f"{TASKS}/task-1").json()["linked_task_ids"] == ["task-3"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "invalid"},
        {"type": "invalid"},
        {"description": "   "},
        {"description": None},
        {"spent_minutes": -1},
        {"spent_minutes": 1.5},
        {"spent_minutes": True},
        {"id": "custom-id"},
        {"number": "ASTA-100"},
        {"project_id": "missing"},
        {"assignee_id": "missing"},
        {"linked_task_ids": ["missing"]},
        {"linked_task_ids": ["task-1", "task-1"]},
        {"due_date": "not-a-date"},
    ],
)
def test_invalid_creates_do_not_mutate_state(client: TestClient, overrides: dict) -> None:
    response = client.post(TASKS, json={**CREATE_BODY, **overrides})
    assert response.status_code == 422
    assert response.json()["detail"]
    assert len(client.get(TASKS).json()) == 6
    assert create_task(client)["number"] == "ASTA-5"


@pytest.mark.parametrize(
    "payload",
    [
        {"description": None},
        {"project_id": None},
        {"type": None},
        {"status": None},
        {"spent_minutes": None},
        {"linked_task_ids": None},
        {"project_id": "missing"},
        {"assignee_id": "missing"},
        {"linked_task_ids": ["task-1"]},
        {"linked_task_ids": ["missing"]},
        {"linked_task_ids": ["task-2", "task-2"]},
        {"status": "invalid"},
        {"id": "new-id"},
        {"number": "ASTA-100"},
    ],
)
def test_invalid_updates_preserve_the_task(client: TestClient, payload: dict) -> None:
    original = client.get(f"{TASKS}/task-1").json()
    response = client.patch(f"{TASKS}/task-1", json=payload)
    assert response.status_code == 422
    assert client.get(f"{TASKS}/task-1").json() == original


def test_nullable_fields_can_be_cleared(client: TestClient) -> None:
    response = client.patch(f"{TASKS}/task-2", json={"due_date": None, "assignee_id": None})
    assert response.status_code == 200
    assert response.json()["due_date"] is None
    assert response.json()["assignee_id"] is None
    assert response.json()["is_overdue"] is False


@pytest.mark.parametrize("method", ["get", "patch", "delete", "status"])
def test_unknown_task_returns_404(client: TestClient, method: str) -> None:
    if method == "status":
        response = client.patch(f"{TASKS}/missing/status", json={"status": "closed"})
    elif method == "patch":
        response = client.patch(f"{TASKS}/missing", json={"description": "Новое описание"})
    else:
        response = getattr(client, method)(f"{TASKS}/missing")
    assert response.status_code == 404
    assert "не найдена" in response.json()["detail"]


def test_invalid_status_request_and_filter(client: TestClient) -> None:
    assert client.patch(f"{TASKS}/task-1/status", json={"status": "invalid"}).status_code == 422
    assert client.get(TASKS, params={"status": "invalid"}).status_code == 422
    assert client.post(TASKS, json={}).status_code == 422


def test_new_app_resets_data_and_instances_are_independent(client: TestClient, today: date) -> None:
    create_task(client)
    client.delete(f"{TASKS}/task-2")
    client.patch(f"{TASKS}/task-3/status", json={"status": "closed"})
    with TestClient(create_app(today=lambda: today)) as other:
        assert len(other.get(TASKS).json()) == 6
        assert other.get(f"{TASKS}/task-2").status_code == 200
        assert other.get(f"{TASKS}/task-3").json()["status"] == "in_review"
        assert create_task(other)["number"] == "ASTA-5"
    assert client.get(f"{TASKS}/task-2").status_code == 404


def test_parallel_creates_have_unique_numbers(client: TestClient) -> None:
    service = client.app.state.task_service
    payload = TaskCreate.model_validate(CREATE_BODY)
    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(lambda _: service.create_task(payload), range(40)))
    assert len({task.id for task in created}) == 40
    assert {task.number for task in created} == {f"ASTA-{number}" for number in range(5, 45)}
