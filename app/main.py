import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.database import DATABASE_PATH, database_connection, initialize_database
from app.schemas import (
    DailyEntryCreate,
    DailyEntryResponse,
    HabitCreate,
    HabitResponse,
    MITCreate,
    MITResponse,
    ReflectionCreate,
    ReflectionResponse,
    OpportunityCreate,
    OpportunityResponse,
    OpportunityStatus,
    OpportunityUpdate,
    PreparationCategoryCreate,
    PreparationCategoryResponse,
    PreparationCategoryUpdate,
    PreparationTopicCreate,
    PreparationTopicResponse,
    PreparationTopicStatus,
    PreparationTopicUpdate,
    DailyDeepWorkSummary,
    DeepWorkCategory,
    DeepWorkSessionCreate,
    DeepWorkSessionResponse,
    DeepWorkTimerResponse,
    DeepWorkTimerStart,
    DeepWorkTimerStopResponse,
    DashboardResponse,
    DashboardSettingsResponse,
    DashboardSettingsUpdate,
    PerformanceEntryCreate,
    PerformanceEntryResponse,
    PerformanceEntryUpdate,
    PerformanceLevel,
    PerformanceSummaryResponse,
    PerformanceType,
)

app = FastAPI()
STATIC_DIR = Path(__file__).resolve().parent.parent / 'static'
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

SPRINT_START = date(2026, 10, 6)
SPRINT_END = date(2026, 11, 5)
PLACEMENT_THRESHOLD = 60
DEEP_WORK_TARGET_MINUTES = 180
MIN_DEEP_WORK_SESSION_MINUTES = 30
DEFAULT_PLACEMENT_GOAL = "Get placed in a good software / AI role"
DASHBOARD_SETTING_DEFAULTS = {
    "placement_goal": DEFAULT_PLACEMENT_GOAL,
    "daily_deep_work_target_minutes": str(DEEP_WORK_TARGET_MINUTES),
}
PLACEMENT_PIPELINE_STATUSES = (
    "Interested", "Applied", "Assessment", "Interview", "HR",
    "Selected", "Rejected", "Withdrawn", "Not Eligible", "Expired",
)
ACTIVE_APPLICATION_STATUSES = ("Interested", "Applied", "Assessment", "Interview", "HR")



@app.on_event("startup")
def startup_event():
    initialize_database()


def current_local_datetime() -> datetime:
    """Return a timezone-aware timestamp in the server's local timezone."""
    return datetime.now().astimezone()


def get_deep_work_minutes(connection: sqlite3.Connection, requested_date: date) -> int:
    date_string = requested_date.isoformat()
    session_totals = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0) "
        "FROM deep_work_sessions WHERE date = ?",
        (date_string,),
    ).fetchone()
    if session_totals[0]:
        return session_totals[1]

    daily_entry = connection.execute(
        "SELECT deep_work_minutes FROM daily_entries WHERE date = ?",
        (date_string,),
    ).fetchone()
    return daily_entry[0] if daily_entry else 0

def calculate_current_streak(completion_dates: list[str], today: date) -> int:
    completed_days = set(completion_dates)
    streak = 0
    current_day = today
    while current_day.isoformat() in completed_days:
        streak += 1
        current_day -= timedelta(days=1)
    return streak


def calculate_daily_score(connection: sqlite3.Connection, requested_date: date) -> dict:
    date_string = requested_date.isoformat()
    deep_work_minutes = get_deep_work_minutes(connection, requested_date)
    technical_completed = connection.execute(
        "SELECT COUNT(*) FROM habit_completions AS completion "
        "JOIN habits AS habit ON habit.id = completion.habit_id "
        "WHERE completion.date = ? AND completion.completed = 1 "
        "AND habit.category = 'Technical'",
        (date_string,),
    ).fetchone()[0]
    placement_completed = connection.execute(
        "SELECT COUNT(*) FROM habit_completions AS completion "
        "JOIN habits AS habit ON habit.id = completion.habit_id "
        "WHERE completion.date = ? AND completion.completed = 1 "
        "AND habit.category = 'Placement'",
        (date_string,),
    ).fetchone()[0]

    deep_work_points = min(deep_work_minutes / DEEP_WORK_TARGET_MINUTES, 1) * 40
    technical_points = technical_completed / 5 * 30
    placement_points = placement_completed / 5 * 30
    score = int(round(deep_work_points + technical_points + placement_points))

    return {
        "date": date_string,
        "score": score,
        "deep_work_points": deep_work_points,
        "technical_points": technical_points,
        "placement_points": placement_points,
        "technical_completed": technical_completed,
        "placement_completed": placement_completed,
    }


def calculate_placement_streak(scores_by_date: dict[str, int], today: date) -> int:
    if today < SPRINT_START:
        return 0

    current_day = min(today, SPRINT_END)
    streak = 0
    while current_day >= SPRINT_START:
        if scores_by_date.get(current_day.isoformat(), 0) < PLACEMENT_THRESHOLD:
            break
        streak += 1
        current_day -= timedelta(days=1)
    return streak


