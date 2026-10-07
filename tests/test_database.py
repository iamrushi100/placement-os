import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.database import LATEST_SCHEMA_VERSION, initialize_database
from app.main import (
    complete_habit,
    create_habit,
    get_daily_score,
    get_habits,
    get_today_habits,
)
from app.schemas import HabitCreate


EXPECTED_TABLES = {
    "habits",
    "habit_completions",
    "daily_entries",
    "daily_mits",
    "daily_reflections",
}


@contextmanager
def database_connection(path):
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class DatabaseMigrationTests(unittest.TestCase):
    def test_migration_creates_existing_tables_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.db"
            with patch("app.database.DATABASE_PATH", database_path):
                initialize_database()

                with database_connection(database_path) as connection:
                    tables = {
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master "
                            "WHERE type = 'table'"
                        )
                    }
                    self.assertTrue(EXPECTED_TABLES.issubset(tables))
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        LATEST_SCHEMA_VERSION,
                    )
                    connection.execute(
                        "INSERT INTO habits (name, category) VALUES (?, ?)",
                        ("Test habit", "Technical"),
                    )

                initialize_database()

                with database_connection(database_path) as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT name FROM habits WHERE id = 1"
                        ).fetchone()[0],
                        "Test habit",
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        LATEST_SCHEMA_VERSION,
                    )

    def test_migration_preserves_existing_unversioned_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.db"
            with database_connection(database_path) as connection:
                connection.execute(
                    "CREATE TABLE habits ("
                    "id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                    "category TEXT NOT NULL, description TEXT, "
                    "is_active INTEGER NOT NULL DEFAULT 1, "
                    "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                connection.execute(
                    "INSERT INTO habits (name, category) VALUES (?, ?)",
                    ("Existing habit", "Technical"),
                )

            with patch("app.database.DATABASE_PATH", database_path):
                initialize_database()

            with database_connection(database_path) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM habits WHERE id = 1"
                    ).fetchone()[0],
                    "Existing habit",
                )
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertTrue(EXPECTED_TABLES.issubset(tables))

    def test_newer_schema_version_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "future.db"
            with database_connection(database_path) as connection:
                connection.execute(
                    f"PRAGMA user_version = {LATEST_SCHEMA_VERSION + 1}"
                )

            with patch("app.database.DATABASE_PATH", database_path):
                with self.assertRaisesRegex(RuntimeError, "newer than supported"):
                    initialize_database()

            with database_connection(database_path) as connection:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0],
                    LATEST_SCHEMA_VERSION + 1,
                )


class ExistingApiWorkflowTests(unittest.TestCase):
    def test_habit_completion_still_updates_today_status_and_score(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "api-test.db"
            with patch("app.database.DATABASE_PATH", database_path):
                initialize_database()

            with patch("app.main.DATABASE_PATH", database_path):
                self.assertEqual(get_habits(), [])
                habit = create_habit(
                    HabitCreate(
                        name="Test DSA",
                        category="Technical",
                        description="API smoke test",
                    )
                )
                self.assertEqual(habit["name"], "Test DSA")

                self.assertEqual(get_today_habits()[0]["completed"], False)
                completion = complete_habit(habit["id"])
                self.assertEqual(completion["completed"], 1)
                self.assertEqual(get_today_habits()[0]["completed"], True)
                self.assertEqual(get_daily_score(date.today())["score"], 6)

                with self.assertRaises(HTTPException) as duplicate:
                    complete_habit(habit["id"])
                self.assertEqual(duplicate.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()