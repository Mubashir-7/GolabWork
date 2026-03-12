# Event Log API

A simple event logging and analytics API built with FastAPI.

## Setup

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

## Test

```bash
pytest -v
```

## API Endpoints

### POST /events
Create a new event.

### GET /events/{event_id}
Retrieve a single event by ID.

### GET /events
List events with optional filters: `category`, `user_id`, `start`, `end`.

### DELETE /events/{event_id}
Delete an event.

### GET /stats
Get event statistics. Supports the same filters as GET /events.

Returns: `total_events`, `events_by_category`, `unique_users`, `first_event`, `last_event`.