@app.post("/api/habits", response_model=HabitResponse)
def create_habit(habit: HabitCreate):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            "INSERT INTO habits (name, category, description) VALUES (?, ?, ?)",
            (habit.name, habit.category, habit.description),
        )
        created_habit = connection.execute(
            "SELECT id, name, category, description, is_active, created_at "
            "FROM habits WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(created_habit)


@app.get("/api/habits", response_model=list[HabitResponse])
def get_habits():
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        habits = connection.execute(
            "SELECT id, name, category, description, is_active, created_at "
            "FROM habits ORDER BY id"
        ).fetchall()
        return [dict(habit) for habit in habits]


@app.get("/api/habits/today")
def get_today_habits():
    today = date.today().isoformat()
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        habits = connection.execute(
            "SELECT habit.id, habit.name, habit.category, habit.description, "
            "CASE WHEN completion.id IS NULL THEN 0 ELSE 1 END AS completed "
            "FROM habits AS habit "
            "LEFT JOIN habit_completions AS completion "
            "ON completion.habit_id = habit.id "
            "AND completion.date = ? AND completion.completed = 1 "
            "WHERE habit.is_active = 1 ORDER BY habit.id",
            (today,),
        ).fetchall()
        return [
            {
                "id": habit["id"],
                "name": habit["name"],
                "category": habit["category"],
                "description": habit["description"],
                "completed": bool(habit["completed"]),
            }
            for habit in habits
        ]

@app.post("/api/habits/{habit_id}/complete")
def complete_habit(habit_id: int):
    today = date.today().isoformat()
    try:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            habit = connection.execute(
                "SELECT is_active FROM habits WHERE id = ?", (habit_id,)
            ).fetchone()
            if habit is None:
                raise HTTPException(status_code=404, detail="Habit not found")
            if not habit["is_active"]:
                raise HTTPException(status_code=400, detail="Habit is inactive")

            cursor = connection.execute(
                "INSERT INTO habit_completions (habit_id, date, completed) "
                "VALUES (?, ?, 1)",
                (habit_id, today),
            )
            completion = connection.execute(
                "SELECT id, habit_id, date, completed, created_at "
                "FROM habit_completions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(completion)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Habit is already completed today",
        )


@app.get("/api/habits/{habit_id}/streak")
def get_habit_streak(habit_id: int):
    with database_connection(DATABASE_PATH) as connection:
        habit = connection.execute(
            "SELECT id FROM habits WHERE id = ?", (habit_id,)
        ).fetchone()
        if habit is None:
            raise HTTPException(status_code=404, detail="Habit not found")

        completion_dates = connection.execute(
            "SELECT date FROM habit_completions "
            "WHERE habit_id = ? AND completed = 1",
            (habit_id,),
        ).fetchall()

    current_streak = calculate_current_streak(
        [row[0] for row in completion_dates], date.today()
    )
    return {"habit_id": habit_id, "current_streak": current_streak}


@app.post("/api/daily-entries", response_model=DailyEntryResponse)
def create_daily_entry(entry: DailyEntryCreate):
    try:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                "INSERT INTO daily_entries (date, deep_work_minutes) "
                "VALUES (?, ?)",
                (entry.date.isoformat(), entry.deep_work_minutes),
            )
            created_entry = connection.execute(
                "SELECT id, date, deep_work_minutes, created_at "
                "FROM daily_entries WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(created_entry)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A daily entry already exists for this date",
        )


@app.get("/api/daily-entries/{date}", response_model=DailyEntryResponse)
def get_daily_entry(date: date):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        entry = connection.execute(
            "SELECT id, date, deep_work_minutes, created_at "
            "FROM daily_entries WHERE date = ?",
            (date.isoformat(),),
        ).fetchone()
        if entry is None:
            raise HTTPException(status_code=404, detail="Daily entry not found")
        return dict(entry)


@app.get("/api/daily-score/{date}")
def get_daily_score(date: date):
    with database_connection(DATABASE_PATH) as connection:
        return calculate_daily_score(connection, date)


@app.get("/api/sprint-history")
def get_sprint_history():
    history = []
    current_day = SPRINT_START

    with database_connection(DATABASE_PATH) as connection:
        while current_day <= SPRINT_END:
            daily_score = calculate_daily_score(connection, current_day)
            history.append(
                {
                    "date": current_day.isoformat(),
                    "score": daily_score["score"],
                    "deep_work_minutes": get_deep_work_minutes(connection, current_day),
                    "technical_completed": daily_score["technical_completed"],
                    "placement_completed": daily_score["placement_completed"],
                    "successful": daily_score["score"] >= PLACEMENT_THRESHOLD,
                }
            )
            current_day += timedelta(days=1)

    return history

@app.get("/api/analytics")
def get_analytics():
    today = date.today()
    last_day = min(today, SPRINT_END)
    if today < SPRINT_START:
        return {
            "average_score": 0,
            "average_deep_work_minutes": 0,
            "habit_completion_rate": 0,
            "successful_days": 0,
            "best_streak": 0,
        }

    elapsed_days = (last_day - SPRINT_START).days + 1
    total_score = 0
    total_deep_work_minutes = 0
    successful_days = 0
    current_streak = 0
    best_streak = 0

    with database_connection(DATABASE_PATH) as connection:
        active_habits = connection.execute(
            "SELECT COUNT(*) FROM habits WHERE is_active = 1"
        ).fetchone()[0]
        completed_habit_records = connection.execute(
            "SELECT COUNT(*) FROM habit_completions AS completion "
            "JOIN habits AS habit ON habit.id = completion.habit_id "
            "WHERE completion.date BETWEEN ? AND ? "
            "AND completion.completed = 1 AND habit.is_active = 1",
            (SPRINT_START.isoformat(), last_day.isoformat()),
        ).fetchone()[0]

        current_day = SPRINT_START
        while current_day <= last_day:
            daily_score = calculate_daily_score(connection, current_day)
            total_score += daily_score["score"]
            total_deep_work_minutes += get_deep_work_minutes(connection, current_day)

            if daily_score["score"] >= PLACEMENT_THRESHOLD:
                successful_days += 1
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 0
            current_day += timedelta(days=1)

    possible_completions = active_habits * elapsed_days
    return {
        "average_score": int(round(total_score / elapsed_days)),
        "average_deep_work_minutes": int(round(total_deep_work_minutes / elapsed_days)),
        "habit_completion_rate": int(
            round(completed_habit_records / possible_completions * 100)
        ) if possible_completions else 0,
        "successful_days": successful_days,
        "best_streak": best_streak,
    }

