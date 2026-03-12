# FIXES.md — Event Log API Bug Report

Issues are ordered by severity (critical first).

---

## Fixed Issues

---

### 1. SQL Injection in `list_events`
**Severity: Critical**

**File:** `app/routes/events.py`, `list_events()`, lines 89–105 (original)

**Problem:**
The `category`, `user_id`, `start`, and `end` query parameters were interpolated directly into the SQL string using f-strings:

```python
query += f" AND category = '{category}'"
query += f" AND user_id = '{user_id}'"
query += f" AND timestamp >= '{start}'"
query += f" AND timestamp <= '{end}'"
```

An attacker could pass `click' OR '1'='1` as the `category` parameter to bypass the filter and return all events, or craft more destructive payloads (e.g., to dump or corrupt data). The rest of the codebase (`get_stats`, all INSERT/SELECT by ID) correctly uses parameterized `?` placeholders — this endpoint was the outlier.

**Why it matters:** SQL injection is a top-tier security vulnerability. It can result in unauthorized data access, data corruption, or full database compromise.

**Fix:** Rewrote `list_events` to use the same parameterized query pattern as `get_stats`: accumulate `where_clauses` and `params` lists, join them, and pass `params` to `db.execute()`.

**New tests:** `TestListEventsSQLInjection::test_sql_injection_in_category_does_not_return_all_events`, `test_sql_injection_in_user_id_does_not_return_all_events`

---

### 2. `get_stats` crashes when no events exist (NoneType error)
**Severity: High**

**File:** `app/routes/events.py`, `get_stats()`, lines 190–196 (original)

**Problem:**
When no events match the query (empty database or filter that matches nothing), both `first_row` and `last_row` are `None`. The code then unconditionally accessed `first_row["timestamp"]` and `last_row["timestamp"]`, causing an unhandled `TypeError: 'NoneType' object is not subscriptable` — a 500 Internal Server Error.

```python
first_event = first_row["timestamp"]   # crashes if first_row is None
last_event = last_row["timestamp"]     # crashes if last_row is None
```

**Why it matters:** Any call to `GET /stats` on an empty database (or with a filter that matches nothing) raises an unhandled exception. This is a correctness bug that also leaks a 500 error to clients.

**Fix:** Added None guard: `first_row["timestamp"] if first_row else None` (same for `last_row`).

**New tests:** `TestGetStats::test_get_stats_empty`, `TestGetStats::test_get_stats_empty_after_filter`

---

### 3. `events_by_category` in `get_stats` ignores all filters
**Severity: High**

**File:** `app/routes/events.py`, `get_stats()`, lines 174–177 (original)

**Problem:**
The `events_by_category` query had no `WHERE` clause and no parameters:

```python
cat_rows = db.execute(
    "SELECT category, COUNT(*) as count FROM events GROUP BY category"
).fetchall()
```

This always returns counts for all events in the database, regardless of any `category`, `user_id`, `start`, or `end` filters. The other stats fields (`total_events`, `unique_users`, `first_event`, `last_event`) all correctly applied `where_sql` and `params`.

**Why it matters:** The API spec says all statistics should reflect the applied filters. A caller filtering by `user_id` would see correct `total_events` but completely wrong `events_by_category`.

**Fix:** Added `{where_sql}` and `params` to the `events_by_category` query.

**New test:** `TestGetStats::test_get_stats_with_category_filter` was extended to assert `"page_view" not in data["events_by_category"]` when filtering by `category=click`.

---

### 4. `list_events` missing `ORDER BY timestamp DESC`
**Severity: High**

**File:** `app/routes/events.py`, `list_events()`, line 107 (original)

**Problem:**
The query had no `ORDER BY` clause:

```python
rows = db.execute(query).fetchall()
```

The API spec explicitly states: "Returns events sorted by timestamp descending (newest first)." Without the clause, SQLite returns rows in insertion order (or arbitrary order), which is non-deterministic and violates the spec.

**Why it matters:** Clients relying on sort order for pagination, display, or processing get unpredictable results.

**Fix:** Added `ORDER BY timestamp DESC` to the query.

**New test:** `TestListEventsSorting::test_list_events_sorted_newest_first`

---

### 5. `delete_event` returns 200 with body instead of 204 with no body
**Severity: High**

**File:** `app/routes/events.py`, `delete_event()`, lines 113–126 (original)

**Problem:**
The endpoint returned `{"message": "Event deleted successfully"}` with the default 200 status code:

```python
return {"message": "Event deleted successfully"}
```

The API spec says: "Returns 204 on success." HTTP 204 means No Content — the response must have no body. The existing test also incorrectly asserted `status_code == 200`, masking this bug.

**Why it matters:** Clients that check for 204 (the standard for successful DELETE) would treat the response as a failure.

**Fix:** Added `status_code=204` to the `@router.delete` decorator and returned `Response(status_code=204)` with no body.

