from datetime import date

from pydantic import BaseModel, Field, field_validator


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


class MITCreate(BaseModel):
    date: date
    task: str

    @field_validator("task")
    @classmethod
    def task_must_not_be_empty(cls, value: str) -> str:
        task = value.strip()
        if not task:
            raise ValueError("Task must not be empty")
        return task


class MITResponse(BaseModel):
    id: int
    date: date
    task: str
    completed: int
    created_at: str


class ReflectionCreate(BaseModel):
    date: date
    went_well: str = ""
    challenges: str = ""
    improvement: str = ""


class ReflectionResponse(BaseModel):
    id: int
    date: date
    went_well: str
    challenges: str
    improvement: str
    created_at: str
