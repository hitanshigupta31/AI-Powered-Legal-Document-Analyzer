# ============================================================
# CLAUSEGUARD - WATCHTOWER PERSISTENCE SCHEMA
# ============================================================

from pathlib import Path
import sqlite3


APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
DATABASE_PATH = PROJECT_DIR / "clauseguard.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _table_columns(cursor, table_name: str) -> set[str]:
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _ensure_column(cursor, table_name: str, column_name: str, column_sql: str) -> None:
    if column_name not in _table_columns(cursor, table_name):
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )


def initialize_watchtower_schema() -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchtowers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                source_version_id INTEGER,
                activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchtowers_user_id
            ON watchtowers(user_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchtower_id INTEGER NOT NULL,
                clause_id TEXT NOT NULL,
                clause_title TEXT,
                item_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                requirement_text TEXT,
                trigger_type TEXT NOT NULL,
                rule_json TEXT,
                evidence_json TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (watchtower_id) REFERENCES watchtowers(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_items_watchtower_id
            ON watch_items(watchtower_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchtower_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT,
                description TEXT NOT NULL,
                observed_value REAL,
                observed_unit TEXT,
                evidence_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (watchtower_id) REFERENCES watchtowers(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_events_watchtower_id
            ON watch_events(watchtower_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchtower_id INTEGER NOT NULL,
                watch_item_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                result TEXT NOT NULL,
                explanation TEXT NOT NULL,
                evidence_json TEXT,
                evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(watch_item_id, event_id),
                FOREIGN KEY (watchtower_id) REFERENCES watchtowers(id) ON DELETE CASCADE,
                FOREIGN KEY (watch_item_id) REFERENCES watch_items(id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES watch_events(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_evaluations_event_id
            ON watch_evaluations(event_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchtower_id INTEGER NOT NULL,
                watch_item_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                due_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (watchtower_id) REFERENCES watchtowers(id) ON DELETE CASCADE,
                FOREIGN KEY (watch_item_id) REFERENCES watch_items(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_alerts_watchtower_id
            ON watch_alerts(watchtower_id)
        """)

        # --------------------------------------------------------
        # Watchtower user decisions
        # --------------------------------------------------------
        # A Watchtower evaluation answers: "What did the contract state
        # mean when this event occurred?"
        #
        # A Watchtower decision answers: "What did the user choose to do
        # about that finding?"
        #
        # Decisions are intentionally stored separately from evaluations
        # and alerts so we preserve the distinction between system-detected
        # facts and user-selected business actions.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchtower_id INTEGER NOT NULL,
                watch_item_id INTEGER NOT NULL,
                decision TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                due_at TEXT,
                follow_up_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (watchtower_id) REFERENCES watchtowers(id) ON DELETE CASCADE,
                FOREIGN KEY (watch_item_id) REFERENCES watch_items(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_decisions_watchtower_id
            ON watch_decisions(watchtower_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_decisions_item_id
            ON watch_decisions(watch_item_id)
        """)

        watch_decision_columns = {
            "watchtower_id": "INTEGER",
            "watch_item_id": "INTEGER",
            "decision": "TEXT",
            "status": "TEXT DEFAULT 'active'",
            "due_at": "TEXT",
            "follow_up_at": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for name, sql in watch_decision_columns.items():
            _ensure_column(cursor, "watch_decisions", name, sql)

        # --------------------------------------------------------
        # Backward-compatible schema migration
        # --------------------------------------------------------
        # The project has already created Watchtower tables in earlier
        # iterations. CREATE TABLE IF NOT EXISTS does not modify an
        # existing table, so every runtime-used column is explicitly
        # ensured here.
        watchtower_columns = {
            "contract_id": "INTEGER",
            "user_id": "INTEGER",
            "status": "TEXT DEFAULT 'active'",
            "source_version_id": "INTEGER",
            "activated_at": "TEXT",
            "updated_at": "TEXT",
        }
        for name, sql in watchtower_columns.items():
            _ensure_column(cursor, "watchtowers", name, sql)

        watch_item_columns = {
            "watchtower_id": "INTEGER",
            "clause_id": "TEXT",
            "clause_title": "TEXT",
            "item_type": "TEXT",
            "title": "TEXT",
            "description": "TEXT",
            "requirement_text": "TEXT",
            "trigger_type": "TEXT",
            "rule_json": "TEXT",
            "evidence_json": "TEXT",
            "status": "TEXT DEFAULT 'active'",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for name, sql in watch_item_columns.items():
            _ensure_column(cursor, "watch_items", name, sql)

        watch_event_columns = {
            "watchtower_id": "INTEGER",
            "event_type": "TEXT",
            "event_date": "TEXT",
            "description": "TEXT",
            "observed_value": "REAL",
            "observed_unit": "TEXT",
            "evidence_json": "TEXT",
            "created_at": "TEXT",
        }
        for name, sql in watch_event_columns.items():
            _ensure_column(cursor, "watch_events", name, sql)

        evaluation_columns = {
            "watchtower_id": "INTEGER",
            "watch_item_id": "INTEGER",
            "event_id": "INTEGER",
            "result": "TEXT",
            "explanation": "TEXT",
            "evidence_json": "TEXT",
            "evaluated_at": "TEXT",
        }
        for name, sql in evaluation_columns.items():
            _ensure_column(cursor, "watch_evaluations", name, sql)

        alert_columns = {
            "watchtower_id": "INTEGER",
            "watch_item_id": "INTEGER",
            "alert_type": "TEXT",
            "title": "TEXT",
            "message": "TEXT",
            "status": "TEXT DEFAULT 'open'",
            "due_at": "TEXT",
            "created_at": "TEXT",
        }
        for name, sql in alert_columns.items():
            _ensure_column(cursor, "watch_alerts", name, sql)

        # Backfill timestamps/status fields where older rows predate the
        # current schema.
        cursor.execute("""
            UPDATE watchtowers
            SET status = COALESCE(status, 'active'),
                activated_at = COALESCE(activated_at, CURRENT_TIMESTAMP),
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        """)
        cursor.execute("""
            UPDATE watch_items
            SET status = COALESCE(status, 'active'),
                created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        """)
        cursor.execute("""
            UPDATE watch_events
            SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)
        """)
        cursor.execute("""
            UPDATE watch_evaluations
            SET evaluated_at = COALESCE(evaluated_at, CURRENT_TIMESTAMP)
        """)
        cursor.execute("""
            UPDATE watch_alerts
            SET status = COALESCE(status, 'open'),
                created_at = COALESCE(created_at, CURRENT_TIMESTAMP)
        """)

        # Runtime queries rely on these indexes. They are safe even when
        # older tables lacked them.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_events_watchtower_id
            ON watch_events(watchtower_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_evaluations_event_id
            ON watch_evaluations(event_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_alerts_watchtower_id
            ON watch_alerts(watchtower_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_decisions_watchtower_id
            ON watch_decisions(watchtower_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_decisions_item_id
            ON watch_decisions(watch_item_id)
        """)

        cursor.execute("""
            UPDATE watch_decisions
            SET status = COALESCE(status, 'active'),
                created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        """)

        connection.commit()
    finally:
        connection.close()
