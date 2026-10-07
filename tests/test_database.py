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
    create_opportunity,
    delete_opportunity,
    get_opportunities,
    get_opportunity,
    update_opportunity,
)
from app.schemas import HabitCreate, OpportunityCreate, OpportunityResponse, OpportunityUpdate


EXPECTED_TABLES = {
    "habits",
    "habit_completions",
    "daily_entries",
    "daily_mits",
    "daily_reflections",
    "opportunities",
    "preparation_categories",
    "preparation_topics",
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



class OpportunityApiTests(unittest.TestCase):
    def test_opportunity_inbox_pipeline_filters_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunities.db"
            with patch("app.database.DATABASE_PATH", database_path):
                initialize_database()

            with patch("app.main.DATABASE_PATH", database_path):
                self.assertEqual(get_opportunities(), [])

                inbox_item = create_opportunity(
                    OpportunityCreate(
                        company="Example Labs",
                        role="Backend Engineer",
                        source="Company site",
                        deadline=date(2026, 11, 1),
                    )
                )
                response = OpportunityResponse.model_validate(inbox_item)
                self.assertEqual(response.status, "Interested")
                self.assertEqual(response.priority, "Medium")
                self.assertFalse(response.is_serious)
                self.assertEqual(get_opportunity(response.id)["company"], "Example Labs")
                self.assertEqual(len(get_opportunities()), 1)
                self.assertEqual(
                    len(get_opportunities(serious=False, status="Interested")), 1
                )

                promoted = update_opportunity(
                    response.id,
                    OpportunityUpdate(
                        is_serious=True,
                        status="Applied",
                        priority="High",
                        notes="Application submitted",
                    ),
                )
                self.assertTrue(promoted["is_serious"])
                self.assertEqual(promoted["status"], "Applied")
                self.assertEqual(len(get_opportunities(serious=True)), 1)
                self.assertEqual(len(get_opportunities(status="Applied")), 1)
                self.assertEqual(get_opportunities(serious=False), [])

                second = create_opportunity(
                    OpportunityCreate(company="Other Co", role="Analyst")
                )
                self.assertIsNone(delete_opportunity(second["id"]))
                self.assertEqual(len(get_opportunities()), 1)

                for operation in (
                    lambda: get_opportunity(9999),
                    lambda: update_opportunity(9999, OpportunityUpdate(notes="x")),
                    lambda: delete_opportunity(9999),
                ):
                    with self.assertRaises(HTTPException) as missing:
                        operation()
                    self.assertEqual(missing.exception.status_code, 404)

    def test_invalid_opportunity_fields_are_rejected(self):
        for payload in (
            {"company": "", "role": "Engineer"},
            {"company": "Example", "role": "  "},
            {"company": "Example", "role": "Engineer", "status": "Unknown"},
            {"company": "Example", "role": "Engineer", "priority": "Urgent"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    OpportunityCreate.model_validate(payload)

        for payload in ({"status": "Unknown"}, {"priority": "Urgent"}, {"company": None}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    OpportunityUpdate.model_validate(payload)

if __name__ == "__main__":
    unittest.main()