"""
Shared test fixtures.

All tests use an isolated temporary database via the `client` fixture.
Use `sample_event` and `create_event` for test data setup.
"""

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    """
    Provide a test client with a fresh database for each test.

    Every test gets an isolated database. No state leaks between tests.
    """
    db_path = str(tmp_path / "test_events.db")
    os.environ["DATABASE_PATH"] = db_path

    from app.database import init_db, reset_db
    from app.main import app

    reset_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_event() -> dict:
    """A valid event payload for use in tests."""
    return {
        "category": "page_view",
        "payload": {"page": "/home", "referrer": "google.com"},
        "user_id": "user_123",
    }


@pytest.fixture
def create_event(client):
    """
    Factory fixture to create events in the database via the API.

    Usage:
        event = create_event({"category": "click", "payload": {"button": "signup"}})
        assert event["id"] is not None
    """
    def _create(data: dict) -> dict:
        response = client.post("/events", json=data)
        assert response.status_code == 201, f"Failed to create event: {response.text}"
        return response.json()
    return _create
