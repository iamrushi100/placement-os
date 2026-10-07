import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.database import initialize_database
from app.main import (
    calculate_daily_score,
    create_deep_work_session,
    delete_deep_work_session,
    get_daily_deep_work_summary,
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
            create_deep_work_session(DeepWorkSessionCreate(
                date=legacy_date, duration_minutes=30, category="Other"
            ))
            connection = sqlite3.connect(self.database_path)
            try:
                score_after = calculate_daily_score(connection, legacy_date)
            finally:
                connection.close()
            self.assertEqual(score_after["score"], 7)


if __name__ == "__main__":
    unittest.main()