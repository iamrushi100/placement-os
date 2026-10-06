from datetime import date

from pydantic import BaseModel, Field


class HabitCreate(BaseModel):
    name: str
    category: str
    description: str | None = None


class HabitResponse(BaseModel):
    id: int
    name: str
    category: str
    description: str | None
    is_active: int
    created_at: str


class DailyEntryCreate(BaseModel):
    date: date
    deep_work_minutes: int = Field(ge=0)


class DailyEntryResponse(BaseModel):
    id: int
    date: date
    deep_work_minutes: int
    created_at: str
