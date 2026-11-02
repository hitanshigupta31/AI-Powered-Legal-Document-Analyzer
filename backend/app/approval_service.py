# ============================================================
# CLAUSEGUARD - CHANGE APPROVAL / EXACT APPLICATION SERVICE
# Feature 3 / Layer 4
# ============================================================
"""
Human approval and deterministic application of exact Change Objects.

Flow:

    Layer 3 proposal
        -> persist exact Change Object
        -> founder approves/rejects
        -> approved Change Object is applied exactly as stored
        -> revised contract version + change ledger

This service never calls the LLM.

Important guarantees:
    - approval applies the exact stored proposed_text
    - no proposal regeneration
    - original contract row is never modified
    - clause integrity is checked before application
    - revisions are stored separately
    - applied changes are written to a change ledger
"""

import json
import sqlite3
from typing import Any, Optional

from app.database import get_connection
from app.pipeline import analyze_document


# ============================================================
# SCHEMA / MIGRATION
# ============================================================

BASE_DRAFT_CHANGE_COLUMNS = {
    "clause_title": "TEXT",
    "source": "TEXT",
    "requirements_json": "TEXT",
    "user_requirements_json": "TEXT",
}


def _table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    cursor = connection.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {
        str(row[1])
        for row in cursor.fetchall()
    }


def initialize_approval_schema() -> None:
    """
    Create Layer 4 persistence tables and add missing columns
    to an existing draft_changes table when necessary.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ----------------------------------------------------
        # Exact draft proposals.
        # ----------------------------------------------------
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS draft_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                change_id TEXT NOT NULL,
                clause_id TEXT NOT NULL,
                clause_title TEXT,
                change_type TEXT,
                source TEXT NOT NULL DEFAULT 'ai_generated',
                negotiation_objective TEXT NOT NULL,
                original_text TEXT NOT NULL,
                proposed_text TEXT NOT NULL,
                reason TEXT,
                evidence_json TEXT,
                preserved_facts_json TEXT,
                risk_notes_json TEXT,
                requirements_json TEXT,
                user_requirements_json TEXT,
                change_recommended INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'proposed',
                validated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(contract_id, change_id),
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        # ----------------------------------------------------
        # Lightweight migration when an older draft_changes
        # table already exists.
        # ----------------------------------------------------
        existing = _table_columns(
            connection,
            "draft_changes",
        )

        version_columns = _table_columns(
            connection,
            "contract_versions",
        )

        if "summary_json" not in version_columns:
            cursor.execute(
                """
                ALTER TABLE contract_versions
                ADD COLUMN summary_json TEXT
                """
            )

        for column_name, column_type in BASE_DRAFT_CHANGE_COLUMNS.items():
            if column_name not in existing:
                cursor.execute(
                    f"""
                    ALTER TABLE draft_changes
                    ADD COLUMN {column_name} {column_type}
                    """
                )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_draft_changes_contract_id
            ON draft_changes(contract_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_draft_changes_user_id
            ON draft_changes(user_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_draft_changes_status
            ON draft_changes(status)
            """
        )

        # ----------------------------------------------------
        # Revised contract versions.
        #
        # The source contract row remains immutable.
        # Version 1 is the original contract implicitly.
        # First generated revision is version 2.
        # ----------------------------------------------------
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contract_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                parent_version_id INTEGER,
                full_text TEXT NOT NULL,
                clauses_json TEXT NOT NULL,
                summary_json TEXT,
                applied_change_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(contract_id, version_number),
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (parent_version_id) REFERENCES contract_versions(id)
                    ON DELETE SET NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_contract_versions_contract_id
            ON contract_versions(contract_id)
            """
        )

        # ----------------------------------------------------
        # Human-readable change ledger.
        # ----------------------------------------------------
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS change_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                revision_id INTEGER NOT NULL,
                change_id TEXT NOT NULL,
                clause_id TEXT NOT NULL,
                clause_title TEXT,
                action TEXT NOT NULL,
                original_text TEXT NOT NULL,
                applied_text TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (revision_id) REFERENCES contract_versions(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_change_ledger_contract_id
            ON change_ledger(contract_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_change_ledger_revision_id
            ON change_ledger(revision_id)
            """
        )

        connection.commit()

    finally:
        connection.close()

    # Repair revisions produced by the earlier non-cumulative
    # implementation, once the required tables exist.
    _repair_non_cumulative_revisions()


