import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator


DATABASE_PATH = Path(__file__).resolve().parent.parent / "placement.db"
LATEST_SCHEMA_VERSION = 7


@contextmanager
def database_connection(path: Path) -> Iterator[sqlite3.Connection]:
    """Open a transaction-scoped SQLite connection and always close it."""
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
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
def _create_preparation_tables(connection: sqlite3.Connection) -> None:
    """Create editable preparation categories/topics and seed defaults once."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS preparation_categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS preparation_topics (
            id INTEGER PRIMARY KEY,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL CHECK (length(trim(name)) > 0),
            status TEXT NOT NULL DEFAULT 'Not Started'
                CHECK (status IN ('Not Started', 'In Progress', 'Completed')),
            practice_count INTEGER NOT NULL DEFAULT 0
                CHECK (practice_count >= 0),
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id)
                REFERENCES preparation_categories(id) ON DELETE RESTRICT
        )
        """
    )

    default_categories = (
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
    )
    connection.executemany(
        "INSERT OR IGNORE INTO preparation_categories (name) VALUES (?)",
        ((name,) for name in default_categories),
    )

def _create_deep_work_tables(connection: sqlite3.Connection) -> None:
    """Add completed focus sessions and the single active timer state."""
    categories = "'DSA', 'SQL', 'Python', 'AI/ML', 'GenAI', 'Cybersecurity', 'Project', 'Interview Preparation', 'Other'"
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS deep_work_sessions (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL CHECK (duration_minutes >= 30),
            category TEXT NOT NULL CHECK (category IN ({categories})),
            notes TEXT,
            started_at TEXT,
            ended_at TEXT,
            source TEXT NOT NULL CHECK (source IN ('manual', 'timer')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (
                (source = 'manual' AND started_at IS NULL AND ended_at IS NULL)
                OR (source = 'timer' AND started_at IS NOT NULL AND ended_at IS NOT NULL)
            )
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS deep_work_active_timer (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            category TEXT NOT NULL CHECK (category IN ({categories})),
            notes TEXT,
            started_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'timer' CHECK (source = 'timer')
        )
        """
    )

def _create_dashboard_settings_table(connection: sqlite3.Connection) -> None:
    """Store the two user-configurable values shown on the dashboard."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.executemany(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        (
            ("placement_goal", "Get placed in a good software / AI role"),
            ("daily_deep_work_target_minutes", "180"),
        ),
    )


def _create_performance_entries_table(connection: sqlite3.Connection) -> None:
    """Store assessment and interview reflections with optional source links."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS performance_entries (
            id INTEGER PRIMARY KEY,
            company TEXT,
            role TEXT,
            date TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN (
                'Assessment', 'Coding Test', 'Technical Interview',
                'HR Interview', 'Mock Interview'
            )),
            performance TEXT NOT NULL CHECK (performance IN ('Good', 'Mixed', 'Poor')),
            opportunity_id INTEGER,
            preparation_topic_id INTEGER,
            questions TEXT NOT NULL DEFAULT '',
            couldnt_answer TEXT NOT NULL DEFAULT '',
            what_learned TEXT NOT NULL DEFAULT '',
            action_items TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE SET NULL,
            FOREIGN KEY (preparation_topic_id) REFERENCES preparation_topics(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_performance_date ON performance_entries(date DESC, id DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_performance_type ON performance_entries(type)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_performance_level ON performance_entries(performance)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_performance_opportunity ON performance_entries(opportunity_id)"
    )


def _snapshot_performance_context(connection: sqlite3.Connection) -> None:
    """Backfill existing linked entries without replacing stored snapshots."""
    connection.execute(
        """
        UPDATE performance_entries
        SET company = COALESCE(
                company,
                (SELECT company FROM opportunities WHERE id = performance_entries.opportunity_id)
            ),
            role = COALESCE(
                role,
                (SELECT role FROM opportunities WHERE id = performance_entries.opportunity_id)
            )
        WHERE opportunity_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM opportunities WHERE id = performance_entries.opportunity_id
          )
        """
    )


MIGRATIONS = (
    (1, _create_current_tables),
    (2, _create_opportunities_table),
    (3, _create_preparation_tables),
    (4, _create_deep_work_tables),
    (5, _create_dashboard_settings_table),
    (6, _create_performance_entries_table),
    (7, _snapshot_performance_context),
)


def initialize_database() -> None:
    """Apply pending schema migrations atomically and safely on startup."""
    with closing(sqlite3.connect(DATABASE_PATH, timeout=30)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
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
