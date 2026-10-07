import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app.database as database
from app.database import initialize_database
from app.main import (
    create_opportunity,
    create_habit,
    complete_habit,
    create_daily_entry,
    get_daily_entry,
    create_mit,
    get_mits,
    create_reflection,
    get_reflection,
    get_daily_score,
    get_placement_streak,
    get_dashboard,
    create_performance_entry,
    create_preparation_topic,
    delete_performance_entry,
    get_performance_entry,
    get_performance_summary,
    list_performance_entries,
    update_performance_entry,
    create_preparation_category,
)
from app.schemas import (
    OpportunityCreate,
    HabitCreate,
    DailyEntryCreate,
    MITCreate,
    ReflectionCreate,
    PerformanceEntryCreate,
    PerformanceEntryUpdate,
    PreparationCategoryCreate,
    PreparationTopicCreate,
)


class PerformanceJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.database_path = Path(self.temp_directory.name) / "performance.db"
        self.database_path_patch = patch("app.database.DATABASE_PATH", self.database_path)
        self.main_database_path_patch = patch("app.main.DATABASE_PATH", self.database_path)
        self.database_path_patch.start()
        self.main_database_path_patch.start()
        self.addCleanup(self.database_path_patch.stop)
        self.addCleanup(self.main_database_path_patch.stop)
        initialize_database()

    def sample(self, **overrides):
        payload = {
            "date": date.today().isoformat(),
            "type": "Technical Interview",
            "performance": "Mixed",
            "company": "Example Labs",
            "role": "Backend Engineer",
            "questions": "How does an index work?",
            "couldnt_answer": "Query planner details",
            "what_learned": "Review database internals",
            "action_items": "Practice explain plans",
            "notes": "Technical round",
        }
        payload.update(overrides)
        return PerformanceEntryCreate.model_validate(payload)

    def create_topic(self):
        category = create_preparation_category(PreparationCategoryCreate(name="SQL"))
        return create_preparation_topic(
            PreparationTopicCreate(category_id=category["id"], name="Indexing")
        )

    def test_crud_and_optional_relations(self):
        opportunity = create_opportunity(
            OpportunityCreate(company="Example Labs", role="Backend Engineer")
        )
        topic = self.create_topic()
        entry = create_performance_entry(self.sample(
            opportunity_id=opportunity["id"],
            preparation_topic_id=topic["id"],
            company=None,
            role=None,
        ))
        self.assertEqual(entry["company"], "Example Labs")
        self.assertEqual(entry["role"], "Backend Engineer")
        self.assertEqual(entry["preparation_topic_name"], "Indexing")
        self.assertEqual(entry["preparation_category"], "SQL")
        self.assertEqual(get_performance_entry(entry["id"])["id"], entry["id"])
        self.assertEqual(len(list_performance_entries()), 1)

        with database.database_connection(self.database_path) as connection:
            stored = connection.execute(
                "SELECT company, role FROM performance_entries WHERE id = ?",
                (entry["id"],),
            ).fetchone()
            topic_state = connection.execute(
                "SELECT status, practice_count FROM preparation_topics WHERE id = ?",
                (topic["id"],),
            ).fetchone()
        self.assertEqual(stored, (None, None))
        self.assertEqual(topic_state, ("Not Started", 0))

        updated = update_performance_entry(entry["id"], PerformanceEntryUpdate(
            opportunity_id=None,
            company="Personal practice",
            role="Interview prep",
            performance="Good",
            notes="Updated notes",
        ))
        self.assertEqual(updated["company"], "Personal practice")
        self.assertEqual(updated["performance"], "Good")
        self.assertEqual(updated["notes"], "Updated notes")
        self.assertIsNone(updated["opportunity_id"])
        self.assertIsNone(delete_performance_entry(entry["id"]))
        self.assertEqual(list_performance_entries(), [])

        standalone = create_performance_entry(self.sample(
            type="Mock Interview", opportunity_id=None, preparation_topic_id=None
        ))
        self.assertIsNone(standalone["opportunity_id"])
        self.assertIsNone(standalone["preparation_topic_id"])

    def test_filters_by_type_performance_company_opportunity_and_date(self):
        opportunity = create_opportunity(
            OpportunityCreate(company="Northwind", role="Data Engineer")
        )
        first = create_performance_entry(self.sample(
            type="Coding Test", performance="Good", company="Northwind",
            role="Data Engineer", date="2026-10-01",
        ))
        second = create_performance_entry(self.sample(
            type="HR Interview", performance="Poor", company=None, role=None,
            opportunity_id=opportunity["id"], date="2026-10-02",
        ))
        self.assertEqual([row["id"] for row in list_performance_entries(type="Coding Test")], [first["id"]])
        self.assertEqual([row["id"] for row in list_performance_entries(performance="Poor")], [second["id"]])
        self.assertEqual([row["id"] for row in list_performance_entries(company="northwind")], [second["id"], first["id"]])
        self.assertEqual([row["id"] for row in list_performance_entries(opportunity_id=opportunity["id"])], [second["id"]])
        self.assertEqual([row["id"] for row in list_performance_entries(date=date(2026, 10, 1))], [first["id"]])

    def test_invalid_references_missing_entries_and_validation(self):
        invalid = (
            {"type": "Unknown", "performance": "Good"},
            {"type": "Assessment", "performance": "Excellent"},
            {"type": "Assessment", "performance": "Mixed", "date": "not-a-date"},
            {"type": "Assessment", "performance": "Good", "opportunity_id": 0},
            {"type": "Assessment", "performance": "Good", "preparation_topic_id": 0},
        )
        for values in invalid:
            payload = {"date": "2026-10-07", "type": "Assessment", "performance": "Good"}
            payload.update(values)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                PerformanceEntryCreate.model_validate(payload)
        for payload in (
            PerformanceEntryCreate.model_validate({
                "date": "2026-10-07", "type": "Assessment", "performance": "Good", "opportunity_id": 999
            }),
            PerformanceEntryCreate.model_validate({
                "date": "2026-10-07", "type": "Assessment", "performance": "Good", "preparation_topic_id": 999
            }),
        ):
            with self.assertRaises(HTTPException) as missing_ref:
                create_performance_entry(payload)
            self.assertEqual(missing_ref.exception.status_code, 404)

        for operation in (
            lambda: get_performance_entry(999),
            lambda: update_performance_entry(999, PerformanceEntryUpdate(notes="x")),
            lambda: delete_performance_entry(999),
        ):
            with self.assertRaises(HTTPException) as missing:
                operation()
            self.assertEqual(missing.exception.status_code, 404)

    def test_summary_populated_and_empty(self):
        empty = get_performance_summary()
        self.assertEqual(empty["total"], 0)
        self.assertEqual(empty["recent_entries"], 0)
        self.assertEqual(set(empty["by_type"].values()), {0})
        self.assertEqual(set(empty["by_performance"].values()), {0})
        today = date.today()
        create_performance_entry(self.sample(date=today, type="Assessment", performance="Good"))
        create_performance_entry(self.sample(date=today - timedelta(days=2), type="Assessment", performance="Mixed"))
        create_performance_entry(self.sample(date=today - timedelta(days=40), type="Mock Interview", performance="Poor"))
        summary = get_performance_summary()
        self.assertEqual(summary, {
            "total": 3,
            "by_type": {"Assessment": 2, "Coding Test": 0, "Technical Interview": 0,
                        "HR Interview": 0, "Mock Interview": 1},
            "by_performance": {"Good": 1, "Mixed": 1, "Poor": 1},
            "recent_entries": 2,
        })

    def test_existing_v1_workflows_and_v2_dashboard_remain_available(self):
        today = date.today()
        habit = create_habit(HabitCreate(name="DSA", category="Technical"))
        self.assertEqual(complete_habit(habit["id"])["completed"], 1)
        daily_entry = create_daily_entry(DailyEntryCreate(date=today, deep_work_minutes=90))
        self.assertEqual(daily_entry["deep_work_minutes"], 90)
        self.assertEqual(get_daily_entry(today)["deep_work_minutes"], 90)
        self.assertEqual(get_daily_score(today)["score"], 26)
        self.assertIn("current_streak", get_placement_streak())

        mit = create_mit(MITCreate(date=today, task="Review graph problems"))
        self.assertEqual(get_mits(today)[0]["id"], mit["id"])
        reflection = create_reflection(ReflectionCreate(date=today, went_well="Focused practice"))
        self.assertEqual(get_reflection(today)["id"], reflection["id"])
        self.assertIn("applications", get_dashboard())

    def test_migration_from_version_five_preserves_v1_and_v2_rows(self):
        v5_path = Path(self.temp_directory.name) / "v5.db"
        with patch("app.database.DATABASE_PATH", v5_path), patch.object(
            database, "LATEST_SCHEMA_VERSION", 5
        ), patch.object(database, "MIGRATIONS", database.MIGRATIONS[:5]):
            initialize_database()
            with database.database_connection(v5_path) as connection:
                connection.execute("INSERT INTO habits (name, category) VALUES ('DSA', 'Technical')")
                connection.execute("INSERT INTO habit_completions (habit_id, date) VALUES (1, '2026-10-06')")
                connection.execute("INSERT INTO daily_entries (date, deep_work_minutes) VALUES ('2026-10-06', 120)")
                connection.execute("INSERT INTO daily_mits (date, task) VALUES ('2026-10-06', 'Practice SQL')")
                connection.execute("INSERT INTO daily_reflections (date, went_well) VALUES ('2026-10-06', 'Focused')")
                connection.execute("INSERT INTO opportunities (company, role) VALUES ('Example', 'Engineer')")
                category = connection.execute("SELECT id FROM preparation_categories WHERE name = 'SQL / DBMS'").fetchone()[0]
                connection.execute("INSERT INTO preparation_topics (category_id, name) VALUES (?, 'Indexes')", (category,))
                connection.execute("INSERT INTO deep_work_sessions (date, duration_minutes, category, source) VALUES ('2026-10-06', 60, 'SQL', 'manual')")
                connection.execute("UPDATE app_settings SET value = 'Preserve this' WHERE key = 'placement_goal'")
                before = {
                    table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("habits", "habit_completions", "daily_entries", "daily_mits",
                                  "daily_reflections", "opportunities", "preparation_categories",
                                  "preparation_topics", "deep_work_sessions", "app_settings")
                }
        with patch("app.database.DATABASE_PATH", v5_path):
            initialize_database()
            initialize_database()
        with database.database_connection(v5_path) as connection:
            after = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in before
            }
            self.assertEqual(after, before)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], database.LATEST_SCHEMA_VERSION)
            self.assertEqual(connection.execute("SELECT value FROM app_settings WHERE key = 'placement_goal'").fetchone()[0], "Preserve this")
            self.assertEqual(connection.execute("SELECT couldnt_answer FROM performance_entries").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
