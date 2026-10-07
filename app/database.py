import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator


DATABASE_PATH = Path(__file__).resolve().parent.parent / "placement.db"
LATEST_SCHEMA_VERSION = 2


@contextmanager
def database_connection(path: Path) -> Iterator[sqlite3.Connection]:
    """Open a transaction-scoped SQLite connection and always close it."""
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            yield connection


def _create_current_tables(connection: sqlite3.Connection) -> None:
    """Create the existing application tables for new or pre-migration DBs."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS habit_completions (
            id INTEGER PRIMARY KEY,
            habit_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (habit_id) REFERENCES habits(id),
            UNIQUE (habit_id, date)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_entries (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,
            deep_work_minutes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_mits (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            task TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (date, task)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_reflections (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,
            went_well TEXT NOT NULL DEFAULT '',
            challenges TEXT NOT NULL DEFAULT '',
            improvement TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _create_opportunities_table(connection: sqlite3.Connection) -> None:
    """Add the V2 placement opportunities inbox and application pipeline."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY,
            company TEXT NOT NULL CHECK (length(trim(company)) > 0),
            role TEXT NOT NULL CHECK (length(trim(role)) > 0),
            location TEXT,
            source TEXT,
            job_link TEXT,
            status TEXT NOT NULL DEFAULT 'Interested'
                CHECK (status IN (
                    'Interested', 'Applied', 'Assessment', 'Interview', 'HR',
                    'Selected', 'Rejected', 'Withdrawn', 'Not Eligible', 'Expired'
                )),
            priority TEXT NOT NULL DEFAULT 'Medium'
                CHECK (priority IN ('Low', 'Medium', 'High')),
            ctc TEXT,
            deadline TEXT,
            referral TEXT,
            eligibility TEXT,
            requirements TEXT,
            notes TEXT,
            is_serious INTEGER NOT NULL DEFAULT 0
                CHECK (is_serious IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
MIGRATIONS = ((1, _create_current_tables), (2, _create_opportunities_table))


def initialize_database() -> None:
    """Apply pending schema migrations atomically and safely on startup."""
    with closing(sqlite3.connect(DATABASE_PATH, timeout=30)) as connection:
        current_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version > LATEST_SCHEMA_VERSION:
            raise RuntimeError(
                "Database schema version "
                f"{current_version} is newer than supported version "
                f"{LATEST_SCHEMA_VERSION}"
            )

        for version, migration in MIGRATIONS:
            if version <= current_version:
                continue

            try:
                connection.execute("BEGIN IMMEDIATE")
                migration(connection)
                connection.execute(f"PRAGMA user_version = {version}")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
