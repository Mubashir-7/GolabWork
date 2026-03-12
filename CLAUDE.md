# CLAUDE.md — Event Log API

## Project Overview
FastAPI + SQLite event logging API. 5 endpoints, 17 tests.
Entry point: `app/main.py`. Routes: `app/routes/events.py`.

## Architecture
- `app/main.py` — FastAPI app + lifespan
- `app/routes/events.py` — All 5 endpoint handlers
- `app/models.py` — Pydantic request/response models (EventCreate, EventResponse)
- `app/utils.py` — ONLY timestamp source of truth: `now_utc()`, `parse_timestamp()`, `format_timestamp()`, `VALID_CATEGORIES`
- `app/errors.py` — ONLY error format source of truth: `error_response()`, `not_found()`, `invalid_input()`
- `app/database.py` — `get_db()` returns sqlite3 connection with row_factory; `init_db()` / `reset_db()` for setup
- `tests/conftest.py` — `client` (isolated tmp DB), `sample_event`, `create_event` fixtures
- `tests/test_events.py` — Tests grouped in classes by endpoint

## Non-Negotiable Patterns (do not deviate)
1. **Error format**: ALWAYS use `not_found()` / `invalid_input()` / `error_response()` from `app/errors.py`. NEVER use FastAPI `HTTPException` — it produces `{"detail":"..."}` which breaks the API contract.
2. **Timestamps**: ALWAYS use `parse_timestamp()` from `app/utils.py` for parsing (normalizes to UTC). ALWAYS use `now_utc()` for current time. Never use `datetime.fromisoformat()` directly in routes.
3. **SQL queries**: ALWAYS use parameterized queries (`?` placeholders). NEVER use f-strings or string concatenation in SQL — SQL injection risk.
4. **DB connections**: Always use `try/finally: db.close()` — already the pattern everywhere.
5. **Category validation**: Use `VALID_CATEGORIES` set from `app/utils.py`.

## API Spec Constraints (spec beats tests when they conflict)
- `GET /events` — must sort `ORDER BY timestamp DESC`
- `DELETE /events/{id}` — must return 204 with no body on success; 404 with `not_found()` format if missing
- `GET /stats` — `events_by_category` must respect the same filters as `total_events`; `first_event`/`last_event` must be `null` when no events match
- Timestamps stored as UTC ISO 8601. Filter params must be normalized to UTC before SQL comparison.

## Running Tests
```bash
pytest tests/ -v
```

## Review Focus Areas
When reviewing this codebase, check in priority order:
1. SQL injection in any raw string query building
2. Error response format — HTTPException vs error_response()
3. HTTP status codes matching the spec
4. Filter logic correctness — do all stats fields respect the same filters?
5. Null/empty cases — what happens when no events exist?
6. Timestamp handling — are filter params normalized to UTC before comparison?
7. Sort order on list endpoints
8. Utility consistency — are shared utils always used, or are there duplicate implementations?
