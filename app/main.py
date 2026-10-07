import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.database import DATABASE_PATH, initialize_database
from app.schemas import (
    DailyEntryCreate,
    DailyEntryResponse,
    HabitCreate,
    HabitResponse,
    MITCreate,
    MITResponse,
    ReflectionCreate,
    ReflectionResponse,
)

app = FastAPI()
STATIC_DIR = Path(__file__).resolve().parent.parent / 'static'
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

SPRINT_START = date(2026, 10, 6)
SPRINT_END = date(2026, 11, 5)
PLACEMENT_THRESHOLD = 60


@app.on_event("startup")
def startup_event():
    initialize_database()


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
    daily_entry = connection.execute(
        "SELECT deep_work_minutes FROM daily_entries WHERE date = ?",
        (date_string,),
    ).fetchone()
    deep_work_minutes = daily_entry[0] if daily_entry else 0

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

    deep_work_points = min(deep_work_minutes / 180, 1) * 40
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
    with sqlite3.connect(DATABASE_PATH) as connection:
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
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        habits = connection.execute(
            "SELECT id, name, category, description, is_active, created_at "
            "FROM habits ORDER BY id"
        ).fetchall()
        return [dict(habit) for habit in habits]


@app.get("/api/habits/today")
def get_today_habits():
    today = date.today().isoformat()
    with sqlite3.connect(DATABASE_PATH) as connection:
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
        with sqlite3.connect(DATABASE_PATH) as connection:
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
    with sqlite3.connect(DATABASE_PATH) as connection:
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
        with sqlite3.connect(DATABASE_PATH) as connection:
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
    with sqlite3.connect(DATABASE_PATH) as connection:
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
    with sqlite3.connect(DATABASE_PATH) as connection:
        return calculate_daily_score(connection, date)


@app.get("/api/sprint-history")
def get_sprint_history():
    history = []
    current_day = SPRINT_START

    with sqlite3.connect(DATABASE_PATH) as connection:
        while current_day <= SPRINT_END:
            daily_score = calculate_daily_score(connection, current_day)
            daily_entry = connection.execute(
                "SELECT deep_work_minutes FROM daily_entries WHERE date = ?",
                (current_day.isoformat(),),
            ).fetchone()
            history.append(
                {
                    "date": current_day.isoformat(),
                    "score": daily_score["score"],
                    "deep_work_minutes": daily_entry[0] if daily_entry else 0,
                    "technical_completed": daily_score["technical_completed"],
                    "placement_completed": daily_score["placement_completed"],
                    "successful": daily_score["score"] >= PLACEMENT_THRESHOLD,
                }
            )
            current_day += timedelta(days=1)

    return history

@app.get("/api/placement-streak")
def get_placement_streak():
    today = date.today()
    scores_by_date = {}
    last_sprint_day = min(today, SPRINT_END)

    if today >= SPRINT_START:
        with sqlite3.connect(DATABASE_PATH) as connection:
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
        with sqlite3.connect(DATABASE_PATH) as connection:
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
    with sqlite3.connect(DATABASE_PATH) as connection:
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
        with sqlite3.connect(DATABASE_PATH) as connection:
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
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        reflection = connection.execute(
            "SELECT id, date, went_well, challenges, improvement, created_at "
            "FROM daily_reflections WHERE date = ?",
            (date.isoformat(),),
        ).fetchone()
        if reflection is None:
            raise HTTPException(status_code=404, detail="Reflection not found")
        return dict(reflection)

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")