# ============================================================
# JSON HELPERS
# ============================================================

def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default

    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _row_to_change(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "contract_id": row["contract_id"],
        "user_id": row["user_id"],
        "change_id": row["change_id"],
        "clause_id": row["clause_id"],
        "clause_title": row["clause_title"],
        "change_type": row["change_type"],
        "source": row["source"] or "ai_generated",
        "negotiation_objective": row["negotiation_objective"],
        "original_text": row["original_text"],
        "proposed_text": row["proposed_text"],
        "reason": row["reason"],
        "evidence": _json_loads(row["evidence_json"], []),
        "preserved_facts": _json_loads(row["preserved_facts_json"], []),
        "risk_notes": _json_loads(row["risk_notes_json"], []),
        "requirements_addressed": _json_loads(
            row["requirements_json"],
            [],
        ),
        "user_requirements": _json_loads(
            row["user_requirements_json"],
            [],
        ),
        "change_recommended": bool(
            row["change_recommended"]
        ),
        "status": row["status"],
        "validated": bool(row["validated"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ============================================================
# DRAFT PROPOSAL PERSISTENCE
# ============================================================

def persist_change_proposal(
    contract_id: int,
    user_id: int,
    change: dict,
) -> dict:
    """
    Persist the exact Layer 3 Change Object.

    Re-running the same Layer 3 request is allowed only while the
    existing proposal remains in 'proposed' state.
    """

    change_id = str(
        change.get("change_id", "")
    ).strip()

    if not change_id:
        raise ValueError(
            "Cannot persist a change without change_id."
        )

    if not bool(change.get("validated", False)):
        raise ValueError(
            "Only validated changes can be persisted."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                status
            FROM draft_changes
            WHERE contract_id = ?
              AND user_id = ?
              AND change_id = ?
            LIMIT 1
            """,
            (
                contract_id,
                user_id,
                change_id,
            )
        )

        existing = cursor.fetchone()

        if existing is not None:
            current_status = str(
                existing["status"]
            )

            if current_status in {
                "approved",
                "applied",
            }:
                raise ValueError(
                    f"Change '{change_id}' is already {current_status} "
                    "and cannot be overwritten."
                )

            # Re-running Layer 3 before approval simply replaces the
            # still-proposed object with the newly generated object.
            cursor.execute(
                """
                DELETE FROM draft_changes
                WHERE contract_id = ?
                  AND user_id = ?
                  AND change_id = ?
                """,
                (
                    contract_id,
                    user_id,
                    change_id,
                )
            )

        cursor.execute(
            """
            INSERT INTO draft_changes (
                contract_id,
                user_id,
                change_id,
                clause_id,
                clause_title,
                change_type,
                source,
                negotiation_objective,
                original_text,
                proposed_text,
                reason,
                evidence_json,
                preserved_facts_json,
                risk_notes_json,
                requirements_json,
                user_requirements_json,
                change_recommended,
                status,
                validated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract_id,
                user_id,
                change_id,
                str(change.get("clause_id", "")),
                change.get("clause_title"),
                change.get("change_type"),
                change.get("source", "ai_generated"),
                change.get(
                    "negotiation_objective",
                    "founder_directed",
                ),
                str(change.get("original_text", "")),
                str(change.get("proposed_text", "")),
                change.get("reason"),
                json.dumps(
                    change.get("evidence", []),
                    ensure_ascii=False,
                ),
                json.dumps(
                    change.get("preserved_facts", []),
                    ensure_ascii=False,
                ),
                json.dumps(
                    change.get("risk_notes", []),
                    ensure_ascii=False,
                ),
                json.dumps(
                    change.get(
                        "requirements_addressed",
                        [],
                    ),
                    ensure_ascii=False,
                ),
                json.dumps(
                    change.get(
                        "user_requirements",
                        [],
                    ),
                    ensure_ascii=False,
                ),
                1 if change.get(
                    "change_recommended",
                    True,
                ) else 0,
                "proposed",
                1,
            )
        )

        connection.commit()

    finally:
        connection.close()

    saved = get_draft_change(
        contract_id=contract_id,
        user_id=user_id,
        change_id=change_id,
    )

    if saved is None:
        raise RuntimeError(
            "Failed to reload the persisted draft change."
        )

    return saved


def get_draft_changes(
    contract_id: int,
    user_id: int,
) -> list[dict]:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                contract_id,
                user_id,
                change_id,
                clause_id,
                clause_title,
                change_type,
                source,
                negotiation_objective,
                original_text,
                proposed_text,
                reason,
                evidence_json,
                preserved_facts_json,
                risk_notes_json,
                requirements_json,
                user_requirements_json,
                change_recommended,
                status,
                validated,
                created_at,
                updated_at
            FROM draft_changes
            WHERE contract_id = ?
              AND user_id = ?
            ORDER BY id ASC
            """,
            (
                contract_id,
                user_id,
            )
        )

        return [
            _row_to_change(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


def get_draft_change(
    contract_id: int,
    user_id: int,
    change_id: str,
) -> Optional[dict]:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                contract_id,
                user_id,
                change_id,
                clause_id,
                clause_title,
                change_type,
                source,
                negotiation_objective,
                original_text,
                proposed_text,
                reason,
                evidence_json,
                preserved_facts_json,
                risk_notes_json,
                requirements_json,
                user_requirements_json,
                change_recommended,
                status,
                validated,
                created_at,
                updated_at
            FROM draft_changes
            WHERE contract_id = ?
              AND user_id = ?
              AND change_id = ?
            LIMIT 1
            """,
            (
                contract_id,
                user_id,
                change_id,
            )
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return _row_to_change(row)

    finally:
        connection.close()


# ============================================================
# APPROVAL / REJECTION
# ============================================================

def set_change_status(
    contract_id: int,
    user_id: int,
    change_id: str,
    new_status: str,
) -> dict:
    if new_status not in {
        "approved",
        "rejected",
    }:
        raise ValueError(
            "Invalid approval status."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                status,
                validated
            FROM draft_changes
            WHERE contract_id = ?
              AND user_id = ?
              AND change_id = ?
            LIMIT 1
            """,
            (
                contract_id,
                user_id,
                change_id,
            )
        )

        row = cursor.fetchone()

        if row is None:
            raise ValueError(
                f"Draft change '{change_id}' was not found."
            )

        status = str(row["status"])

        if status != "proposed":
            raise ValueError(
                f"Draft change '{change_id}' cannot be {new_status}; "
                f"current status is '{status}'."
            )

        if new_status == "approved" and not bool(
            row["validated"]
        ):
            raise ValueError(
                f"Draft change '{change_id}' has not passed validation."
            )

        cursor.execute(
            """
            UPDATE draft_changes
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE contract_id = ?
              AND user_id = ?
              AND change_id = ?
              AND status = 'proposed'
            """,
            (
                new_status,
                contract_id,
                user_id,
                change_id,
            )
        )

        changed = cursor.rowcount > 0

        connection.commit()

    finally:
        connection.close()

    if not changed:
        raise ValueError(
            f"Draft change '{change_id}' was not updated."
        )

    result = get_draft_change(
        contract_id=contract_id,
        user_id=user_id,
        change_id=change_id,
    )

    if result is None:
        raise RuntimeError(
            "Failed to reload updated draft change."
        )

    return result


def _get_latest_revision_row(
    connection,
    contract_id: int,
    user_id: int,
):
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            version_number,
            full_text,
            clauses_json,
            summary_json
        FROM contract_versions
        WHERE contract_id = ?
          AND user_id = ?
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (
            contract_id,
            user_id,
        )
    )

    return cursor.fetchone()


def _repair_non_cumulative_revisions() -> None:
    """
    Development-safe migration for revisions created by the earlier
    Layer 4 implementation.

    Older revisions were incorrectly built from the immutable original
    contract instead of their parent revision. This function reconstructs
    each affected revision from its parent plus that revision's own ledger
    changes, then re-runs deterministic analysis.

    The change ledger itself is preserved.
    The operation is idempotent because reconstructed text is checked
    against the stored revision before an update is committed.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                contract_id,
                user_id,
                version_number,
                parent_version_id,
                full_text,
                clauses_json,
                summary_json
            FROM contract_versions
            ORDER BY contract_id ASC, version_number ASC
            """
        )

        revision_rows = cursor.fetchall()

        for revision in revision_rows:
            parent_id = revision["parent_version_id"]

            if parent_id is None:
                continue

            # Load parent state.
            cursor.execute(
                """
                SELECT
                    id,
                    full_text,
                    clauses_json
                FROM contract_versions
                WHERE id = ?
                LIMIT 1
                """,
                (parent_id,)
            )

            parent = cursor.fetchone()

            if parent is None:
                continue

            parent_clauses = _json_loads(
                parent["clauses_json"],
                [],
            )

            if not isinstance(parent_clauses, list):
                continue

            # Load exactly the changes recorded for this revision.
            cursor.execute(
                """
                SELECT
                    change_id,
                    clause_id,
                    clause_title,
                    original_text,
                    applied_text
                FROM change_ledger
                WHERE revision_id = ?
                ORDER BY id ASC
                """,
                (revision["id"],)
            )

            ledger_rows = cursor.fetchall()

            if not ledger_rows:
                continue

            changes = [
                {
                    "change_id": row["change_id"],
                    "clause_id": row["clause_id"],
                    "clause_title": row["clause_title"],
                    "original_text": row["original_text"],
                    "proposed_text": row["applied_text"],
                }
                for row in ledger_rows
            ]

            # Rebuild from parent instead of from original contract.
            try:
                reconstructed_full_text, reconstructed_clauses = (
                    _build_revised_contract(
                        original_text=parent["full_text"],
                        clauses=parent_clauses,
                        changes=changes,
                    )
                )
            except ValueError:
                # If the revision already reflects its parent correctly,
                # the exact replacement will fail because the ledger's
                # original text may no longer be present. Leave it alone.
                continue

            reconstructed_clauses, reconstructed_summary = (
                _reanalyze_revised_contract(
                    revised_full_text=reconstructed_full_text,
                    revised_clauses=reconstructed_clauses,
                    changes=changes,
                )
            )

            # Only write if the revision actually differs.
            current_clauses = _json_loads(
                revision["clauses_json"],
                [],
            )

            current_full_text = str(
                revision["full_text"]
            )

            if (
                current_full_text == reconstructed_full_text
                and current_clauses == reconstructed_clauses
            ):
                continue

            cursor.execute(
                """
                UPDATE contract_versions
                SET full_text = ?,
                    clauses_json = ?,
                    summary_json = ?
                WHERE id = ?
                """,
                (
                    reconstructed_full_text,
                    json.dumps(
                        reconstructed_clauses,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        reconstructed_summary,
                        ensure_ascii=False,
                    ),
                    revision["id"],
                )
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# EXACT REVISION APPLICATION
# ============================================================

def _build_revision_summary(clauses: list) -> dict:
    high = sum(
        1
        for clause in clauses
        if str(
            clause.get(
                "risk_level",
                "",
            )
        ).upper() == "HIGH"
    )

    medium = sum(
        1
        for clause in clauses
        if str(
            clause.get(
                "risk_level",
                "",
            )
        ).upper() == "MEDIUM"
    )

    low = sum(
        1
        for clause in clauses
        if str(
            clause.get(
                "risk_level",
                "",
            )
        ).upper() == "LOW"
    )

    scores = [
        float(
            clause.get(
                "risk_score",
                0,
            )
        )
        for clause in clauses
        if isinstance(
            clause.get(
                "risk_score",
            ),
            (int, float),
        )
    ]

    return {
        "overall_score": (
            round(sum(scores) / len(scores))
            if scores
            else 0
        ),
        "high_risk_count": high,
        "medium_risk_count": medium,
        "low_risk_count": low,
        "attention_count": high + medium,
        "priority_findings": sorted(
            clauses,
            key=lambda clause: float(
                clause.get(
                    "risk_score",
                    0,
                )
            ),
            reverse=True,
        )[:5],
    }


def _reanalyze_revised_contract(
    revised_full_text: str,
    revised_clauses: list,
    changes: list[dict],
) -> tuple[list, dict]:
    """
    Re-run ClauseGuard analysis on the revised contract text.

    The revision is only committed when:
        1. the analyzer returns clauses,
        2. every changed clause still exists,
        3. analyzed clause text equals the exact approved text.

    This prevents stale risk metadata from the original contract
    from being carried into the revised version.
    """

    analysed_clauses = analyze_document(
        revised_full_text
    )

    if not isinstance(
        analysed_clauses,
        list,
    ) or not analysed_clauses:
        raise ValueError(
            "Re-analysis produced no clauses for the revised contract."
        )

    applied_metadata = {
        str(
            clause.get(
                "clause_id",
                "",
            )
        ): clause
        for clause in revised_clauses
    }

    enriched_clauses = []

    for clause in analysed_clauses:
        enriched = dict(clause)

        clause_id = str(
            clause.get(
                "clause_id",
                "",
            )
        )

        source_clause = applied_metadata.get(
            clause_id
        )

        if source_clause is not None and source_clause.get(
            "draft_change_applied"
        ):
            enriched["draft_change_applied"] = True
            enriched["draft_change_id"] = source_clause.get(
                "draft_change_id"
            )

        enriched_clauses.append(
            enriched
        )

    for change in changes:
        clause_id = str(
            change["clause_id"]
        )

        analysed_clause = next(
            (
                clause
                for clause in enriched_clauses
                if str(
                    clause.get(
                        "clause_id",
                        "",
                    )
                ) == clause_id
            ),
            None,
        )

        if analysed_clause is None:
            raise ValueError(
                f"Re-analysis could not resolve applied clause "
                f"'{clause_id}' for change '{change['change_id']}'."
            )

        if str(
            analysed_clause.get(
                "text",
                "",
            )
        ) != str(
            change["proposed_text"]
        ):
            raise ValueError(
                f"Re-analysis changed the text representation of "
                f"clause '{clause_id}'. The revision was not stored."
            )

    return (
        enriched_clauses,
        _build_revision_summary(
            enriched_clauses
        ),
    )


def _build_revised_contract(
    original_text: str,
    clauses: list,
    changes: list[dict],
) -> tuple[str, list]:
    """
    Apply exact stored replacements against the exact source text.

    Every target clause must:
        - exist
        - still match the stored original_text
        - be selected at most once
    """

    revised_text = str(
        original_text
    )

    revised_clauses = [
        dict(clause)
        for clause in clauses
    ]

    seen_clause_ids: set[str] = set()

    # Validate all changes before mutating the working copy.
    for change in changes:
        clause_id = str(
            change["clause_id"]
        )

        if clause_id in seen_clause_ids:
            raise ValueError(
                f"Multiple approved changes target clause '{clause_id}'."
            )

        seen_clause_ids.add(
            clause_id
        )

        target_index = None

        for index, clause in enumerate(
            revised_clauses
        ):
            if str(
                clause.get(
                    "clause_id",
                    "",
                )
            ) == clause_id:
                target_index = index
                break

        if target_index is None:
            raise ValueError(
                f"Clause '{clause_id}' for change "
                f"'{change['change_id']}' was not found."
            )

        current_clause_text = str(
            revised_clauses[target_index].get(
                "text",
                "",
            )
        )

        stored_original = str(
            change["original_text"]
        )

        if current_clause_text != stored_original:
            raise ValueError(
                f"Clause '{clause_id}' has changed since "
                f"change '{change['change_id']}' was proposed. "
                "Re-run the improvement analysis."
            )

        proposed_text = str(
            change["proposed_text"]
        ).strip()

        if not proposed_text:
            raise ValueError(
                f"Change '{change['change_id']}' has empty proposed text."
            )

        occurrence_count = revised_text.count(
            stored_original
        )

        if occurrence_count != 1:
            raise ValueError(
                f"Could not deterministically replace clause '{clause_id}': "
                f"expected exactly one occurrence of the original text, "
                f"found {occurrence_count}."
            )

        revised_text = revised_text.replace(
            stored_original,
            proposed_text,
            1,
        )

        revised_clause = dict(
            revised_clauses[target_index]
        )

        revised_clause["text"] = proposed_text
        revised_clause["draft_change_applied"] = True
        revised_clause["draft_change_id"] = change[
            "change_id"
        ]

        revised_clauses[target_index] = revised_clause

    return (
        revised_text,
        revised_clauses,
    )


def apply_approved_changes_exact(
    contract_id: int,
    user_id: int,
    approved_change_ids: list[str],
) -> dict:
    """
    Create a new contract revision from exact approved proposals.

    The contracts table is never updated.
    """

    approved_change_ids = [
        str(item).strip()
        for item in approved_change_ids
        if str(item).strip()
    ]

    if not approved_change_ids:
        raise ValueError(
            "At least one approved change must be supplied."
        )

    if len(set(approved_change_ids)) != len(
        approved_change_ids
    ):
        raise ValueError(
            "Duplicate change IDs were supplied."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ----------------------------------------------------
        # Load the immutable source contract plus the latest
        # effective revision, when one exists.
        #
        # Every new revision must be cumulative.
        # ----------------------------------------------------
        cursor.execute(
            """
            SELECT
                id,
                user_id,
                filename,
                original_text,
                clauses_json,
                summary_json
            FROM contracts
            WHERE id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (
                contract_id,
                user_id,
            )
        )

        contract_row = cursor.fetchone()

        if contract_row is None:
            raise ValueError(
                "Contract not found."
            )

        latest_revision = _get_latest_revision_row(
            connection=connection,
            contract_id=contract_id,
            user_id=user_id,
        )

        if latest_revision is None:
            base_full_text = contract_row["original_text"]
            clauses = _json_loads(
                contract_row["clauses_json"],
                [],
            )
            parent_version_id = None
        else:
            base_full_text = latest_revision["full_text"]
            clauses = _json_loads(
                latest_revision["clauses_json"],
                [],
            )
            parent_version_id = int(
                latest_revision["id"]
            )

        if not isinstance(clauses, list):
            raise ValueError(
                "Stored contract clauses are invalid."
            )

        # ----------------------------------------------------
        # Load and validate exact approved objects.
        # ----------------------------------------------------
        changes = []

        for change_id in approved_change_ids:
            cursor.execute(
                """
                SELECT
                    id,
                    contract_id,
                    user_id,
                    change_id,
                    clause_id,
                    clause_title,
                    change_type,
                    source,
                    negotiation_objective,
                    original_text,
                    proposed_text,
                    reason,
                    evidence_json,
                    preserved_facts_json,
                    risk_notes_json,
                    requirements_json,
                    user_requirements_json,
                    change_recommended,
                    status,
                    validated,
                    created_at,
                    updated_at
                FROM draft_changes
                WHERE contract_id = ?
                  AND user_id = ?
                  AND change_id = ?
                LIMIT 1
                """,
                (
                    contract_id,
                    user_id,
                    change_id,
                )
            )

            row = cursor.fetchone()

            if row is None:
                raise ValueError(
                    f"Approved change '{change_id}' was not found."
                )

            if str(row["status"]) != "approved":
                raise ValueError(
                    f"Change '{change_id}' is not approved. "
                    f"Current status: {row['status']}."
                )

            if not bool(row["validated"]):
                raise ValueError(
                    f"Change '{change_id}' did not pass validation."
                )

            changes.append(
                _row_to_change(row)
            )

        revised_full_text, revised_clauses = (
            _build_revised_contract(
                original_text=base_full_text,
                clauses=clauses,
                changes=changes,
            )
        )

        revised_clauses, revised_summary = (
            _reanalyze_revised_contract(
                revised_full_text=revised_full_text,
                revised_clauses=revised_clauses,
                changes=changes,
            )
        )

        # ----------------------------------------------------
        # Determine the next revision number.
        # The base state above already came from the latest
        # revision, so its ID is the correct parent.
        # ----------------------------------------------------
        cursor.execute(
            """
            SELECT
                version_number
            FROM contract_versions
            WHERE contract_id = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (contract_id,)
        )

        previous_version = cursor.fetchone()

        if previous_version is None:
            version_number = 2
        else:
            version_number = (
                int(previous_version["version_number"])
                + 1
            )

        # ----------------------------------------------------
        # Create immutable revision.
        # ----------------------------------------------------
        cursor.execute(
            """
            INSERT INTO contract_versions (
                contract_id,
                user_id,
                version_number,
                parent_version_id,
                full_text,
                clauses_json,
                summary_json,
                applied_change_ids_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract_id,
                user_id,
                version_number,
                parent_version_id,
                revised_full_text,
                json.dumps(
                    revised_clauses,
                    ensure_ascii=False,
                ),
                json.dumps(
                    revised_summary,
                    ensure_ascii=False,
                ),
                json.dumps(
                    approved_change_ids,
                    ensure_ascii=False,
                ),
            )
        )

        revision_id = int(
            cursor.lastrowid
        )

        # ----------------------------------------------------
        # Write one ledger row per applied proposal.
        # ----------------------------------------------------
        for change in changes:
            cursor.execute(
                """
                INSERT INTO change_ledger (
                    contract_id,
                    user_id,
                    revision_id,
                    change_id,
                    clause_id,
                    clause_title,
                    action,
                    original_text,
                    applied_text,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    user_id,
                    revision_id,
                    change["change_id"],
                    change["clause_id"],
                    change.get("clause_title"),
                    "applied",
                    change["original_text"],
                    change["proposed_text"],
                    change.get("reason"),
                )
            )

        # ----------------------------------------------------
        # Only after the new revision and ledger have been
        # written successfully do we mark the proposals applied.
        # ----------------------------------------------------
        for change in changes:
            cursor.execute(
                """
                UPDATE draft_changes
                SET status = 'applied',
                    updated_at = CURRENT_TIMESTAMP
                WHERE contract_id = ?
                  AND user_id = ?
                  AND change_id = ?
                  AND status = 'approved'
                """,
                (
                    contract_id,
                    user_id,
                    change["change_id"],
                )
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    f"Could not mark change '{change['change_id']}' "
                    "as applied."
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return {
        "success": True,
        "contract": {
            "id": contract_id,
            "filename": contract_row["filename"] or "Unknown",
        },
        "revision": {
            "id": revision_id,
            "version_number": version_number,
            "parent_version_id": parent_version_id,
            "clause_count": len(revised_clauses),
            "summary": revised_summary,
        },
        "applied_changes": [
            {
                "change_id": change["change_id"],
                "clause_id": change["clause_id"],
                "clause_title": change.get("clause_title"),
                "original_text": change["original_text"],
                "applied_text": change["proposed_text"],
                "reason": change.get("reason"),
            }
            for change in changes
        ],
        "revised_clauses": [
            clause
            for clause in revised_clauses
            if clause.get("draft_change_applied")
        ],
        "original_contract_preserved": True,
    }


# ============================================================
# REVISION / LEDGER READ APIs
# ============================================================

def get_contract_revisions(
    contract_id: int,
    user_id: int,
) -> list[dict]:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                contract_id,
                version_number,
                parent_version_id,
                summary_json,
                applied_change_ids_json,
                created_at
            FROM contract_versions
            WHERE contract_id = ?
              AND user_id = ?
            ORDER BY version_number DESC
            """,
            (
                contract_id,
                user_id,
            )
        )

        return [
            {
                "id": row["id"],
                "contract_id": row["contract_id"],
                "version_number": row["version_number"],
                "parent_version_id": row["parent_version_id"],
                "summary": _json_loads(
                    row["summary_json"],
                    {},
                ),
                "applied_change_ids": _json_loads(
                    row["applied_change_ids_json"],
                    [],
                ),
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


def get_contract_revision(
    contract_id: int,
    user_id: int,
    revision_id: int,
) -> Optional[dict]:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                contract_id,
                user_id,
                version_number,
                parent_version_id,
                full_text,
                clauses_json,
                summary_json,
                applied_change_ids_json,
                created_at
            FROM contract_versions
            WHERE id = ?
              AND contract_id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (
                revision_id,
                contract_id,
                user_id,
            )
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "contract_id": row["contract_id"],
            "version_number": row["version_number"],
            "parent_version_id": row["parent_version_id"],
            "full_text": row["full_text"],
            "clauses": _json_loads(
                row["clauses_json"],
                [],
            ),
            "summary": _json_loads(
                row["summary_json"],
                {},
            ),
            "applied_change_ids": _json_loads(
                row["applied_change_ids_json"],
                [],
            ),
            "created_at": row["created_at"],
        }

    finally:
        connection.close()


def get_change_ledger(
    contract_id: int,
    user_id: int,
) -> list[dict]:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                contract_id,
                revision_id,
                change_id,
                clause_id,
                clause_title,
                action,
                original_text,
                applied_text,
                reason,
                created_at
            FROM change_ledger
            WHERE contract_id = ?
              AND user_id = ?
            ORDER BY id ASC
            """,
            (
                contract_id,
                user_id,
            )
        )

        return [
            {
                "id": row["id"],
                "contract_id": row["contract_id"],
                "revision_id": row["revision_id"],
                "change_id": row["change_id"],
                "clause_id": row["clause_id"],
                "clause_title": row["clause_title"],
                "action": row["action"],
                "original_text": row["original_text"],
                "applied_text": row["applied_text"],
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()
