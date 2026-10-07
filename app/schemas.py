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

from typing import Literal

from pydantic import model_validator


OpportunityStatus = Literal[
    "Interested",
    "Applied",
    "Assessment",
    "Interview",
    "HR",
    "Selected",
    "Rejected",
    "Withdrawn",
    "Not Eligible",
    "Expired",
]
OpportunityPriority = Literal["Low", "Medium", "High"]


class OpportunityCreate(BaseModel):
    company: str
    role: str
    location: str | None = None
    source: str | None = None
    job_link: str | None = None
    status: OpportunityStatus = "Interested"
    priority: OpportunityPriority = "Medium"
    ctc: str | None = None
    deadline: date | None = None
    referral: str | None = None
    eligibility: str | None = None
    requirements: str | None = None
    notes: str | None = None
    is_serious: bool = False

    @field_validator("company", "role")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Field must not be empty")
        return text


class OpportunityUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    location: str | None = None
    source: str | None = None
    job_link: str | None = None
    status: OpportunityStatus | None = None
    priority: OpportunityPriority | None = None
    ctc: str | None = None
    deadline: date | None = None
    referral: str | None = None
    eligibility: str | None = None
    requirements: str | None = None
    notes: str | None = None
    is_serious: bool | None = None

    @field_validator("company", "role")
    @classmethod
    def supplied_text_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        text = value.strip()
        if not text:
            raise ValueError("Field must not be empty")
        return text

    @model_validator(mode="after")
    def non_nullable_fields_cannot_be_cleared(self):
        for field_name in ("company", "role", "status", "priority", "is_serious"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class OpportunityResponse(BaseModel):
    id: int
    company: str
    role: str
    location: str | None
    source: str | None
    job_link: str | None
    status: OpportunityStatus
    priority: OpportunityPriority
    ctc: str | None
    deadline: date | None
    referral: str | None
    eligibility: str | None
    requirements: str | None
    notes: str | None
    is_serious: bool
    created_at: str
    updated_at: str