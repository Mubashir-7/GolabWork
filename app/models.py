from pydantic import BaseModel, field_validator
from typing import Any, Optional
from app.utils import VALID_CATEGORIES


class EventCreate(BaseModel):
    category: str
    payload: dict[str, Any]
    user_id: Optional[str] = None
    timestamp: Optional[str] = None

    @field_validator("category")
    @classmethod
    def category_must_be_valid(cls, v):
        if v not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )
        return v


class EventResponse(BaseModel):
    id: int
    category: str
    payload: dict[str, Any]
    user_id: Optional[str]
    timestamp: str
