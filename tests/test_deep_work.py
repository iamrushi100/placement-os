import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.database import database_connection, initialize_database
from app.main import (
    calculate_daily_score,
    create_deep_work_session,
    delete_deep_work_session,
    get_daily_deep_work_summary,
    get_deep_work_categories,
    get_deep_work_session,
    get_deep_work_sessions,
    get_deep_work_timer,
    start_deep_work_timer,
    stop_deep_work_timer,
)
from app.schemas import DeepWorkSessionCreate, DeepWorkTimerStart


class DeepWorkTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "deep-work.db"
        self.database_patch = patch("app.database.DATABASE_PATH", self.database_path)
        self.database_patch.start()
        initialize_database()
        self.main_patch = patch("app.main.DATABASE_PATH", self.database_path)
        self.main_patch.start()

    def tearDown(self):
        self.main_patch.stop()
        self.database_patch.stop()
        self.tempdir.cleanup()

    def test_manual_sessions_list_filter_daily_total_get_delete(self):
        first = create_deep_work_session(DeepWorkSessionCreate(
            date=date(2026, 10, 7), duration_minutes=60, category="DSA", notes="Graphs"
        ))
        second = create_deep_work_session(DeepWorkSessionCreate(
            date=date(2026, 10, 7), duration_minutes=45, category="Python"
        ))
        self.assertEqual(first["source"], "manual")
        self.assertIsNone(first["started_at"])
        self.assertEqual(len(get_deep_work_sessions(date=date(2026, 10, 7))), 2)
        self.assertEqual(len(get_deep_work_sessions(category="DSA")), 1)
        self.assertEqual(get_deep_work_session(first["id"])["notes"], "Graphs")
        daily = get_daily_deep_work_summary(date(2026, 10, 7))
        self.assertEqual(daily["total_minutes"], 105)
        self.assertEqual(daily["progress_percentage"], 100 * 105 / 180)
        self.assertIsNone(delete_deep_work_session(first["id"]))
        self.assertEqual(len(get_deep_work_sessions()), 1)
        with self.assertRaises(HTTPException) as missing:
            get_deep_work_session(999)
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(HTTPException):
            delete_deep_work_session(999)

    def test_category_list_comes_from_backend_supported_values(self):
        self.assertEqual(
            get_deep_work_categories(),
            ["DSA", "SQL", "Python", "AI/ML", "GenAI", "Cybersecurity", "Project", "Interview Preparation", "Other"],
        )

    def test_validation_rejects_short_session_and_unknown_category(self):
        with self.assertRaises(ValueError):
            DeepWorkSessionCreate(date="2026-10-07", duration_minutes=29, category="DSA")
        with self.assertRaises(ValueError):
            DeepWorkSessionCreate(date="2026-10-07", duration_minutes=30, category="Other topic")

    def test_timer_singleton_short_stop_and_completed_stop(self):
        start_time = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)
        with patch("app.main.current_local_datetime", return_value=start_time):
            timer = start_deep_work_timer(DeepWorkTimerStart(category="SQL", notes="joins"))
        self.assertEqual(timer["category"], "SQL")
        self.assertIsNotNone(get_deep_work_timer())
        with self.assertRaises(HTTPException) as already_running:
            start_deep_work_timer(DeepWorkTimerStart(category="DSA"))
        self.assertEqual(already_running.exception.status_code, 409)

        with patch("app.main.current_local_datetime", return_value=start_time + timedelta(minutes=29, seconds=59)):
            short = stop_deep_work_timer()
        self.assertFalse(short["completed"])
        self.assertEqual(short["duration_minutes"], 29)
        self.assertIsNone(get_deep_work_timer())
        with self.assertRaises(HTTPException) as no_timer:
            stop_deep_work_timer()
        self.assertEqual(no_timer.exception.status_code, 409)

        with patch("app.main.current_local_datetime", return_value=start_time):
            start_deep_work_timer(DeepWorkTimerStart(category="DSA"))
        with patch("app.main.current_local_datetime", return_value=start_time + timedelta(minutes=42, seconds=10)):
            completed = stop_deep_work_timer()
        self.assertTrue(completed["completed"])
        self.assertEqual(completed["duration_minutes"], 42)
        self.assertEqual(completed["session"]["source"], "timer")
        self.assertEqual(completed["session"]["date"], "2026-10-07")
        self.assertEqual(get_daily_deep_work_summary(date(2026, 10, 7))["total_minutes"], 42)

    def test_score_uses_sessions_and_falls_back_to_legacy_daily_entry(self):
        legacy_date = date(2026, 10, 6)
        with patch("app.main.DATABASE_PATH", self.database_path):
            import sqlite3
            connection = sqlite3.connect(self.database_path)
            try:
                connection.execute(
                    "INSERT INTO daily_entries (date, deep_work_minutes) VALUES (?, ?)",
                    (legacy_date.isoformat(), 90),
                )
                connection.commit()
            finally:
                connection.close()
            connection = sqlite3.connect(self.database_path)
            try:
                score_before = calculate_daily_score(connection, legacy_date)
            finally:
                connection.close()
            self.assertEqual(score_before["score"], 20)
            self.assertEqual(get_daily_deep_work_summary(legacy_date)["total_minutes"], 90)
            create_deep_work_session(DeepWorkSessionCreate(
                date=legacy_date, duration_minutes=30, category="Other"
            ))
            connection = sqlite3.connect(self.database_path)
            try:
                score_after = calculate_daily_score(connection, legacy_date)
            finally:
                connection.close()
            self.assertEqual(score_after["score"], 7)
            self.assertEqual(get_daily_deep_work_summary(legacy_date)["total_minutes"], 30)
            with database_connection(self.database_path) as verify_connection:
                self.assertEqual(
                    verify_connection.execute(
                        "SELECT deep_work_minutes FROM daily_entries WHERE date = ?",
                        (legacy_date.isoformat(),),
                    ).fetchone()[0],
                    90,
                )

    def test_score_is_zero_without_activity(self):
        with database_connection(self.database_path) as connection:
            score = calculate_daily_score(connection, date(2026, 10, 7))
        self.assertEqual(score["score"], 0)

    def test_negative_legacy_deep_work_cannot_make_score_negative(self):
        requested_date = date(2026, 10, 7)
        with database_connection(self.database_path) as connection:
            connection.execute(
                "INSERT INTO daily_entries (date, deep_work_minutes) VALUES (?, ?)",
                (requested_date.isoformat(), -500),
            )
            score = calculate_daily_score(connection, requested_date)
        self.assertEqual(score["score"], 0)

    def test_score_is_capped_at_100_and_inactive_habits_do_not_count(self):
        import sqlite3
        with database_connection(self.database_path) as connection:
            connection.execute(
                "INSERT INTO daily_entries (date, deep_work_minutes) VALUES ('2026-10-07', 180)"
            )
            habit_ids = []
            for category in ("Technical", "Placement"):
                for index in range(6):
                    cursor = connection.execute(
                        "INSERT INTO habits (name, category) VALUES (?, ?)",
                        (f"{category} {index}", category),
                    )
                    habit_ids.append(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO habit_completions (habit_id, date) VALUES (?, '2026-10-07')",
                ((habit_id,) for habit_id in habit_ids),
            )
            connection.commit()
            capped = calculate_daily_score(connection, date(2026, 10, 7))
            self.assertEqual(capped["score"], 100)
            self.assertEqual(capped["technical_completed"], 6)
            self.assertEqual(capped["placement_completed"], 6)
            connection.execute(
                "UPDATE habits SET is_active = 0 WHERE category = 'Technical' AND id != ?",
                (habit_ids[4],),
            )
            connection.commit()
            inactive_excluded = calculate_daily_score(connection, date(2026, 10, 7))
            self.assertEqual(inactive_excluded["technical_completed"], 1)
            self.assertEqual(inactive_excluded["score"], 76)


if __name__ == "__main__":
    unittest.main()