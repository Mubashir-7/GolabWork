"""
Tests for event endpoints.

Naming convention: test_<action>_<condition>
Use fixtures from conftest.py for test data setup.
"""


# --- POST /events ---


class TestCreateEvent:
    """Tests for the POST /events endpoint."""

    def test_create_event_with_all_fields(self, client, sample_event):
        response = client.post("/events", json=sample_event)
        assert response.status_code == 201

        data = response.json()
        assert data["id"] is not None
        assert data["category"] == "page_view"
        assert data["payload"] == {"page": "/home", "referrer": "google.com"}
        assert data["user_id"] == "user_123"
        assert data["timestamp"] is not None

    def test_create_event_without_optional_fields(self, client):
        response = client.post("/events", json={
            "category": "click",
            "payload": {"button": "signup"},
        })
        assert response.status_code == 201

        data = response.json()
        assert data["user_id"] is None
        assert data["timestamp"] is not None

    def test_create_event_with_custom_timestamp(self, client):
        response = client.post("/events", json={
            "category": "purchase",
            "payload": {"item": "widget", "amount": 29.99},
            "timestamp": "2026-03-01T12:00:00-05:00",
        })
        assert response.status_code == 201

        data = response.json()
        # Timestamp should be normalized to UTC
        assert "17:00:00" in data["timestamp"]
        assert "+00:00" in data["timestamp"]

    def test_create_event_invalid_category(self, client):
        response = client.post("/events", json={
            "category": "invalid_category",
            "payload": {"key": "value"},
        })
        assert response.status_code == 422

    def test_create_event_missing_payload(self, client):
        response = client.post("/events", json={
            "category": "click",
        })
        assert response.status_code == 422

    def test_create_event_invalid_timestamp(self, client):
        response = client.post("/events", json={
            "category": "click",
            "payload": {"key": "value"},
            "timestamp": "not-a-timestamp",
        })
        assert response.status_code == 400

        data = response.json()
        assert data["error"]["code"] == "invalid_input"
        assert "timestamp" in data["error"]["message"].lower()


# --- GET /events/{event_id} ---