@app.get("/api/placement-streak")
def get_placement_streak():
    today = date.today()
    scores_by_date = {}
    last_sprint_day = min(today, SPRINT_END)

    if today >= SPRINT_START:
        with database_connection(DATABASE_PATH) as connection:
            current_day = SPRINT_START
            while current_day <= last_sprint_day:
                daily_score = calculate_daily_score(connection, current_day)
                scores_by_date[current_day.isoformat()] = daily_score["score"]
                current_day += timedelta(days=1)

    current_streak = calculate_placement_streak(scores_by_date, today)
    return {
        "sprint_start": SPRINT_START.isoformat(),
        "sprint_end": SPRINT_END.isoformat(),
        "threshold": PLACEMENT_THRESHOLD,
        "current_streak": current_streak,
    }


@app.post("/api/mits", response_model=MITResponse)
def create_mit(mit: MITCreate):
    mit_date = mit.date.isoformat()
    try:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            duplicate = connection.execute(
                "SELECT id FROM daily_mits WHERE date = ? AND task = ?",
                (mit_date, mit.task),
            ).fetchone()
            if duplicate is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This MIT already exists for the date",
                )

            count = connection.execute(
                "SELECT COUNT(*) FROM daily_mits WHERE date = ?",
                (mit_date,),
            ).fetchone()[0]
            if count >= 3:
                raise HTTPException(
                    status_code=400,
                    detail="A maximum of 3 MITs is allowed per day",
                )

            cursor = connection.execute(
                "INSERT INTO daily_mits (date, task, completed) VALUES (?, ?, 0)",
                (mit_date, mit.task),
            )
            created_mit = connection.execute(
                "SELECT id, date, task, completed, created_at "
                "FROM daily_mits WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(created_mit)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="This MIT already exists for the date",
        )


@app.get("/api/mits/{date}", response_model=list[MITResponse])
def get_mits(date: date):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        mits = connection.execute(
            "SELECT id, date, task, completed, created_at "
            "FROM daily_mits WHERE date = ? ORDER BY id",
            (date.isoformat(),),
        ).fetchall()
        return [dict(mit) for mit in mits]

@app.post("/api/reflections", response_model=ReflectionResponse)
def create_reflection(reflection: ReflectionCreate):
    reflection_date = reflection.date.isoformat()
    try:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                "INSERT INTO daily_reflections "
                "(date, went_well, challenges, improvement) "
                "VALUES (?, ?, ?, ?)",
                (
                    reflection_date,
                    reflection.went_well,
                    reflection.challenges,
                    reflection.improvement,
                ),
            )
            created_reflection = connection.execute(
                "SELECT id, date, went_well, challenges, improvement, created_at "
                "FROM daily_reflections WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(created_reflection)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A reflection already exists for this date",
        )


@app.get("/api/reflections/{date}", response_model=ReflectionResponse)
def get_reflection(date: date):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        reflection = connection.execute(
            "SELECT id, date, went_well, challenges, improvement, created_at "
            "FROM daily_reflections WHERE date = ?",
            (date.isoformat(),),
        ).fetchone()
        if reflection is None:
            raise HTTPException(status_code=404, detail="Reflection not found")
        return dict(reflection)


OPPORTUNITY_SELECT = (
    "id, company, role, location, source, job_link, status, priority, ctc, "
    "deadline, referral, eligibility, requirements, notes, is_serious, "
    "created_at, updated_at"
)