**Test updated:** `TestDeleteEvent::test_delete_event_success` now asserts `status_code == 204` and `response.content == b""`.

---

### 6. `delete_event` uses `HTTPException` instead of standardized error format
**Severity: High**

**File:** `app/routes/events.py`, `delete_event()`, line 120 (original)

**Problem:**
The 404 branch raised `HTTPException`:

```python
raise HTTPException(status_code=404, detail="Event not found")
```

This produces `{"detail": "Event not found"}`. The `app/errors.py` module explicitly documents: *"Do NOT use FastAPI's default HTTPException — it produces a different response format that is inconsistent with our API."* Every other endpoint uses `not_found()` / `invalid_input()` from `app/errors.py`, which produce `{"error": {"code": "...", "message": "..."}}`.

**Why it matters:** Inconsistent error format — clients that parse error responses by `error.code` would silently fail on DELETE 404s. The existing test only checked the status code, not the body, so this was invisible.

**Fix:** Replaced `raise HTTPException(...)` with `return not_found("Event", event_id)`.

**Test updated:** `TestDeleteEvent::test_delete_event_not_found` now also asserts `data["error"]["code"] == "not_found"` and that the event ID appears in the message.

---

### 7. Filter timestamps not normalized to UTC before SQL comparison
**Severity: Medium**

**File:** `app/routes/events.py`, `list_events()` lines 94–105 and `get_stats()` lines 148–161 (original)

**Problem:**
Both endpoints validated the `start`/`end` filter timestamps but then passed the **raw user-supplied string** to the SQL query:

```python
# list_events (original)
datetime.fromisoformat(start)     # just validates, returns nothing
query += f" AND timestamp >= '{start}'"  # raw string used

# get_stats (original)
parse_timestamp(start)            # just validates, returns nothing
params.append(start)              # raw string used
```

Events are stored as UTC ISO 8601 strings (e.g., `2026-03-01T12:00:00+00:00`). SQLite compares timestamps as strings. If a caller passes `2026-03-01T12:00:00-05:00` (which is `17:00 UTC`), SQLite compares it lexicographically against `+00:00`-suffixed strings. Because `-` (ASCII 45) sorts before `+` (ASCII 43) in ASCII... actually `-` > `+` in ASCII, meaning `2026-03-01T12:00:00-05:00` would compare as greater than `2026-03-01T12:00:00+00:00`, which is semantically wrong (the UTC time would be 17:00 vs 12:00).

**Why it matters:** Date range filters produce incorrect results when the caller uses a non-UTC timezone offset.

**Fix:** In both endpoints, capture the return value of `parse_timestamp()` (which normalizes to UTC) and use `.isoformat()` as the SQL parameter. In `list_events`, also replaced the inconsistent `datetime.fromisoformat()` call with `parse_timestamp()` for consistency.

**New tests:** `TestTimestampNormalization::test_list_events_start_filter_with_timezone_offset`, `test_stats_start_filter_with_timezone_offset`

---

### 8. `list_events` used `datetime.fromisoformat()` instead of shared `parse_timestamp()`
**Severity: Low**

**File:** `app/routes/events.py`, `list_events()`, lines 96, 102 (original)

**Problem:**
`list_events` validated timestamps with `datetime.fromisoformat()` directly, while `get_stats` (and `create_event`) used the shared `parse_timestamp()` utility from `app/utils.py`. The comment in `app/utils.py` states: *"All timestamp handling should use the functions in this module."*

```python
# list_events (original) — inconsistent
datetime.fromisoformat(start)

# get_stats (original) — consistent
parse_timestamp(start)
```

Beyond inconsistency, `datetime.fromisoformat()` also doesn't produce the UTC-normalized value needed for correct SQL comparisons (see Issue 7).

**Why it matters:** Utility functions exist to centralize behavior. Bypassing them means changes to timestamp handling (e.g., adding support for additional formats) would need to be applied in multiple places.

**Fix:** Replaced all `datetime.fromisoformat()` calls in routes with `parse_timestamp()`. The `datetime` import was also removed since it was no longer used after this fix.

---

## Summary Table

| # | Location | Severity | Category |
|---|----------|----------|----------|
| 1 | `list_events` — category/user_id/start/end filters | Critical | Security |
| 2 | `get_stats` — NoneType crash on empty results | High | Correctness |
| 3 | `get_stats` — events_by_category ignores filters | High | Correctness |
| 4 | `list_events` — missing ORDER BY timestamp DESC | High | Correctness |
| 5 | `delete_event` — wrong status code (200 vs 204) | High | Correctness |
| 6 | `delete_event` — HTTPException vs standardized error | High | Consistency |
| 7 | `list_events`/`get_stats` — raw timestamp in SQL | Medium | Correctness |
| 8 | `list_events` — datetime.fromisoformat() vs parse_timestamp() | Low | Consistency |
