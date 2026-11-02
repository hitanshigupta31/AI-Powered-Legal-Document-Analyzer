# ============================================================
# CLAUSEGUARD - DATABASE
# ============================================================

from pathlib import Path
import sqlite3
from typing import Optional


# ------------------------------------------------------------
# DATABASE LOCATION
# ------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent

DATABASE_PATH = PROJECT_DIR / "clauseguard.db"


# ------------------------------------------------------------
# CONNECTION
# ------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


# ------------------------------------------------------------
# INITIALIZE DATABASE
# ------------------------------------------------------------

def initialize_database() -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_token_hash
            ON sessions(token_hash)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id
            ON sessions(user_id)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT,
                original_text TEXT NOT NULL,
                clauses_json TEXT NOT NULL,
                summary_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_contracts_user_id
            ON contracts(user_id)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                answer_type TEXT,
                grounded INTEGER DEFAULT 0,
                sources_json TEXT,
                follow_up_suggestions_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_contract_id
            ON chat_messages(contract_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id
            ON chat_messages(user_id)
            """
        )

        connection.commit()

    finally:

        connection.close()


# ------------------------------------------------------------
# USER HELPERS
# ------------------------------------------------------------

def create_user(
    name: str,
    email: str,
    password_hash: str
) -> int:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO users (
                name,
                email,
                password_hash
            )
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                password_hash
            )
        )

        connection.commit()

        return int(cursor.lastrowid)

    finally:

        connection.close()


def get_user_by_email(
    email: str
) -> Optional[sqlite3.Row]:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                password_hash,
                created_at
            FROM users
            WHERE email = ?
            LIMIT 1
            """,
            (email,)
        )

        return cursor.fetchone()

    finally:

        connection.close()


def get_user_by_id(
    user_id: int
) -> Optional[sqlite3.Row]:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                created_at
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (user_id,)
        )

        return cursor.fetchone()

    finally:

        connection.close()


# ------------------------------------------------------------
# SESSION HELPERS
# ------------------------------------------------------------

def create_session(
    token_hash: str,
    user_id: int,
    expires_at: str
) -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO sessions (
                token_hash,
                user_id,
                expires_at
            )
            VALUES (?, ?, ?)
            """,
            (
                token_hash,
                user_id,
                expires_at
            )
        )

        connection.commit()

    finally:

        connection.close()


def get_session_user_id(
    token_hash: str
) -> Optional[int]:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                user_id
            FROM sessions
            WHERE token_hash = ?
              AND expires_at > CURRENT_TIMESTAMP
            LIMIT 1
            """,
            (token_hash,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return int(row["user_id"])

    finally:

        connection.close()


def delete_session(
    token_hash: str
) -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM sessions
            WHERE token_hash = ?
            """,
            (token_hash,)
        )

        connection.commit()

    finally:

        connection.close()


def delete_expired_sessions() -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM sessions
            WHERE expires_at <= CURRENT_TIMESTAMP
            """
        )

        connection.commit()

    finally:

        connection.close()


# ------------------------------------------------------------
# CONTRACT HELPERS
# ------------------------------------------------------------


def save_contract(
    user_id: int,
    filename: Optional[str],
    original_text: str,
    clauses: list,
    summary: dict
) -> int:
    import json
    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO contracts (
                user_id,
                filename,
                original_text,
                clauses_json,
                summary_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                filename,
                original_text,
                json.dumps(clauses, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False) if summary else None
            )
        )

        connection.commit()

        return int(cursor.lastrowid)

    finally:

        connection.close()


def get_contract(
    contract_id: int,
    user_id: int
) -> Optional[sqlite3.Row]:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                user_id,
                filename,
                original_text,
                clauses_json,
                summary_json,
                created_at
            FROM contracts
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (contract_id, user_id)
        )

        return cursor.fetchone()

    finally:

        connection.close()


def get_user_contracts(
    user_id: int,
    limit: int = 10
) -> list:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                filename,
                created_at
            FROM contracts
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )

        return cursor.fetchall()

    finally:

        connection.close()


# ------------------------------------------------------------
# CHAT MESSAGE HELPERS
# ------------------------------------------------------------


def save_chat_message(
    contract_id: int,
    user_id: int,
    role: str,
    content: str,
    answer_type: Optional[str] = None,
    grounded: bool = False,
    sources: Optional[list] = None,
    follow_up_suggestions: Optional[list] = None
) -> int:
    import json
    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO chat_messages (
                contract_id,
                user_id,
                role,
                content,
                answer_type,
                grounded,
                sources_json,
                follow_up_suggestions_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract_id,
                user_id,
                role,
                content,
                answer_type,
                1 if grounded else 0,
                json.dumps(sources, ensure_ascii=False) if sources else None,
                json.dumps(follow_up_suggestions, ensure_ascii=False) if follow_up_suggestions else None
            )
        )

        connection.commit()

        return int(cursor.lastrowid)

    finally:

        connection.close()


def get_chat_history(
    contract_id: int,
    user_id: int,
    limit: int = 20
) -> list:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                role,
                content,
                answer_type,
                grounded,
                sources_json,
                follow_up_suggestions_json,
                created_at
            FROM chat_messages
            WHERE contract_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (contract_id, user_id, limit)
        )

        rows = cursor.fetchall()
        # Return in chronological order (oldest first)
        return list(reversed(rows))

    finally:

        connection.close()


def delete_chat_history(
    contract_id: int,
    user_id: int
) -> None:

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM chat_messages
            WHERE contract_id = ? AND user_id = ?
            """,
            (contract_id, user_id)
        )

        connection.commit()

    finally:

        connection.close()