@app.post("/api/opportunities", response_model=OpportunityResponse)
def create_opportunity(opportunity: OpportunityCreate):
    values = opportunity.model_dump()
    values["deadline"] = values["deadline"].isoformat() if values["deadline"] else None
    values["is_serious"] = int(values["is_serious"])
    fields = (
        "company, role, location, source, job_link, status, priority, ctc, "
        "deadline, referral, eligibility, requirements, notes, is_serious"
    )
    placeholders = ", ".join("?" for _ in range(14))

    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            f"INSERT INTO opportunities ({fields}) VALUES ({placeholders})",
            tuple(values[field] for field in fields.split(", ")),
        )
        created = connection.execute(
            f"SELECT {OPPORTUNITY_SELECT} FROM opportunities WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(created)


@app.get("/api/opportunities", response_model=list[OpportunityResponse])
def get_opportunities(
    serious: bool | None = None,
    status: OpportunityStatus | None = None,
):
    conditions = []
    parameters = []
    if serious is not None:
        conditions.append("is_serious = ?")
        parameters.append(int(serious))
    if status is not None:
        conditions.append("status = ?")
        parameters.append(status)

    query = f"SELECT {OPPORTUNITY_SELECT} FROM opportunities"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"

    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        opportunities = connection.execute(query, parameters).fetchall()
        return [dict(opportunity) for opportunity in opportunities]


@app.get("/api/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(opportunity_id: int):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        opportunity = connection.execute(
            f"SELECT {OPPORTUNITY_SELECT} FROM opportunities WHERE id = ?",
            (opportunity_id,),
        ).fetchone()
        if opportunity is None:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        return dict(opportunity)


@app.put("/api/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(opportunity_id: int, changes: OpportunityUpdate):
    updates = changes.model_dump(exclude_unset=True)
    if "deadline" in updates and updates["deadline"] is not None:
        updates["deadline"] = updates["deadline"].isoformat()
    if "is_serious" in updates:
        updates["is_serious"] = int(updates["is_serious"])

    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        if updates:
            assignments = [f"{field} = ?" for field in updates]
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            cursor = connection.execute(
                "UPDATE opportunities SET " + ", ".join(assignments)
                + " WHERE id = ?",
                (*updates.values(), opportunity_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Opportunity not found")
        else:
            exists = connection.execute(
                "SELECT 1 FROM opportunities WHERE id = ?", (opportunity_id,)
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="Opportunity not found")

        updated = connection.execute(
            f"SELECT {OPPORTUNITY_SELECT} FROM opportunities WHERE id = ?",
            (opportunity_id,),
        ).fetchone()
        return dict(updated)


@app.delete("/api/opportunities/{opportunity_id}", status_code=204)
def delete_opportunity(opportunity_id: int):
    with database_connection(DATABASE_PATH) as connection:
        cursor = connection.execute(
            "DELETE FROM opportunities WHERE id = ?", (opportunity_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Opportunity not found")


PREPARATION_TOPIC_SELECT = (
    "id, category_id, name, status, practice_count, notes, created_at, updated_at"
)


@app.post(
    "/api/preparation/categories",
    response_model=PreparationCategoryResponse,
)
def create_preparation_category(category: PreparationCategoryCreate):
    try:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                "INSERT INTO preparation_categories (name) VALUES (?)",
                (category.name,),
            )
            created = connection.execute(
                "SELECT id, name, created_at FROM preparation_categories WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(created)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409, detail="A preparation category with this name already exists"
        )


@app.get(
    "/api/preparation/categories",
    response_model=list[PreparationCategoryResponse],
)
def get_preparation_categories():
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        categories = connection.execute(
            "SELECT id, name, created_at FROM preparation_categories ORDER BY id"
        ).fetchall()
        return [dict(category) for category in categories]


@app.put(
    "/api/preparation/categories/{category_id}",
    response_model=PreparationCategoryResponse,
)
def update_preparation_category(
    category_id: int, changes: PreparationCategoryUpdate
):
    if "name" not in changes.model_fields_set:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            category = connection.execute(
                "SELECT id, name, created_at FROM preparation_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            if category is None:
                raise HTTPException(status_code=404, detail="Category not found")
            return dict(category)

    try:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                "UPDATE preparation_categories SET name = ? WHERE id = ?",
                (changes.name, category_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Category not found")
            updated = connection.execute(
                "SELECT id, name, created_at FROM preparation_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            return dict(updated)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409, detail="A preparation category with this name already exists"
        )

@app.delete("/api/preparation/categories/{category_id}", status_code=204)
def delete_preparation_category(category_id: int):
    with database_connection(DATABASE_PATH) as connection:
        exists = connection.execute(
            "SELECT 1 FROM preparation_categories WHERE id = ?", (category_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Category not found")

        topic_count = connection.execute(
            "SELECT COUNT(*) FROM preparation_topics WHERE category_id = ?",
            (category_id,),
        ).fetchone()[0]
        if topic_count:
            raise HTTPException(
                status_code=409,
                detail="Delete or move this category's topics before deleting it",
            )
        connection.execute(
            "DELETE FROM preparation_categories WHERE id = ?", (category_id,)
        )


@app.post(
    "/api/preparation/topics",
    response_model=PreparationTopicResponse,
)
def create_preparation_topic(topic: PreparationTopicCreate):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        category = connection.execute(
            "SELECT 1 FROM preparation_categories WHERE id = ?",
            (topic.category_id,),
        ).fetchone()
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")

        cursor = connection.execute(
            "INSERT INTO preparation_topics "
            "(category_id, name, status, practice_count, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                topic.category_id,
                topic.name,
                topic.status,
                topic.practice_count,
                topic.notes,
            ),
        )
        created = connection.execute(
            f"SELECT {PREPARATION_TOPIC_SELECT} FROM preparation_topics WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(created)


@app.get(
    "/api/preparation/topics",
    response_model=list[PreparationTopicResponse],
)
def get_preparation_topics(
    category_id: int | None = None,
    status: PreparationTopicStatus | None = None,
):
    conditions = []
    parameters = []
    if category_id is not None:
        conditions.append("category_id = ?")
        parameters.append(category_id)
    if status is not None:
        conditions.append("status = ?")
        parameters.append(status)

    query = f"SELECT {PREPARATION_TOPIC_SELECT} FROM preparation_topics"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY category_id, id"

    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        topics = connection.execute(query, parameters).fetchall()
        return [dict(topic) for topic in topics]


@app.get(
    "/api/preparation/topics/{topic_id}",
    response_model=PreparationTopicResponse,
)
def get_preparation_topic(topic_id: int):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        topic = connection.execute(
            f"SELECT {PREPARATION_TOPIC_SELECT} FROM preparation_topics WHERE id = ?",
            (topic_id,),
        ).fetchone()
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
        return dict(topic)


@app.put(
    "/api/preparation/topics/{topic_id}",
    response_model=PreparationTopicResponse,
)
def update_preparation_topic(topic_id: int, changes: PreparationTopicUpdate):
    updates = changes.model_dump(exclude_unset=True)
    if "notes" in updates and updates["notes"] is None:
        updates["notes"] = ""
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        if "category_id" in updates:
            category = connection.execute(
                "SELECT 1 FROM preparation_categories WHERE id = ?",
                (updates["category_id"],),
            ).fetchone()
            if category is None:
                raise HTTPException(status_code=404, detail="Category not found")

        if updates:
            assignments = [f"{field} = ?" for field in updates]
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            cursor = connection.execute(
                "UPDATE preparation_topics SET " + ", ".join(assignments)
                + " WHERE id = ?",
                (*updates.values(), topic_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Topic not found")
        else:
            exists = connection.execute(
                "SELECT 1 FROM preparation_topics WHERE id = ?", (topic_id,)
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="Topic not found")

        updated = connection.execute(
            f"SELECT {PREPARATION_TOPIC_SELECT} FROM preparation_topics WHERE id = ?",
            (topic_id,),
        ).fetchone()
        return dict(updated)


@app.delete("/api/preparation/topics/{topic_id}", status_code=204)
def delete_preparation_topic(topic_id: int):
    with database_connection(DATABASE_PATH) as connection:
        cursor = connection.execute(
            "DELETE FROM preparation_topics WHERE id = ?", (topic_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Topic not found")


@app.post(
    "/api/preparation/topics/{topic_id}/practice",
    response_model=PreparationTopicResponse,
)
def practice_preparation_topic(topic_id: int):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            "UPDATE preparation_topics "
            "SET practice_count = practice_count + 1, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (topic_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Topic not found")
        topic = connection.execute(
            f"SELECT {PREPARATION_TOPIC_SELECT} FROM preparation_topics WHERE id = ?",
            (topic_id,),
        ).fetchone()
        return dict(topic)


DEEP_WORK_SESSION_SELECT = (
    "id, date, duration_minutes, category, notes, started_at, ended_at, source, created_at"
)


def _deep_work_session_dict(row: sqlite3.Row) -> dict:
    return dict(row)


@app.post("/api/deep-work/sessions", response_model=DeepWorkSessionResponse, status_code=201)
def create_deep_work_session(session: DeepWorkSessionCreate):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            "INSERT INTO deep_work_sessions "
            "(date, duration_minutes, category, notes, source) VALUES (?, ?, ?, ?, 'manual')",
            (session.date.isoformat(), session.duration_minutes, session.category, session.notes),
        )
        created = connection.execute(
            f"SELECT {DEEP_WORK_SESSION_SELECT} FROM deep_work_sessions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return _deep_work_session_dict(created)


@app.get("/api/deep-work/sessions", response_model=list[DeepWorkSessionResponse])
def get_deep_work_sessions(date: date | None = None, category: DeepWorkCategory | None = None):
    conditions = []
    parameters = []
    if date is not None:
        conditions.append("date = ?")
        parameters.append(date.isoformat())
    if category is not None:
        conditions.append("category = ?")
        parameters.append(category)
    query = f"SELECT {DEEP_WORK_SESSION_SELECT} FROM deep_work_sessions"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY date, id"
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [_deep_work_session_dict(row) for row in connection.execute(query, parameters).fetchall()]


@app.get("/api/deep-work/sessions/{session_id}", response_model=DeepWorkSessionResponse)
def get_deep_work_session(session_id: int):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        session = connection.execute(
            f"SELECT {DEEP_WORK_SESSION_SELECT} FROM deep_work_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session is None:
            raise HTTPException(status_code=404, detail="Deep work session not found")
        return _deep_work_session_dict(session)


@app.delete("/api/deep-work/sessions/{session_id}", status_code=204)
def delete_deep_work_session(session_id: int):
    with database_connection(DATABASE_PATH) as connection:
        cursor = connection.execute("DELETE FROM deep_work_sessions WHERE id = ?", (session_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Deep work session not found")


@app.get("/api/deep-work/daily/{requested_date}", response_model=DailyDeepWorkSummary)
def get_daily_deep_work_summary(requested_date: date):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT {DEEP_WORK_SESSION_SELECT} FROM deep_work_sessions WHERE date = ? ORDER BY id",
            (requested_date.isoformat(),),
        ).fetchall()
    sessions = [_deep_work_session_dict(row) for row in rows]
    total = sum(session["duration_minutes"] for session in sessions)
    return {
        "date": requested_date.isoformat(),
        "total_minutes": total,
        "target_minutes": DEEP_WORK_TARGET_MINUTES,
        "progress_percentage": min(total / DEEP_WORK_TARGET_MINUTES, 1) * 100,
        "sessions": sessions,
    }


@app.post("/api/deep-work/timer/start", response_model=DeepWorkTimerResponse, status_code=201)
def start_deep_work_timer(timer: DeepWorkTimerStart):
    started_at = current_local_datetime().isoformat(timespec="seconds")
    try:
        with database_connection(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute(
                "INSERT INTO deep_work_active_timer (id, category, notes, started_at) "
                "VALUES (1, ?, ?, ?)",
                (timer.category, timer.notes, started_at),
            )
            return dict(connection.execute(
                "SELECT id, category, notes, started_at, source "
                "FROM deep_work_active_timer WHERE id = 1"
            ).fetchone())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A deep work timer is already active")


@app.get("/api/deep-work/timer", response_model=DeepWorkTimerResponse | None)
def get_deep_work_timer():
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        timer = connection.execute(
            "SELECT id, category, notes, started_at, source "
            "FROM deep_work_active_timer WHERE id = 1"
        ).fetchone()
        return dict(timer) if timer else None


@app.post("/api/deep-work/timer/stop", response_model=DeepWorkTimerStopResponse)
def stop_deep_work_timer():
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        timer = connection.execute(
            "SELECT id, category, notes, started_at FROM deep_work_active_timer WHERE id = 1"
        ).fetchone()
        if timer is None:
            raise HTTPException(status_code=409, detail="No deep work timer is active")
        try:
            started_at = datetime.fromisoformat(timer["started_at"])
            if started_at.tzinfo is None:
                raise ValueError("Timer timestamp has no timezone")
            elapsed_seconds = current_local_datetime().timestamp() - started_at.timestamp()
            if elapsed_seconds < 0:
                raise ValueError("Timer start is in the future")
        except (TypeError, ValueError):
            connection.execute("DELETE FROM deep_work_active_timer WHERE id = 1")
            return {
                "completed": False,
                "duration_minutes": 0,
                "message": "The saved timer timestamp was invalid; the timer was cleared.",
                "session": None,
            }

        duration_minutes = int(elapsed_seconds // 60)
        if duration_minutes < MIN_DEEP_WORK_SESSION_MINUTES:
            connection.execute("DELETE FROM deep_work_active_timer WHERE id = 1")
            return {
                "completed": False,
                "duration_minutes": duration_minutes,
                "message": "Session was under 30 minutes and was not saved.",
                "session": None,
            }

        ended_at = current_local_datetime().isoformat(timespec="seconds")
        cursor = connection.execute(
            "INSERT INTO deep_work_sessions "
            "(date, duration_minutes, category, notes, started_at, ended_at, source) "
            "VALUES (?, ?, ?, ?, ?, ?, 'timer')",
            (started_at.date().isoformat(), duration_minutes, timer["category"], timer["notes"],
             timer["started_at"], ended_at),
        )
        session = connection.execute(
            f"SELECT {DEEP_WORK_SESSION_SELECT} FROM deep_work_sessions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        connection.execute("DELETE FROM deep_work_active_timer WHERE id = 1")
        return {
            "completed": True,
            "duration_minutes": duration_minutes,
            "message": "Deep work session saved.",
            "session": _deep_work_session_dict(session),
        }


def read_dashboard_settings(connection: sqlite3.Connection) -> dict:
    settings = dict(connection.execute(
        "SELECT key, value FROM app_settings "
        "WHERE key IN ('placement_goal', 'daily_deep_work_target_minutes')"
    ).fetchall())
    goal = settings.get("placement_goal", DASHBOARD_SETTING_DEFAULTS["placement_goal"])
    try:
        target_minutes = int(settings.get("daily_deep_work_target_minutes", DASHBOARD_SETTING_DEFAULTS["daily_deep_work_target_minutes"]))
    except (TypeError, ValueError):
        target_minutes = DEEP_WORK_TARGET_MINUTES
    return {
        "goal": goal,
        "daily_deep_work_target_minutes": target_minutes,
    }


@app.get("/api/dashboard/settings", response_model=DashboardSettingsResponse)
def get_dashboard_settings():
    with database_connection(DATABASE_PATH) as connection:
        return read_dashboard_settings(connection)


@app.put("/api/dashboard/settings", response_model=DashboardSettingsResponse)
def update_dashboard_settings(changes: DashboardSettingsUpdate):
    updates = changes.model_dump(exclude_unset=True)
    with database_connection(DATABASE_PATH) as connection:
        for key, value in updates.items():
            stored_key = "placement_goal" if key == "goal" else key
            connection.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (stored_key, str(value)),
            )
        return read_dashboard_settings(connection)


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard():
    today = date.today()
    today_text = today.isoformat()
    week_start = today - timedelta(days=today.weekday())
    active_status_placeholders = ", ".join("?" for _ in ACTIVE_APPLICATION_STATUSES)
    pipeline_counts = {status: 0 for status in PLACEMENT_PIPELINE_STATUSES}

    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        settings = read_dashboard_settings(connection)
        active_applications = connection.execute(
            "SELECT COUNT(*) FROM opportunities WHERE is_serious = 1 "
            f"AND status IN ({active_status_placeholders})",
            ACTIVE_APPLICATION_STATUSES,
        ).fetchone()[0]
        for row in connection.execute(
            "SELECT status, COUNT(*) AS total FROM opportunities "
            "WHERE is_serious = 1 GROUP BY status"
        ).fetchall():
            pipeline_counts[row["status"]] = row["total"]

        deadline = connection.execute(
            "SELECT id, company, role, deadline FROM opportunities "
            f"WHERE deadline IS NOT NULL AND deadline >= ? AND status IN ({active_status_placeholders}) "
            "ORDER BY deadline, id LIMIT 1",
            (today_text, *ACTIVE_APPLICATION_STATUSES),
        ).fetchone()

        topic_totals = connection.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed, "
            "SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress, "
            "SUM(CASE WHEN status = 'Not Started' THEN 1 ELSE 0 END) AS not_started, "
            "COALESCE(SUM(practice_count), 0) AS practice_count "
            "FROM preparation_topics"
        ).fetchone()
        category_rows = connection.execute(
            "SELECT category.id, category.name, COUNT(topic.id) AS total_topics, "
            "SUM(CASE WHEN topic.status = 'Completed' THEN 1 ELSE 0 END) AS completed_topics "
            "FROM preparation_categories AS category "
            "LEFT JOIN preparation_topics AS topic ON topic.category_id = category.id "
            "GROUP BY category.id, category.name ORDER BY category.name"
        ).fetchall()
        categories = [
            {
                "category_id": row["id"],
                "category": row["name"],
                "total_topics": row["total_topics"],
                "completed_topics": row["completed_topics"] or 0,
                "completion_percentage": round(
                    (row["completed_topics"] or 0) / row["total_topics"] * 100, 1
                ) if row["total_topics"] else 0,
            }
            for row in category_rows
        ]
        total_topics = topic_totals["total"] or 0
        completed_topics = topic_totals["completed"] or 0
        preparation = {
            "total_topics": total_topics,
            "completed": completed_topics,
            "in_progress": topic_totals["in_progress"] or 0,
            "not_started": topic_totals["not_started"] or 0,
            "completion_percentage": round(completed_topics / total_topics * 100, 1) if total_topics else 0,
            "total_practice_count": topic_totals["practice_count"],
            "categories": categories,
        }

        target_minutes = settings["daily_deep_work_target_minutes"]
        daily_actual = connection.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM deep_work_sessions WHERE date = ?",
            (today_text,),
        ).fetchone()[0]
        weekly_actual = connection.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM deep_work_sessions "
            "WHERE date BETWEEN ? AND ?",
            (week_start.isoformat(), today_text),
        ).fetchone()[0]
        deep_work = {
            "daily": {
                "target_minutes": target_minutes,
                "actual_minutes": daily_actual,
                "progress_percentage": round(daily_actual / target_minutes * 100, 1),
            },
            "weekly": {
                "target_minutes": target_minutes * 7,
                "actual_minutes": weekly_actual,
                "progress_percentage": round(weekly_actual / (target_minutes * 7) * 100, 1),
            },
        }

        mits = [dict(row) for row in connection.execute(
            "SELECT id, date, task, completed, created_at FROM daily_mits "
            "WHERE date = ? ORDER BY id",
            (today_text,),
        ).fetchall()]
        incomplete_topics = [dict(row) for row in connection.execute(
            "SELECT topic.id, topic.category_id, category.name AS category, topic.name, "
            "topic.status, topic.practice_count, topic.notes "
            "FROM preparation_topics AS topic "
            "JOIN preparation_categories AS category ON category.id = topic.category_id "
            "WHERE topic.status != 'Completed' ORDER BY category.name, topic.name"
        ).fetchall()]

    return {
        "goal": settings["goal"],
        "applications": {"active": active_applications, "pipeline": pipeline_counts},
        "next_deadline": dict(deadline) if deadline else None,
        "preparation": preparation,
        "deep_work": deep_work,
        "today": {"mits": mits, "incomplete_topics": incomplete_topics},
    }

PERFORMANCE_ENTRY_SELECT = (
    "entry.id, COALESCE(opportunity.company, entry.company) AS company, "
    "COALESCE(opportunity.role, entry.role) AS role, entry.date, entry.type, "
    "entry.performance, entry.opportunity_id, entry.preparation_topic_id, "
    "topic.name AS preparation_topic_name, category.name AS preparation_category, "
    "entry.questions, entry.couldnt_answer, entry.what_learned, "
    "entry.action_items, entry.notes, entry.created_at, entry.updated_at"
)
PERFORMANCE_ENTRY_FROM = (
    "performance_entries AS entry "
    "LEFT JOIN opportunities AS opportunity ON opportunity.id = entry.opportunity_id "
    "LEFT JOIN preparation_topics AS topic ON topic.id = entry.preparation_topic_id "
    "LEFT JOIN preparation_categories AS category ON category.id = topic.category_id"
)
PERFORMANCE_TYPES = ("Assessment", "Coding Test", "Technical Interview", "HR Interview", "Mock Interview")
PERFORMANCE_LEVELS = ("Good", "Mixed", "Poor")


def _get_performance_entry(connection: sqlite3.Connection, entry_id: int):
    return connection.execute(
        f"SELECT {PERFORMANCE_ENTRY_SELECT} FROM {PERFORMANCE_ENTRY_FROM} WHERE entry.id = ?",
        (entry_id,),
    ).fetchone()


def _validate_performance_references(connection: sqlite3.Connection, values: dict) -> None:
    opportunity_id = values.get("opportunity_id")
    if opportunity_id is not None and connection.execute(
        "SELECT 1 FROM opportunities WHERE id = ?", (opportunity_id,)
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    topic_id = values.get("preparation_topic_id")
    if topic_id is not None and connection.execute(
        "SELECT 1 FROM preparation_topics WHERE id = ?", (topic_id,)
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail="Preparation topic not found")


@app.post("/api/performance", response_model=PerformanceEntryResponse, status_code=201)
def create_performance_entry(entry: PerformanceEntryCreate):
    values = entry.model_dump()
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        _validate_performance_references(connection, values)
        cursor = connection.execute(
            "INSERT INTO performance_entries "
            "(company, role, date, type, performance, opportunity_id, preparation_topic_id, "
            "questions, couldnt_answer, what_learned, action_items, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (values["company"], values["role"], values["date"].isoformat(), values["type"],
             values["performance"], values["opportunity_id"], values["preparation_topic_id"],
             values["questions"], values["couldnt_answer"], values["what_learned"],
             values["action_items"], values["notes"]),
        )
        return dict(_get_performance_entry(connection, cursor.lastrowid))


@app.get("/api/performance/summary", response_model=PerformanceSummaryResponse)
def get_performance_summary():
    today = date.today()
    recent_start = (today - timedelta(days=29)).isoformat()
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        total = connection.execute("SELECT COUNT(*) FROM performance_entries").fetchone()[0]
        type_counts = {value: 0 for value in PERFORMANCE_TYPES}
        for row in connection.execute(
            "SELECT type, COUNT(*) AS count FROM performance_entries GROUP BY type"
        ).fetchall():
            type_counts[row["type"]] = row["count"]
        performance_counts = {value: 0 for value in PERFORMANCE_LEVELS}
        for row in connection.execute(
            "SELECT performance, COUNT(*) AS count FROM performance_entries GROUP BY performance"
        ).fetchall():
            performance_counts[row["performance"]] = row["count"]
        recent = connection.execute(
            "SELECT COUNT(*) FROM performance_entries WHERE date BETWEEN ? AND ?",
            (recent_start, today.isoformat()),
        ).fetchone()[0]
    return {
        "total": total,
        "by_type": type_counts,
        "by_performance": performance_counts,
        "recent_entries": recent,
    }


@app.get("/api/performance", response_model=list[PerformanceEntryResponse])
def list_performance_entries(
    type: PerformanceType | None = None,
    performance: PerformanceLevel | None = None,
    company: str | None = None,
    opportunity_id: Annotated[int | None, Query(ge=1)] = None,
    date: date | None = None,
):
    conditions = []
    parameters = []
    for column, value in (("entry.type", type), ("entry.performance", performance),
                          ("entry.opportunity_id", opportunity_id)):
        if value is not None:
            conditions.append(f"{column} = ?")
            parameters.append(value)
    if company is not None:
        conditions.append("LOWER(COALESCE(opportunity.company, entry.company, '')) = LOWER(?)")
        parameters.append(company.strip())
    if date is not None:
        conditions.append("entry.date = ?")
        parameters.append(date.isoformat())
    query = f"SELECT {PERFORMANCE_ENTRY_SELECT} FROM {PERFORMANCE_ENTRY_FROM}"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY entry.date DESC, entry.created_at DESC, entry.id DESC"
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]


@app.get("/api/performance/{entry_id}", response_model=PerformanceEntryResponse)
def get_performance_entry(entry_id: int):
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        entry = _get_performance_entry(connection, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Performance entry not found")
        return dict(entry)


@app.put("/api/performance/{entry_id}", response_model=PerformanceEntryResponse)
def update_performance_entry(entry_id: int, changes: PerformanceEntryUpdate):
    updates = changes.model_dump(exclude_unset=True)
    for field in ("date", "type", "performance", "company", "role", "opportunity_id",
                  "preparation_topic_id", "questions", "couldnt_answer", "what_learned",
                  "action_items", "notes"):
        if field in updates and isinstance(updates[field], date):
            updates[field] = updates[field].isoformat()
    with database_connection(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        current = connection.execute(
            "SELECT opportunity_id FROM performance_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="Performance entry not found")
        if "opportunity_id" in updates and updates["opportunity_id"] is not None:
            if "company" in updates or "role" in updates:
                raise HTTPException(status_code=422, detail="Company and role are read from the linked opportunity")
        elif current["opportunity_id"] is not None and (
            ("company" in updates or "role" in updates) and "opportunity_id" not in updates
        ):
            raise HTTPException(status_code=422, detail="Clear opportunity_id before setting company or role")
        _validate_performance_references(connection, updates)
        if "questions" in updates and updates["questions"] is None:
            updates["questions"] = ""
        if "couldnt_answer" in updates and updates["couldnt_answer"] is None:
            updates["couldnt_answer"] = ""
        if "what_learned" in updates and updates["what_learned"] is None:
            updates["what_learned"] = ""
        if "action_items" in updates and updates["action_items"] is None:
            updates["action_items"] = ""
        if "notes" in updates and updates["notes"] is None:
            updates["notes"] = ""
        assignments = [f"{field} = ?" for field in updates]
        values = list(updates.values())
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        connection.execute(
            "UPDATE performance_entries SET " + ", ".join(assignments) + " WHERE id = ?",
            (*values, entry_id),
        )
        return dict(_get_performance_entry(connection, entry_id))


@app.delete("/api/performance/{entry_id}", status_code=204)
def delete_performance_entry(entry_id: int):
    with database_connection(DATABASE_PATH) as connection:
        cursor = connection.execute("DELETE FROM performance_entries WHERE id = ?", (entry_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Performance entry not found")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")
