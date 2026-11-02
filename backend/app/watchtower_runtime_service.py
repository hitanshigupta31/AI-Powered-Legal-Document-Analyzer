# ============================================================
# CLAUSEGUARD - WATCHTOWER RUNTIME
# ============================================================

import json
import re
from datetime import date, timedelta
from typing import Optional

from app.database import get_contract
from app.watchtower_extractor import extract_monitorable_items
from app.watchtower_service import get_connection


def _json(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _load(value, default=None):
    if value is None:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except Exception:
        return default if default is not None else {}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _extract_days(value) -> Optional[int]:
    """Return a numeric day count from values such as '30 days'."""
    if value is None:
        return None

    match = re.search(r"\b(\d+)\s*days?\b", str(value), re.I)
    if match:
        return int(match.group(1))

    return None


def _parse_event_date(event_date: Optional[str]) -> Optional[date]:
    if not event_date:
        return None

    try:
        return date.fromisoformat(str(event_date).strip())
    except ValueError:
        return None


def _calculate_due_at(item, event_date: Optional[str], evidence: dict) -> Optional[str]:
    """
    Calculate contractual deadlines deterministically.

    Current supported deadline:
      cure_period -> event_date + cure period

    Renewal deadlines are supported when a term-end date is explicitly
    supplied in the event evidence. We never infer a term-end date from
    the model or from today's date.
    """
    rule = _load(item["rule_json"], {})
    item_type = _norm(item["item_type"])
    event_day = _parse_event_date(event_date)

    if item_type == "cure_period":
        days = _extract_days(rule.get("cure_period"))
        if days is not None and event_day is not None:
            return (event_day + timedelta(days=days)).isoformat()

    if item_type == "renewal":
        notice_days = _extract_days(rule.get("notice_period"))
        term_end = evidence.get("term_end_date")

        if notice_days is not None and term_end:
            try:
                term_end_date = date.fromisoformat(str(term_end).strip())
                return (term_end_date - timedelta(days=notice_days)).isoformat()
            except ValueError:
                return None

    return None


def _alert_title(item, result: str, due_at: Optional[str]) -> str:
    if due_at and _norm(item["item_type"]) == "cure_period":
        return f"{item['title']} deadline"

    if due_at and _norm(item["item_type"]) == "renewal":
        return f"{item['title']}"

    return item["title"]



def _event_matches_item(item, event_type: str, description: str) -> tuple[str, str]:
    event = _norm(event_type)
    desc = _norm(description)
    item_type = _norm(item["item_type"])
    trigger = _norm(item["trigger_type"])
    rule = _load(item["rule_json"], {})

    if item_type == "payment" or trigger == "recurring_due":
        if any(x in event or x in desc for x in ["payment", "invoice", "subscription", "paid"]):
            return "observed", "The recorded event matches the recurring payment obligation monitored by this item."
        if any(x in event or x in desc for x in ["missed payment", "overdue", "late payment", "failed payment"]):
            return "deviation", "The recorded event indicates a payment problem against the recurring payment obligation."
        return "not_relevant", "The event does not describe a payment-related occurrence."

    if item_type == "payment_consequence":
        if any(x in event or x in desc for x in ["late payment", "missed payment", "overdue", "failed payment"]):
            return "triggered", "The event indicates the late-payment condition described by the contract."
        if "payment" in event or "payment" in desc:
            return "observed", "A payment event was recorded, but it does not by itself establish the late-payment consequence."
        return "not_relevant", "The event does not describe a late-payment condition."

    if item_type == "renewal":
        if any(x in event or x in desc for x in ["renewal", "non-renewal", "renewal notice", "term end"]):
            return "triggered", "The event concerns the renewal or non-renewal process monitored by this item."
        return "not_relevant", "The event does not describe a renewal or term-end occurrence."

    if item_type == "cure_period":
        if any(x in event or x in desc for x in ["violation", "breach", "default", "aup"]):
            cure = rule.get("cure_period")
            suffix = f" The contract evidence records a cure/notice period of {cure}." if cure else ""
            return "triggered", "The event matches the contractual breach/violation trigger." + suffix
        if any(x in event or x in desc for x in ["cure", "notice"]):
            return "observed", "The event concerns the notice or cure process monitored by this item."
        return "not_relevant", "The event does not describe the monitored breach or notice trigger."

    if item_type == "threshold":
        return "observed", "A new event was recorded against a measurable contractual threshold; the observed value should be reviewed against the contract evidence."

    if item_type == "term_deadline":
        if any(x in event or x in desc for x in ["expiration", "expiry", "term end", "contract end"]):
            return "triggered", "The event concerns the contractual term or expiration monitored by this item."
        return "not_relevant", "The event does not describe the contractual term or expiration."

    return "observed", "The event was recorded against this active Watchtower item."


def activate_watchtower(contract_id: int, user_id: int, selected_items: list[dict]) -> dict:
    contract = get_contract(contract_id, user_id)
    if contract is None:
        raise ValueError("Contract not found.")

    preview = extract_monitorable_items(contract_id, user_id)
    available = preview["items"]

    if not selected_items:
        selected = available
    else:
        selected = []
        for requested in selected_items:
            rid = str(requested.get("item_id") or "").strip()
            clause_id = str(requested.get("clause_id") or "").strip()
            title = _norm(requested.get("title") or "")
            matches = [
                item for item in available
                if (rid and item.get("item_id") == rid)
                or (clause_id and str(item.get("clause_id")) == clause_id and (not title or _norm(item.get("title")) == title))
                or (title and _norm(item.get("title")) == title)
            ]
            if not matches:
                raise ValueError(f"Watch item not found: {requested}")
            for item in matches:
                if item not in selected:
                    selected.append(item)

    if not selected:
        raise ValueError("No monitorable provisions were detected for activation.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        source_version_id = preview["contract"].get("source_version_id")

        # Explicit upsert rather than ON CONFLICT(contract_id). Older
        # project databases may not have the UNIQUE constraint required
        # by SQLite's ON CONFLICT syntax.
        cursor.execute(
            """
            SELECT *
            FROM watchtowers
            WHERE contract_id = ?
            LIMIT 1
            """,
            (contract_id,),
        )
        watchtower = cursor.fetchone()

        if watchtower is None:
            cursor.execute(
                """
                INSERT INTO watchtowers (
                    contract_id, user_id, status,
                    source_version_id, activated_at, updated_at
                )
                VALUES (?, ?, 'active', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (contract_id, user_id, source_version_id),
            )
        else:
            cursor.execute(
                """
                UPDATE watchtowers
                SET user_id = ?,
                    status = 'active',
                    source_version_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user_id, source_version_id, watchtower["id"]),
            )

        cursor.execute(
            """
            SELECT *
            FROM watchtowers
            WHERE contract_id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (contract_id, user_id),
        )
        watchtower = cursor.fetchone()

        if watchtower is None:
            raise RuntimeError("Watchtower could not be persisted.")

        watchtower_id = int(watchtower["id"])

        cursor.execute("DELETE FROM watch_items WHERE watchtower_id = ?", (watchtower_id,))

        for item in selected:
            cursor.execute("""
                INSERT INTO watch_items (
                    watchtower_id, clause_id, clause_title, item_type, title,
                    description, requirement_text, trigger_type, rule_json,
                    evidence_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """, (
                watchtower_id,
                str(item.get("clause_id")),
                item.get("clause_title"),
                item.get("item_type"),
                item.get("title"),
                item.get("description"),
                item.get("requirement_text"),
                item.get("trigger_type"),
                _json(item.get("rule", {})),
                _json(item.get("evidence", {})),
            ))

        connection.commit()
    finally:
        connection.close()

    return get_watchtower(contract_id, user_id)


def get_watchtower(contract_id: int, user_id: int) -> Optional[dict]:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM watchtowers WHERE contract_id = ? AND user_id = ? LIMIT 1", (contract_id, user_id))
        tower = cursor.fetchone()
        if tower is None:
            return None

        cursor.execute("SELECT * FROM watch_items WHERE watchtower_id = ? ORDER BY id", (tower["id"],))
        items = []
        for row in cursor.fetchall():
            items.append({
                "id": row["id"],
                "clause_id": row["clause_id"],
                "clause_title": row["clause_title"],
                "item_type": row["item_type"],
                "title": row["title"],
                "description": row["description"],
                "requirement_text": row["requirement_text"],
                "trigger_type": row["trigger_type"],
                "rule": _load(row["rule_json"], {}),
                "evidence": _load(row["evidence_json"], {}),
                "status": row["status"],
            })

        cursor.execute("SELECT COUNT(*) AS count FROM watch_events WHERE watchtower_id = ?", (tower["id"],))
        event_count = int(cursor.fetchone()["count"])
        cursor.execute("SELECT COUNT(*) AS count FROM watch_alerts WHERE watchtower_id = ? AND status = 'open'", (tower["id"],))
        alert_count = int(cursor.fetchone()["count"])

        return {
            "watchtower": {
                "id": tower["id"],
                "contract_id": tower["contract_id"],
                "status": tower["status"],
                "activated_at": tower["activated_at"],
                "updated_at": tower["updated_at"],
                "item_count": len(items),
                "event_count": event_count,
                "open_alert_count": alert_count,
            },
            "items": items,
        }
    finally:
        connection.close()


def record_watch_event(contract_id: int, user_id: int, event_type: str, event_date: Optional[str],
                       description: str, observed_value: Optional[float], observed_unit: Optional[str], evidence: dict) -> dict:
    if not event_type.strip() or not description.strip():
        raise ValueError("event_type and description are required.")

    tower = get_watchtower(contract_id, user_id)
    if tower is None:
        raise ValueError("Watchtower is not active for this contract.")

    watchtower_id = tower["watchtower"]["id"]
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO watch_events (
                watchtower_id, event_type, event_date, description,
                observed_value, observed_unit, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (watchtower_id, event_type.strip(), event_date, description.strip(), observed_value, observed_unit, _json(evidence)))
        event_id = int(cursor.lastrowid)

        cursor.execute("SELECT * FROM watch_items WHERE watchtower_id = ? AND status = 'active' ORDER BY id", (watchtower_id,))
        evaluations = []
        alerts = []
        for item in cursor.fetchall():
            result, explanation = _event_matches_item(item, event_type, description)
            # Explicit evaluation upsert. Do not depend on a UNIQUE
            # (watch_item_id, event_id) constraint because older databases
            # may not have it.
            cursor.execute(
                """
                SELECT id
                FROM watch_evaluations
                WHERE watch_item_id = ?
                  AND event_id = ?
                LIMIT 1
                """,
                (item["id"], event_id),
            )
            existing_evaluation = cursor.fetchone()

            if existing_evaluation is None:
                cursor.execute(
                    """
                    INSERT INTO watch_evaluations (
                        watchtower_id, watch_item_id, event_id,
                        result, explanation, evidence_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        watchtower_id,
                        item["id"],
                        event_id,
                        result,
                        explanation,
                        _json(evidence),
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE watch_evaluations
                    SET result = ?,
                        explanation = ?,
                        evidence_json = ?,
                        evaluated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        result,
                        explanation,
                        _json(evidence),
                        existing_evaluation["id"],
                    ),
                )

            evaluations.append({
                "watch_item_id": item["id"],
                "clause_id": item["clause_id"],
                "title": item["title"],
                "result": result,
                "explanation": explanation,
            })

            if result in {"triggered", "deviation"}:
                due_at = _calculate_due_at(
                    item,
                    event_date,
                    evidence or {},
                )
                alert_title = _alert_title(item, result, due_at)

                # Avoid creating duplicate open alerts for the same
                # watch item and event. This keeps repeated evaluation
                # idempotent.
                cursor.execute(
                    """
                    SELECT id
                    FROM watch_alerts
                    WHERE watchtower_id = ?
                      AND watch_item_id = ?
                      AND title = ?
                      AND status = 'open'
                      AND (
                          due_at = ?
                          OR (due_at IS NULL AND ? IS NULL)
                      )
                    LIMIT 1
                    """,
                    (
                        watchtower_id,
                        item["id"],
                        alert_title,
                        due_at,
                        due_at,
                    ),
                )
                existing_alert = cursor.fetchone()

                if existing_alert is None:
                    cursor.execute("""
                        INSERT INTO watch_alerts (
                            watchtower_id, watch_item_id, alert_type,
                            title, message, status, due_at
                        ) VALUES (?, ?, ?, ?, ?, 'open', ?)
                    """, (
                        watchtower_id,
                        item["id"],
                        result,
                        alert_title,
                        explanation,
                        due_at,
                    ))

                alerts.append({
                    "watch_item_id": item["id"],
                    "alert_type": result,
                    "title": alert_title,
                    "message": explanation,
                    "due_at": due_at,
                })

        connection.commit()
    finally:
        connection.close()

    return {
        "success": True,
        "event": {
            "id": event_id,
            "event_type": event_type.strip(),
            "event_date": event_date,
            "description": description.strip(),
            "observed_value": observed_value,
            "observed_unit": observed_unit,
            "evidence": evidence,
        },
        "evaluations": evaluations,
        "alerts": alerts,
    }


def get_watch_alerts(contract_id: int, user_id: int, status: Optional[str] = None) -> list[dict]:
    """Return Watchtower alerts, optionally filtered by status."""
    tower = get_watchtower(contract_id, user_id)
    if tower is None:
        return []

    connection = get_connection()
    try:
        cursor = connection.cursor()

        if status:
            cursor.execute(
                """
                SELECT *
                FROM watch_alerts
                WHERE watchtower_id = ?
                  AND status = ?
                ORDER BY
                    CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                    due_at ASC,
                    id DESC
                """,
                (tower["watchtower"]["id"], status),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM watch_alerts
                WHERE watchtower_id = ?
                ORDER BY
                    CASE WHEN status = 'open' THEN 0 ELSE 1 END,
                    CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                    due_at ASC,
                    id DESC
                """,
                (tower["watchtower"]["id"],),
            )

        return [
            {
                "id": row["id"],
                "watch_item_id": row["watch_item_id"],
                "alert_type": row["alert_type"],
                "title": row["title"],
                "message": row["message"],
                "status": row["status"],
                "due_at": row["due_at"],
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()


def get_watch_evaluations(contract_id: int, user_id: int) -> list[dict]:
    """Return persisted event evaluations for audit/history views."""
    tower = get_watchtower(contract_id, user_id)
    if tower is None:
        return []

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                e.id,
                e.watch_item_id,
                e.event_id,
                e.result,
                e.explanation,
                e.evidence_json,
                e.evaluated_at,
                i.clause_id,
                i.title,
                ev.event_type,
                ev.event_date,
                ev.description
            FROM watch_evaluations e
            JOIN watch_items i
              ON i.id = e.watch_item_id
            JOIN watch_events ev
              ON ev.id = e.event_id
            WHERE e.watchtower_id = ?
            ORDER BY e.id DESC
            """,
            (tower["watchtower"]["id"],),
        )

        return [
            {
                "id": row["id"],
                "watch_item_id": row["watch_item_id"],
                "event_id": row["event_id"],
                "clause_id": row["clause_id"],
                "title": row["title"],
                "event_type": row["event_type"],
                "event_date": row["event_date"],
                "event_description": row["description"],
                "result": row["result"],
                "explanation": row["explanation"],
                "evidence": _load(row["evidence_json"], {}),
                "evaluated_at": row["evaluated_at"],
            }
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()


def close_watch_alert(contract_id: int, user_id: int, alert_id: int) -> dict:
    """Close one open alert belonging to the user's contract Watchtower."""
    tower = get_watchtower(contract_id, user_id)
    if tower is None:
        raise ValueError("Watchtower is not active for this contract.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT *
            FROM watch_alerts
            WHERE id = ?
              AND watchtower_id = ?
            LIMIT 1
            """,
            (alert_id, tower["watchtower"]["id"]),
        )
        alert = cursor.fetchone()

        if alert is None:
            raise ValueError("Watchtower alert not found.")

        if alert["status"] != "open":
            return {
                "success": True,
                "message": "Alert is already closed.",
                "alert": {
                    "id": alert["id"],
                    "status": alert["status"],
                    "due_at": alert["due_at"],
                },
            }

        cursor.execute(
            """
            UPDATE watch_alerts
            SET status = 'closed'
            WHERE id = ?
              AND watchtower_id = ?
            """,
            (alert_id, tower["watchtower"]["id"]),
        )
        connection.commit()

        return {
            "success": True,
            "message": "Watchtower alert closed.",
            "alert": {
                "id": alert["id"],
                "status": "closed",
                "due_at": alert["due_at"],
            },
        }
    finally:
        connection.close()



def get_watch_events(contract_id: int, user_id: int) -> list[dict]:
    tower = get_watchtower(contract_id, user_id)
    if tower is None:
        return []
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM watch_events WHERE watchtower_id = ? ORDER BY id DESC", (tower["watchtower"]["id"],))
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "event_date": row["event_date"],
                "description": row["description"],
                "observed_value": row["observed_value"],
                "observed_unit": row["observed_unit"],
                "evidence": _load(row["evidence_json"], {}),
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()

# ============================================================
# WATCHTOWER USER DECISIONS
# ============================================================

_ALLOWED_DECISIONS = {
    "RENEW",
    "NON_RENEW",
    "DECIDE_LATER",
    "REVIEW_ISSUE",
    "HANDLE_NOW",
    "REVIEW_PAYMENT",
    "RESOLVE_ISSUE",
    "REVIEW",
}


def _normalize_decision(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).upper().strip("_")
    if normalized not in _ALLOWED_DECISIONS:
        raise ValueError(
            "Unsupported Watchtower decision. "
            "Use RENEW, NON_RENEW, DECIDE_LATER, REVIEW_ISSUE, "
            "HANDLE_NOW, REVIEW_PAYMENT, RESOLVE_ISSUE, or REVIEW."
        )
    return normalized


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _get_item_for_contract(cursor, watchtower_id: int, watch_item_id: int):
    cursor.execute(
        """
        SELECT *
        FROM watch_items
        WHERE id = ?
          AND watchtower_id = ?
          AND status = 'active'
        LIMIT 1
        """,
        (watch_item_id, watchtower_id),
    )
    return cursor.fetchone()


def _get_preferred_alert_for_item(cursor, watchtower_id: int, watch_item_id: int):
    cursor.execute(
        """
        SELECT *
        FROM watch_alerts
        WHERE watchtower_id = ?
          AND watch_item_id = ?
        ORDER BY
            CASE WHEN status = 'open' THEN 0 ELSE 1 END,
            CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
            due_at ASC,
            id DESC
        LIMIT 1
        """,
        (watchtower_id, watch_item_id),
    )
    return cursor.fetchone()


def record_watch_decision(
    contract_id: int,
    user_id: int,
    watch_item_id: int,
    decision: str,
) -> dict:
    """
    Persist a user's business decision for one active Watchtower item.

    This is deliberately separate from evaluation and alert state:
      - evaluation = what Watchtower detected;
      - alert = what needs attention;
      - decision = what the user chose to do.

    A new decision supersedes the previous active decision for the same
    monitored item, while keeping the old row as decision history.
    """
    normalized_decision = _normalize_decision(decision)

    tower = get_watchtower(contract_id, user_id)
    if tower is None:
        raise ValueError("Watchtower is not active for this contract.")

    watchtower_id = int(tower["watchtower"]["id"])

    connection = get_connection()
    try:
        cursor = connection.cursor()

        item = _get_item_for_contract(
            cursor,
            watchtower_id,
            int(watch_item_id),
        )
        if item is None:
            raise ValueError("Watchtower item not found or is not active.")

        item_type = _norm(item["item_type"])
        if item_type == "renewal":
            allowed_for_item = {"RENEW", "NON_RENEW", "DECIDE_LATER"}
        elif item_type == "cure_period":
            allowed_for_item = {"REVIEW_ISSUE", "HANDLE_NOW", "DECIDE_LATER"}
        elif item_type in {"payment", "payment_consequence"}:
            allowed_for_item = {"REVIEW_PAYMENT", "RESOLVE_ISSUE", "DECIDE_LATER"}
        else:
            allowed_for_item = {"REVIEW", "HANDLE_NOW", "DECIDE_LATER"}

        if normalized_decision not in allowed_for_item:
            raise ValueError(
                f"Decision {normalized_decision} is not valid for Watchtower item type {item_type}."
            )

        alert = _get_preferred_alert_for_item(
            cursor,
            watchtower_id,
            int(watch_item_id),
        )

        due_at = alert["due_at"] if alert else None
        follow_up_at = None

        due_date = _parse_iso_date(due_at)
        if due_date is not None:
            if normalized_decision == "DECIDE_LATER":
                # Bring the decision back into focus seven days before the
                # contractual deadline. The UI surfaces this date; a separate
                # notification scheduler can consume it later.
                follow_up_date = due_date - timedelta(days=7)
                if follow_up_date < date.today():
                    follow_up_date = date.today()
                follow_up_at = follow_up_date.isoformat()
            elif normalized_decision == "NON_RENEW":
                # Non-renewal remains actionable through the contractual
                # notice deadline.
                follow_up_at = due_date.isoformat()

        # Keep a full decision history while ensuring there is only one
        # currently active decision for the monitored item.
        cursor.execute(
            """
            UPDATE watch_decisions
            SET status = 'superseded',
                updated_at = CURRENT_TIMESTAMP
            WHERE watchtower_id = ?
              AND watch_item_id = ?
              AND status = 'active'
            """,
            (watchtower_id, int(watch_item_id)),
        )

        cursor.execute(
            """
            INSERT INTO watch_decisions (
                watchtower_id,
                watch_item_id,
                decision,
                status,
                due_at,
                follow_up_at
            )
            VALUES (?, ?, ?, 'active', ?, ?)
            """,
            (
                watchtower_id,
                int(watch_item_id),
                normalized_decision,
                due_at,
                follow_up_at,
            ),
        )
        decision_id = int(cursor.lastrowid)

        connection.commit()

        return {
            "success": True,
            "decision": {
                "id": decision_id,
                "watch_item_id": int(watch_item_id),
                "clause_id": item["clause_id"],
                "title": item["title"],
                "decision": normalized_decision,
                "status": "active",
                "due_at": due_at,
                "follow_up_at": follow_up_at,
            },
        }
    finally:
        connection.close()


def get_watch_decisions(
    contract_id: int,
    user_id: int,
    watch_item_id: Optional[int] = None,
) -> list[dict]:
    """Return Watchtower decision history, newest first."""
    tower = get_watchtower(contract_id, user_id)
    if tower is None:
        return []

    connection = get_connection()
    try:
        cursor = connection.cursor()

        query = """
            SELECT
                d.id,
                d.watch_item_id,
                d.decision,
                d.status,
                d.due_at,
                d.follow_up_at,
                d.created_at,
                d.updated_at,
                i.clause_id,
                i.title,
                i.item_type
            FROM watch_decisions d
            JOIN watch_items i
              ON i.id = d.watch_item_id
            WHERE d.watchtower_id = ?
        """
        params = [tower["watchtower"]["id"]]

        if watch_item_id is not None:
            query += " AND d.watch_item_id = ?"
            params.append(int(watch_item_id))

        query += " ORDER BY d.id DESC"

        cursor.execute(query, tuple(params))

        return [
            {
                "id": row["id"],
                "watch_item_id": row["watch_item_id"],
                "clause_id": row["clause_id"],
                "title": row["title"],
                "item_type": row["item_type"],
                "decision": row["decision"],
                "status": row["status"],
                "due_at": row["due_at"],
                "follow_up_at": row["follow_up_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()


def get_latest_watch_decisions(
    contract_id: int,
    user_id: int,
) -> list[dict]:
    """Return only the current active user decision for each watch item."""
    decisions = get_watch_decisions(contract_id, user_id)
    latest = {}
    for decision in decisions:
        if decision["status"] != "active":
            continue
        item_id = decision["watch_item_id"]
        if item_id not in latest:
            latest[item_id] = decision
    return list(latest.values())

