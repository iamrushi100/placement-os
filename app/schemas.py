from pydantic import BaseModel


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
