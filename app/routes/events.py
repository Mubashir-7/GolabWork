"""
Event routes.

Endpoints:
    POST   /events       - Create a new event
    GET    /events/{id}  - Retrieve a single event
    GET    /events       - List events with optional filters
    DELETE /events/{id}  - Delete an event
    GET    /stats        - Event statistics with optional filters
"""

import json
from typing import Optional

from fastapi import APIRouter, Response

from app.database import get_db
from app.models import EventCreate, EventResponse
from app.errors import not_found, invalid_input
from app.utils import now_utc, parse_timestamp

router = APIRouter()


def _row_to_event(row) -> dict:
    """Convert a database row to an EventResponse-compatible dict."""
    return {
        "id": row["id"],
        "category": row["category"],
        "payload": json.loads(row["payload"]),
        "user_id": row["user_id"],
        "timestamp": row["timestamp"],
    }


@router.post("/events", status_code=201)
def create_event(event: EventCreate):
    """Create a new event."""
    if event.timestamp:
        try:
            parsed = parse_timestamp(event.timestamp)
            ts = parsed.isoformat()
        except ValueError as e:
            return invalid_input(str(e))
    else:
        ts = now_utc()

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO events (category, payload, user_id, timestamp) VALUES (?, ?, ?, ?)",
            (event.category, json.dumps(event.payload), event.user_id, ts),
        )
        db.commit()
        event_id = cursor.lastrowid

        row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return _row_to_event(row)
    finally:
        db.close()


@router.get("/events/{event_id}")
def get_event(event_id: int):
    """Retrieve a single event by ID."""
    db = get_db()
    try:
        row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            return not_found("Event", event_id)
        return _row_to_event(row)
    finally:
        db.close()


@router.get("/events")
def list_events(
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """List events with optional filters."""
    db = get_db()
    try:
        where_clauses = []
        params = []

        if category:
            where_clauses.append("category = ?")
            params.append(category)
        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)

        if start:
            try:
                start_dt = parse_timestamp(start)
            except ValueError:
                return invalid_input(f"Invalid ISO 8601 timestamp: {start}")
            where_clauses.append("timestamp >= ?")
            params.append(start_dt.isoformat())

        if end:
            try:
                end_dt = parse_timestamp(end)
            except ValueError:
                return invalid_input(f"Invalid ISO 8601 timestamp: {end}")
            where_clauses.append("timestamp <= ?")
            params.append(end_dt.isoformat())

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        rows = db.execute(
            f"SELECT * FROM events {where_sql} ORDER BY timestamp DESC", params
        ).fetchall()
        return [_row_to_event(row) for row in rows]
    finally:
        db.close()


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int):
    """Delete an event."""
    db = get_db()
    try:
        row = db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            return not_found("Event", event_id)

        db.execute("DELETE FROM events WHERE id = ?", (event_id,))
        db.commit()
        return Response(status_code=204)
    finally:
        db.close()


@router.get("/stats")
def get_stats(
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Get event statistics with optional filters."""
    db = get_db()
    try:
        where_clauses = []
        params = []

        if category:
            where_clauses.append("category = ?")
            params.append(category)
        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if start:
            try:
                start_dt = parse_timestamp(start)
            except ValueError:
                return invalid_input(f"Invalid ISO 8601 timestamp: {start}")
            where_clauses.append("timestamp >= ?")
            params.append(start_dt.isoformat())
        if end:
            try:
                end_dt = parse_timestamp(end)
            except ValueError:
                return invalid_input(f"Invalid ISO 8601 timestamp: {end}")
            where_clauses.append("timestamp <= ?")
            params.append(end_dt.isoformat())

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Total events
        row = db.execute(
            f"SELECT COUNT(*) as count FROM events {where_sql}", params
        ).fetchone()
        total_events = row["count"]

        # Events by category (must respect filters)
        cat_rows = db.execute(
            f"SELECT category, COUNT(*) as count FROM events {where_sql} GROUP BY category",
            params,
        ).fetchall()
        events_by_category = {row["category"]: row["count"] for row in cat_rows}

        # Unique users
        user_rows = db.execute(
            f"SELECT user_id FROM events {where_sql}", params
        ).fetchall()
        unique_users = len(set(row["user_id"] for row in user_rows if row["user_id"]))

        # First and last event timestamps
        first_row = db.execute(
            f"SELECT timestamp FROM events {where_sql} ORDER BY timestamp ASC LIMIT 1",
            params,
        ).fetchone()
        first_event = first_row["timestamp"] if first_row else None

        last_row = db.execute(
            f"SELECT timestamp FROM events {where_sql} ORDER BY timestamp DESC LIMIT 1",
            params,
        ).fetchone()
        last_event = last_row["timestamp"] if last_row else None

        return {
            "total_events": total_events,
            "events_by_category": events_by_category,
            "unique_users": unique_users,
            "first_event": first_event,
            "last_event": last_event,
        }
    finally:
        db.close()
