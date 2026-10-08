import sqlite3
import tempfile
import unittest
from contextlib import closing
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app.database import initialize_database
from app.main import (
    calculate_daily_score,
    create_deep_work_session,
    create_mit,
    create_opportunity,
    get_dashboard,
    get_dashboard_settings,
    update_dashboard_settings,
)
from app.schemas import (
    DashboardResponse,
    DashboardSettingsUpdate,
    DeepWorkSessionCreate,
    MITCreate,
    OpportunityCreate,
)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "dashboard.db"
        self.database_patch = patch("app.database.DATABASE_PATH", self.database_path)
        self.database_patch.start()
        initialize_database()
        self.main_patch = patch("app.main.DATABASE_PATH", self.database_path)
        self.main_patch.start()

    def tearDown(self):
        self.main_patch.stop()
        self.database_patch.stop()
        self.tempdir.cleanup()

    def test_settings_defaults_and_updates(self):
        settings = get_dashboard_settings()
        self.assertEqual(settings["goal"], "Get placed in a good software / AI role")
        self.assertEqual(settings["daily_deep_work_target_minutes"], 180)
        updated = update_dashboard_settings(DashboardSettingsUpdate(
            goal="Become a backend engineer", daily_deep_work_target_minutes=240
        ))
        self.assertEqual(updated["goal"], "Become a backend engineer")
        self.assertEqual(updated["daily_deep_work_target_minutes"], 240)
        target_only = update_dashboard_settings(
            DashboardSettingsUpdate(daily_deep_work_target_minutes=210)
        )
        self.assertEqual(target_only["goal"], "Become a backend engineer")
        self.assertEqual(target_only["daily_deep_work_target_minutes"], 210)
        for payload in ({}, {"goal": "  "}, {"daily_deep_work_target_minutes": 0}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    DashboardSettingsUpdate.model_validate(payload)

    def test_applications_pipeline_and_nearest_open_deadline(self):
        today = date.today()
        records = [
            OpportunityCreate(company="Active A", role="Engineer", status="Interested", is_serious=True, deadline=today + timedelta(days=8)),
            OpportunityCreate(company="Active B", role="Analyst", status="Applied", is_serious=True, deadline=today + timedelta(days=3)),
            OpportunityCreate(company="Active C", role="Scientist", status="Interview", is_serious=True),
            OpportunityCreate(company="Won", role="Engineer", status="Selected", is_serious=True, deadline=today + timedelta(days=1)),
            OpportunityCreate(company="Rejected", role="Analyst", status="Rejected", is_serious=True, deadline=today + timedelta(days=2)),
            OpportunityCreate(company="Inbox", role="Engineer", status="Interested", is_serious=False, deadline=today + timedelta(days=1)),
        ]
        for record in records:
            create_opportunity(record)
        dashboard = get_dashboard()
        self.assertEqual(dashboard["applications"]["active"], 3)
        self.assertEqual(dashboard["applications"]["pipeline"]["Interested"], 1)
        self.assertEqual(dashboard["applications"]["pipeline"]["Applied"], 1)
        self.assertEqual(dashboard["applications"]["pipeline"]["Interview"], 1)
        self.assertEqual(dashboard["applications"]["pipeline"]["Selected"], 1)
        self.assertEqual(dashboard["applications"]["pipeline"]["Rejected"], 1)
        self.assertEqual(dashboard["next_deadline"]["company"], "Inbox")
        self.assertEqual(dashboard["next_deadline"]["opportunity_id"], 6)
        self.assertNotEqual(dashboard["next_deadline"]["company"], "Won")
        DashboardResponse.model_validate(dashboard)

    def test_preparation_counts_category_progress_and_empty_state(self):
        empty = get_dashboard()["preparation"]
        self.assertEqual(empty["total_topics"], 0)
        self.assertEqual(empty["completion_percentage"], 0)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            category_id = connection.execute(
                "SELECT id FROM preparation_categories WHERE name = 'DSA'"
            ).fetchone()[0]
            connection.executemany(
                "INSERT INTO preparation_topics "
                "(category_id, name, status, practice_count) VALUES (?, ?, ?, ?)",
                [
                    (category_id, "Arrays", "Completed", 3),
                    (category_id, "Graphs", "In Progress", 2),
                    (category_id, "DP", "Not Started", 1),
                ],
            )
        prep = get_dashboard()["preparation"]
        self.assertEqual(prep["total_topics"], 3)
        self.assertEqual(prep["completed"], 1)
        self.assertEqual(prep["in_progress"], 1)
        self.assertEqual(prep["not_started"], 1)
        self.assertEqual(prep["completion_percentage"], 33.3)
        self.assertEqual(prep["total_practice_count"], 6)
        dsa = next(category for category in prep["categories"] if category["category"] == "DSA")
        self.assertEqual(dsa["completion_percentage"], 33.3)

    def test_daily_weekly_deep_work_and_scoring_target_remain_separate(self):
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        update_dashboard_settings(DashboardSettingsUpdate(daily_deep_work_target_minutes=240))
        create_deep_work_session(DeepWorkSessionCreate(date=today, duration_minutes=90, category="DSA"))
        create_deep_work_session(DeepWorkSessionCreate(date=today, duration_minutes=30, category="Python"))
        previous_week = week_start - timedelta(days=1)
        create_deep_work_session(DeepWorkSessionCreate(date=previous_week, duration_minutes=60, category="Other"))
        dashboard = get_dashboard()
        daily = dashboard["deep_work"]["daily"]
        weekly = dashboard["deep_work"]["weekly"]
        self.assertEqual(daily["target_minutes"], 240)
        self.assertEqual(daily["actual_minutes"], 120)
        self.assertEqual(daily["progress_percentage"], 50.0)
        self.assertEqual(weekly["target_minutes"], 1680)
        self.assertEqual(weekly["actual_minutes"], 120)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            score = calculate_daily_score(connection, today)
        self.assertEqual(score["score"], 27)

    def test_today_focus_and_complete_dashboard_response(self):
        today = date.today()
        create_mit(MITCreate(date=today, task="Review graph problems"))
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            category_id = connection.execute(
                "SELECT id FROM preparation_categories WHERE name = 'Python'"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO preparation_topics (category_id, name, status) "
                "VALUES (?, ?, 'In Progress')",
                (category_id, "Decorators"),
            )
            connection.execute(
                "INSERT INTO preparation_topics (category_id, name, status) "
                "VALUES (?, ?, 'Completed')",
                (category_id, "Data types"),
            )
        raw = get_dashboard()
        response = DashboardResponse.model_validate(raw)
        self.assertEqual(response.today.mits[0].task, "Review graph problems")
        self.assertEqual([topic.name for topic in response.today.incomplete_topics], ["Decorators"])
        self.assertEqual(response.deep_work.daily.target_minutes, 180)
        self.assertEqual(set(response.applications.pipeline), {
            "Interested", "Applied", "Assessment", "Interview", "HR",
            "Selected", "Rejected", "Withdrawn", "Not Eligible", "Expired",
        })


if __name__ == "__main__":
    unittest.main()