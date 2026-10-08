from __future__ import annotations

import tempfile
import unittest
from datetime import date as real_date, timedelta
from pathlib import Path
from unittest.mock import patch

import app.database as database
from app.database import database_connection, initialize_database
from app.main import (
    PLACEMENT_THRESHOLD, SPRINT_END, SPRINT_START, calculate_daily_score,
    get_analytics, get_placement_streak,
)


class FrozenDate(real_date):
    @classmethod
    def today(cls):
        return cls._today


class CorrectnessRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.path = Path(self.tempdir.name) / "correctness.db"
        self.db_patch = patch("app.database.DATABASE_PATH", self.path)
        self.main_patch = patch("app.main.DATABASE_PATH", self.path)
        self.db_patch.start()
        self.main_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.main_patch.stop)
        initialize_database()

    def test_active_habits_match_score_and_analytics(self):
        with database_connection(self.path) as connection:
            active_id = connection.execute(
                "INSERT INTO habits (name, category) VALUES ('Active', 'Technical')"
            ).lastrowid
            inactive_id = connection.execute(
                "INSERT INTO habits (name, category, is_active) VALUES ('Inactive', 'Technical', 0)"
            ).lastrowid
            connection.executemany(
                "INSERT INTO habit_completions (habit_id, date) VALUES (?, '2026-10-06')",
                ((active_id,), (inactive_id,)),
            )
        with patch("app.main.date", FrozenDate):
            FrozenDate._today = real_date(2026, 10, 8)
            metrics = get_analytics()
        self.assertEqual(metrics["habit_completion_rate"], 33)
        with database_connection(self.path) as connection:
            score = calculate_daily_score(connection, real_date(2026, 10, 6))
        self.assertEqual(score["technical_completed"], 1)
        self.assertEqual(score["score"], 6)

    def test_streak_response_marks_upcoming_and_completed(self):
        with patch("app.main.date", FrozenDate):
            FrozenDate._today = real_date(2026, 10, 5)
            upcoming = get_placement_streak()
        self.assertEqual((upcoming["current_streak"], upcoming["period_status"], upcoming["as_of_date"]), (0, "upcoming", None))
        with database_connection(self.path) as connection:
            ids = []
            for category in ("Technical", "Placement"):
                for index in range(5):
                    ids.append(connection.execute(
                        "INSERT INTO habits (name, category) VALUES (?, ?)",
                        (f"{category}-{index}", category),
                    ).lastrowid)
            day = SPRINT_START
            while day <= SPRINT_END:
                connection.execute(
                    "INSERT INTO daily_entries (date, deep_work_minutes) VALUES (?, 180)",
                    (day.isoformat(),),
                )
                connection.executemany(
                    "INSERT INTO habit_completions (habit_id, date) VALUES (?, ?)",
                    ((habit_id, day.isoformat()) for habit_id in ids),
                )
                day += timedelta(days=1)
        with patch("app.main.date", FrozenDate):
            FrozenDate._today = real_date(2026, 11, 6)
            completed = get_placement_streak()
        self.assertEqual(completed["threshold"], PLACEMENT_THRESHOLD)
        self.assertEqual((completed["period_status"], completed["as_of_date"], completed["current_streak"]), ("completed", "2026-11-05", 31))

    def test_v7_backfills_only_missing_linked_performance_snapshots(self):
        path = Path(self.tempdir.name) / "v6.db"
        with patch("app.database.DATABASE_PATH", path), patch.object(
            database, "LATEST_SCHEMA_VERSION", 6
        ), patch.object(database, "MIGRATIONS", database.MIGRATIONS[:6]):
            initialize_database()
            with database_connection(path) as connection:
                opportunity_id = connection.execute(
                    "INSERT INTO opportunities (company, role) VALUES ('Original Co', 'Original Role')"
                ).lastrowid
                connection.execute(
                    "INSERT INTO performance_entries (date, type, performance, opportunity_id) VALUES ('2026-10-06', 'Assessment', 'Good', ?)",
                    (opportunity_id,),
                )
                connection.execute(
                    "INSERT INTO performance_entries (company, date, type, performance, opportunity_id) VALUES ('Manual', '2026-10-06', 'Assessment', 'Good', ?)",
                    (opportunity_id,),
                )
                connection.execute(
                    "INSERT INTO performance_entries (date, type, performance) VALUES ('2026-10-06', 'Assessment', 'Good')"
                )
        with patch("app.database.DATABASE_PATH", path):
            initialize_database()
            initialize_database()
        with database_connection(path) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 7)
            rows = connection.execute("SELECT company, role FROM performance_entries ORDER BY id").fetchall()
        self.assertEqual(rows, [("Original Co", "Original Role"), ("Manual", "Original Role"), (None, None)])


if __name__ == "__main__":
    unittest.main()