class TestGetEvent:
    """Tests for the GET /events/{event_id} endpoint."""

    def test_get_existing_event(self, client, create_event, sample_event):
        created = create_event(sample_event)

        response = client.get(f"/events/{created['id']}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == created["id"]
        assert data["category"] == "page_view"
        assert data["payload"] == sample_event["payload"]

    def test_get_nonexistent_event(self, client):
        response = client.get("/events/99999")
        assert response.status_code == 404

        data = response.json()
        assert data["error"]["code"] == "not_found"
        assert "99999" in data["error"]["message"]


# --- GET /events ---


class TestListEvents:
    """Tests for the GET /events endpoint."""

    def test_list_events_returns_all(self, client, create_event):
        create_event({"category": "click", "payload": {"button": "signup"}})
        create_event({"category": "page_view", "payload": {"page": "/about"}})

        response = client.get("/events")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2

    def test_list_events_filter_by_category(self, client, create_event):
        create_event({"category": "click", "payload": {"button": "signup"}})
        create_event({"category": "page_view", "payload": {"page": "/about"}})
        create_event({"category": "click", "payload": {"button": "login"}})

        response = client.get("/events?category=click")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        assert all(e["category"] == "click" for e in data)

    def test_list_events_filter_by_user_id(self, client, create_event):
        create_event({"category": "click", "payload": {"button": "signup"}, "user_id": "user_1"})
        create_event({"category": "click", "payload": {"button": "login"}, "user_id": "user_2"})

        response = client.get("/events?user_id=user_1")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "user_1"

    def test_list_events_empty_result(self, client):
        response = client.get("/events?category=click")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_events_invalid_start_timestamp(self, client):
        response = client.get("/events?start=not-a-date")
        assert response.status_code == 400

        data = response.json()
        assert data["error"]["code"] == "invalid_input"


# --- DELETE /events/{event_id} ---


class TestDeleteEvent:
    """Tests for the DELETE /events/{event_id} endpoint."""

    def test_delete_event_success(self, client, create_event, sample_event):
        created = create_event(sample_event)

        response = client.delete(f"/events/{created['id']}")
        assert response.status_code == 204
        assert response.content == b""

        # Verify event is gone
        get_response = client.get(f"/events/{created['id']}")
        assert get_response.status_code == 404

    def test_delete_event_not_found(self, client):
        response = client.delete("/events/99999")
        assert response.status_code == 404

        data = response.json()
        assert data["error"]["code"] == "not_found"
        assert "99999" in data["error"]["message"]


# --- GET /stats ---


class TestGetStats:
    """Tests for the GET /stats endpoint."""

    def test_get_stats_basic(self, client, create_event):
        create_event({"category": "click", "payload": {"button": "signup"}, "user_id": "user_1"})
        create_event({"category": "click", "payload": {"button": "login"}, "user_id": "user_2"})
        create_event({"category": "page_view", "payload": {"page": "/home"}, "user_id": "user_1"})

        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_events"] == 3
        assert data["events_by_category"]["click"] == 2
        assert data["events_by_category"]["page_view"] == 1
        assert data["unique_users"] == 2
        assert data["first_event"] is not None
        assert data["last_event"] is not None

    def test_get_stats_with_category_filter(self, client, create_event):
        create_event({"category": "click", "payload": {"button": "signup"}, "user_id": "user_1"})
        create_event({"category": "page_view", "payload": {"page": "/home"}, "user_id": "user_2"})

        response = client.get("/stats?category=click")
        assert response.status_code == 200

        data = response.json()
        assert data["total_events"] == 1
        # events_by_category must also respect the filter
        assert "click" in data["events_by_category"]
        assert "page_view" not in data["events_by_category"]

    def test_get_stats_empty(self, client):
        """Stats with no events must return nulls, not crash."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_events"] == 0
        assert data["events_by_category"] == {}
        assert data["unique_users"] == 0
        assert data["first_event"] is None
        assert data["last_event"] is None

    def test_get_stats_empty_after_filter(self, client, create_event):
        """Stats with a filter that matches no events must return nulls, not crash."""
        create_event({"category": "click", "payload": {"button": "signup"}, "user_id": "user_1"})

        response = client.get("/stats?category=purchase")
        assert response.status_code == 200

        data = response.json()
        assert data["total_events"] == 0
        assert data["first_event"] is None
        assert data["last_event"] is None


# --- Additional regression tests ---


class TestListEventsSorting:
    """list_events must return events newest-first."""

    def test_list_events_sorted_newest_first(self, client, create_event):
        create_event({
            "category": "click",
            "payload": {},
            "timestamp": "2026-01-01T00:00:00+00:00",
        })
        create_event({
            "category": "click",
            "payload": {},
            "timestamp": "2026-03-01T00:00:00+00:00",
        })
        create_event({
            "category": "click",
            "payload": {},
            "timestamp": "2026-02-01T00:00:00+00:00",
        })

        response = client.get("/events")
        assert response.status_code == 200

        data = response.json()
        timestamps = [e["timestamp"] for e in data]
        assert timestamps == sorted(timestamps, reverse=True)


class TestListEventsSQLInjection:
    """list_events must use parameterized queries, not string interpolation."""

    def test_sql_injection_in_category_does_not_return_all_events(self, client, create_event):
        create_event({"category": "click", "payload": {"button": "x"}, "user_id": "u1"})

        # Classic SQL injection payload — if unsanitized, returns all rows
        response = client.get("/events?category=click' OR '1'='1")
        assert response.status_code == 200
        # Must return 0 results (no category literally equals that string)
        assert response.json() == []

    def test_sql_injection_in_user_id_does_not_return_all_events(self, client, create_event):
        create_event({"category": "click", "payload": {"button": "x"}, "user_id": "u1"})

        response = client.get("/events?user_id=u1' OR '1'='1")
        assert response.status_code == 200
        assert response.json() == []


class TestTimestampNormalization:
    """Filter timestamps must be normalized to UTC before SQL comparison."""

    def test_list_events_start_filter_with_timezone_offset(self, client, create_event):
        create_event({
            "category": "click",
            "payload": {},
            "timestamp": "2026-03-01T12:00:00+00:00",
        })

        # This is 17:00 UTC — event at 12:00 UTC should be excluded
        response = client.get("/events?start=2026-03-01T12:00:00-05:00")
        assert response.status_code == 200
        assert response.json() == []

    def test_stats_start_filter_with_timezone_offset(self, client, create_event):
        create_event({
            "category": "click",
            "payload": {},
            "timestamp": "2026-03-01T12:00:00+00:00",
        })

        # 2026-03-01T12:00:00-05:00 == 2026-03-01T17:00:00+00:00 — event at 12:00 UTC excluded
        response = client.get("/stats?start=2026-03-01T12:00:00-05:00")
        assert response.status_code == 200
        assert response.json()["total_events"] == 0
