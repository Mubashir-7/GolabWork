"""
Event Log API — main application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.routes.events import router as events_router


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(
    title="Event Log API",
    description="A simple event logging and analytics API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(events_router)
