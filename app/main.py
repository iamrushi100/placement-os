import sqlite3
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException
from app.database import DATABASE_PATH, initialize_database
from app.schemas import HabitCreate, HabitResponse

app = FastAPI()


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


@app.get("/")
async def root():
    return {"message": "Placement Streak Tracker API is running"}
