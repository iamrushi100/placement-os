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
PreparationTopicStatus = Literal["Not Started", "In Progress", "Completed"]


class PreparationCategoryCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def category_name_must_not_be_empty(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Category name must not be empty")
        return name


class PreparationCategoryUpdate(BaseModel):
    name: str | None = None

    @field_validator("name")
    @classmethod
    def supplied_category_name_must_not_be_empty(
        cls, value: str | None
    ) -> str | None:
        if value is None:
            return value
        name = value.strip()
        if not name:
            raise ValueError("Category name must not be empty")
        return name

    @model_validator(mode="after")
    def provided_name_cannot_be_null(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Category name cannot be null")
        return self


class PreparationCategoryResponse(BaseModel):
    id: int
    name: str
    created_at: str


class PreparationTopicCreate(BaseModel):
    category_id: int
    name: str
    status: PreparationTopicStatus = "Not Started"
    practice_count: int = Field(default=0, ge=0)
    notes: str = ""

    @field_validator("name")
    @classmethod
    def topic_name_must_not_be_empty(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Topic name must not be empty")
        return name


class PreparationTopicUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = None
    status: PreparationTopicStatus | None = None
    practice_count: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def supplied_topic_name_must_not_be_empty(
        cls, value: str | None
    ) -> str | None:
        if value is None:
            return value
        name = value.strip()
        if not name:
            raise ValueError("Topic name must not be empty")
        return name

    @model_validator(mode="after")
    def required_fields_cannot_be_cleared(self):
        for field_name in ("category_id", "name", "status", "practice_count"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class PreparationTopicResponse(BaseModel):
    id: int
    category_id: int
    name: str
    status: PreparationTopicStatus
    practice_count: int
    notes: str
    created_at: str
    updated_at: str
DeepWorkCategory = Literal[
    "DSA",
    "SQL",
    "Python",
    "AI/ML",
    "GenAI",
    "Cybersecurity",
    "Project",
    "Interview Preparation",
    "Other",
]
DeepWorkSource = Literal["manual", "timer"]


class DeepWorkSessionCreate(BaseModel):
    date: date
    duration_minutes: int = Field(ge=30)
    category: DeepWorkCategory
    notes: str | None = None


class DeepWorkSessionResponse(BaseModel):
    id: int
    date: date
    duration_minutes: int
    category: DeepWorkCategory
    notes: str | None
    started_at: str | None
    ended_at: str | None
    source: DeepWorkSource
    created_at: str


class DeepWorkTimerStart(BaseModel):
    category: DeepWorkCategory
    notes: str | None = None


class DeepWorkTimerResponse(BaseModel):
    id: int
    category: DeepWorkCategory
    notes: str | None
    started_at: str
    source: Literal["timer"]


class DeepWorkTimerStopResponse(BaseModel):
    completed: bool
    duration_minutes: int
    message: str
    session: DeepWorkSessionResponse | None = None


class DailyDeepWorkSummary(BaseModel):
    date: date
    total_minutes: int
    target_minutes: int
    progress_percentage: float
    sessions: list[DeepWorkSessionResponse]

class DashboardSettingsResponse(BaseModel):
    goal: str
    daily_deep_work_target_minutes: int


class DashboardSettingsUpdate(BaseModel):
    goal: str | None = Field(default=None, max_length=200)
    daily_deep_work_target_minutes: int | None = Field(default=None, ge=1, le=1440)

    @field_validator("goal")
    @classmethod
    def goal_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        goal = value.strip()
        if not goal:
            raise ValueError("Goal must not be empty")
        return goal

    @model_validator(mode="after")
    def at_least_one_setting_must_be_supplied(self):
        if not self.model_fields_set:
            raise ValueError("Supply a goal or daily deep-work target")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class DashboardApplicationsSummary(BaseModel):
    active: int
    pipeline: dict[str, int]


class DashboardNextDeadline(BaseModel):
    opportunity_id: int
    company: str
    role: str
    deadline: date


class DashboardCategoryProgress(BaseModel):
    category_id: int
    category: str
    total_topics: int
    completed_topics: int
    completion_percentage: float


class DashboardPreparationSummary(BaseModel):
    total_topics: int
    completed: int
    in_progress: int
    not_started: int
    completion_percentage: float
    total_practice_count: int
    categories: list[DashboardCategoryProgress]


class DashboardDeepWorkPeriod(BaseModel):
    target_minutes: int
    actual_minutes: int
    progress_percentage: float


class DashboardDeepWorkSummary(BaseModel):
    daily: DashboardDeepWorkPeriod
    weekly: DashboardDeepWorkPeriod


class DashboardFocusTopic(BaseModel):
    id: int
    category_id: int
    category: str
    name: str
    status: PreparationTopicStatus
    practice_count: int
    notes: str


class DashboardTodayFocus(BaseModel):
    mits: list[MITResponse]
    incomplete_topics: list[DashboardFocusTopic]


class DashboardResponse(BaseModel):
    goal: str
    applications: DashboardApplicationsSummary
    next_deadline: DashboardNextDeadline | None
    preparation: DashboardPreparationSummary
    deep_work: DashboardDeepWorkSummary
    today: DashboardTodayFocus
