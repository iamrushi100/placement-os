import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app.database as database

from app.database import database_connection, initialize_database
from app.main import (
    create_preparation_category,
    create_preparation_topic,
    delete_preparation_category,
    delete_preparation_topic,
    get_preparation_categories,
    get_preparation_topic,
    get_preparation_topics,
    practice_preparation_topic,
    update_preparation_category,
    update_preparation_topic,
)
from app.schemas import (
    PreparationCategoryCreate,
    PreparationCategoryUpdate,
    PreparationTopicCreate,
    PreparationTopicUpdate,
)


DEFAULT_CATEGORIES = {
    "DSA",
    "SQL / DBMS",
    "Python",
    "OOP",
    "Aptitude",
    "Machine Learning",
    "Deep Learning",
    "GenAI",
    "Cybersecurity",
    "Projects",
    "Interview Preparation",
}


class PreparationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.database_path = Path(self.temp_directory.name) / "preparation.db"

        self.database_path_patch = patch(
            "app.database.DATABASE_PATH", self.database_path
        )
        self.database_path_patch.start()
        self.addCleanup(self.database_path_patch.stop)

        self.main_database_path_patch = patch(
            "app.main.DATABASE_PATH", self.database_path
        )
        self.main_database_path_patch.start()
        self.addCleanup(self.main_database_path_patch.stop)

        initialize_database()

    def category_id(self, name):
        return next(
            category["id"]
            for category in get_preparation_categories()
            if category["name"] == name
        )

    def test_default_categories_are_seeded_once_and_remain_editable(self):
        categories = get_preparation_categories()
        self.assertEqual({category["name"] for category in categories}, DEFAULT_CATEGORIES)
        self.assertEqual(len(categories), len(DEFAULT_CATEGORIES))

        dsa_id = self.category_id("DSA")
        renamed = update_preparation_category(
            dsa_id, PreparationCategoryUpdate(name="Algorithms")
        )
        self.assertEqual(renamed["name"], "Algorithms")

        initialize_database()
        names = {category["name"] for category in get_preparation_categories()}
        self.assertEqual(len(names), len(DEFAULT_CATEGORIES))
        self.assertIn("Algorithms", names)
        self.assertNotIn("DSA", names)

    def test_category_crud_duplicate_and_topic_deletion_protection(self):
        created = create_preparation_category(
            PreparationCategoryCreate(name="  Cloud Security  ")
        )
        self.assertEqual(created["name"], "Cloud Security")
        self.assertIn(created, get_preparation_categories())

        with self.assertRaises(HTTPException) as duplicate:
            create_preparation_category(
                PreparationCategoryCreate(name="Cloud Security")
            )
        self.assertEqual(duplicate.exception.status_code, 409)

        updated = update_preparation_category(
            created["id"], PreparationCategoryUpdate(name="Application Security")
        )
        self.assertEqual(updated["name"], "Application Security")

        topic = create_preparation_topic(
            PreparationTopicCreate(category_id=created["id"], name="Threat Modeling")
        )
        with self.assertRaises(HTTPException) as has_topics:
            delete_preparation_category(created["id"])
        self.assertEqual(has_topics.exception.status_code, 409)

        delete_preparation_topic(topic["id"])
        self.assertIsNone(delete_preparation_category(created["id"]))
        self.assertNotIn(created["id"], [item["id"] for item in get_preparation_categories()])

    def test_topic_crud_filters_and_practice_count(self):
        dsa_id = self.category_id("DSA")
        python_id = self.category_id("Python")
        topic = create_preparation_topic(
            PreparationTopicCreate(
                category_id=dsa_id,
                name=" Arrays ",
                status="In Progress",
                notes="Practice two-pointer problems",
            )
        )
        self.assertEqual(topic["name"], "Arrays")
        self.assertEqual(topic["practice_count"], 0)
        self.assertEqual(topic["status"], "In Progress")
        self.assertEqual(get_preparation_topic(topic["id"])["id"], topic["id"])

        other = create_preparation_topic(
            PreparationTopicCreate(
                category_id=python_id,
                name="Decorators",
                status="Completed",
                practice_count=3,
            )
        )
        self.assertEqual(len(get_preparation_topics()), 2)
        self.assertEqual(
            [item["name"] for item in get_preparation_topics(category_id=dsa_id)],
            ["Arrays"],
        )
        self.assertEqual(
            [item["name"] for item in get_preparation_topics(status="Completed")],
            ["Decorators"],
        )

        updated = update_preparation_topic(
            topic["id"],
            PreparationTopicUpdate(
                category_id=python_id,
                name="Array Patterns",
                practice_count=4,
                notes="Updated notes",
            ),
        )
        self.assertEqual(updated["category_id"], python_id)
        self.assertEqual(updated["status"], "In Progress")
        self.assertEqual(updated["practice_count"], 4)

        practiced = practice_preparation_topic(topic["id"])
        self.assertEqual(practiced["practice_count"], 5)
        self.assertEqual(practiced["status"], "In Progress")
        self.assertEqual(practice_preparation_topic(topic["id"])["practice_count"], 6)

        delete_preparation_topic(other["id"])
        delete_preparation_topic(topic["id"])
        self.assertEqual(get_preparation_topics(), [])

    def test_invalid_categories_topics_and_negative_practice_counts(self):
        for payload, schema in (
            ({"name": "  "}, PreparationCategoryCreate),
            ({"category_id": 1, "name": "  "}, PreparationTopicCreate),
            ({"category_id": 1, "name": "Arrays", "status": "Unknown"}, PreparationTopicCreate),
            ({"category_id": 1, "name": "Arrays", "practice_count": -1}, PreparationTopicCreate),
            ({"practice_count": -1}, PreparationTopicUpdate),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    schema.model_validate(payload)

        with self.assertRaises(HTTPException) as bad_category:
            create_preparation_topic(
                PreparationTopicCreate(category_id=9999, name="No category")
            )
        self.assertEqual(bad_category.exception.status_code, 404)

        category_id = self.category_id("DSA")
        topic = create_preparation_topic(
            PreparationTopicCreate(category_id=category_id, name="Binary Search")
        )
        with self.assertRaises(HTTPException) as bad_topic_category:
            update_preparation_topic(
                topic["id"], PreparationTopicUpdate(category_id=9999)
            )
        self.assertEqual(bad_topic_category.exception.status_code, 404)

        with database_connection(self.database_path) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE preparation_topics SET practice_count = -1 WHERE id = ?",
                    (topic["id"],),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO preparation_topics (category_id, name) "
                    "VALUES (?, ?)",
                    (9999, "Orphan topic"),
                )

        missing_operations = (
            lambda: update_preparation_category(9999, PreparationCategoryUpdate(name="Missing")),
            lambda: delete_preparation_category(9999),
            lambda: get_preparation_topic(9999),
            lambda: update_preparation_topic(9999, PreparationTopicUpdate(name="Missing")),
            lambda: delete_preparation_topic(9999),
            lambda: practice_preparation_topic(9999),
        )
        for operation in missing_operations:
            with self.assertRaises(HTTPException) as missing:
                operation()
            self.assertEqual(missing.exception.status_code, 404)



class PreparationMigrationUpgradeTests(unittest.TestCase):
    def test_version_three_preserves_existing_opportunity_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "v2-upgrade.db"
            with patch.object(database, "DATABASE_PATH", database_path):
                with patch.object(database, "MIGRATIONS", database.MIGRATIONS[:2]):
                    with patch.object(database, "LATEST_SCHEMA_VERSION", 2):
                        database.initialize_database()

                with database_connection(database_path) as connection:
                    connection.execute(
                        "INSERT INTO opportunities (company, role, status, priority) "
                        "VALUES (?, ?, ?, ?)",
                        ("Existing Employer", "Software Engineer", "Applied", "High"),
                    )

                database.initialize_database()
                database.initialize_database()

                with database_connection(database_path) as connection:
                    opportunity = connection.execute(
                        "SELECT company, role, status, priority "
                        "FROM opportunities"
                    ).fetchone()
                    self.assertEqual(
                        tuple(opportunity),
                        ("Existing Employer", "Software Engineer", "Applied", "High"),
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        database.LATEST_SCHEMA_VERSION
                    )

if __name__ == "__main__":
    unittest.main()