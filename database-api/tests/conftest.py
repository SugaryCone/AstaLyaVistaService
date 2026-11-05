from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def today() -> date:
    return date(2026, 11, 5)


@pytest.fixture
def client(today: date) -> Iterator[TestClient]:
    with TestClient(create_app(today=lambda: today)) as test_client:
        yield test_client
