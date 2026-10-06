import sqlite3

from fastapi import FastAPI
from app.database import DATABASE_PATH, initialize_database
from app.schemas import HabitCreate, HabitResponse

app = FastAPI()


@app.on_event("startup")
def startup_event():
    initialize_database()


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


@app.get("/")
async def root():
    return {"message": "Placement Streak Tracker API is running"}
