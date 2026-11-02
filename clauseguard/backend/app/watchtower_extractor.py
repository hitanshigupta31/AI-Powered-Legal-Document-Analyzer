# ============================================================
# CLAUSEGUARD - WATCHTOWER EXTRACTOR
# ============================================================

import json
import re
from typing import Any

from app.database import get_connection, get_contract


# Watchtower deliberately uses a deterministic first-pass extractor.
# The contract text is the source of truth; no invented deadlines or
# thresholds are created here.

MONEY_RE = re.compile(r"(?:\$|€|£)\s?\d[\d,]*(?:\.\d+)?", re.I)
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%", re.I)
DAYS_RE = re.compile(
    r"""
    \b
    (?:
        \d+
        |
        (?:thirty|sixty|ninety|one\s+hundred\s+and\s+twenty)
        \s*\(\s*\d+\s*\)
    )
    \s*days?\b
    """,
    re.I | re.X,
)
MONTH_RE = re.compile(r"\b(?:\d+|twelve|six|three)\s*\(?\s*months?\)?\b", re.I)


def _text(clause: dict[str, Any]) -> str:
    return str(clause.get("text") or "").strip()


def _clause_id(clause: dict[str, Any]) -> str:
    return str(clause.get("clause_id") or clause.get("id") or "").strip()


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _snippet(text: str, terms: list[str], limit: int = 260) -> str:
    lower = text.lower()
    positions = [lower.find(term.lower()) for term in terms if lower.find(term.lower()) >= 0]
    start = max(0, min(positions) - 80) if positions else 0
    snippet = re.sub(r"\s+", " ", text[start:start + limit]).strip()
    return snippet


def _base_item(clause: dict[str, Any], *, item_type: str, title: str,
               description: str, trigger_type: str, rule: dict,
               evidence_terms: list[str]) -> dict:
    text = _text(clause)
    return {
        "clause_id": _clause_id(clause),
        "clause_title": clause.get("title") or f"Clause {_clause_id(clause)}",
        "item_type": item_type,
        "title": title,
        "description": description,
        "requirement_text": text,
        "trigger_type": trigger_type,
        "rule": rule,
        "evidence": {
            "source": "contract_clause",
            "matched_text": _snippet(text, evidence_terms),
            "signals": evidence_terms,
        },
    }


def _extract_days(text: str) -> str | None:
    """
    Extract a contractual day period and normalize it.

    Handles both:
      - "60 days"
      - "sixty (60) days"
      - "sixty days"
      - "30-day" is intentionally not handled here because this
        extractor currently models explicit duration phrases.
    """
    match = DAYS_RE.search(text)
    if not match:
        return None

    raw = re.sub(r"\s+", " ", match.group(0)).strip()

    # Prefer the numeric value when the contract gives both words
    # and a parenthesized number, e.g. "sixty (60) days".
    numeric = re.search(r"\((\d+)\)", raw)
    if numeric:
        return f"{numeric.group(1)} days"

    numeric = re.match(r"(\d+)\s*days?", raw, re.I)
    if numeric:
        return f"{numeric.group(1)} days"

    return raw.lower()


def _load_contract_source(
    contract_id: int,
    user_id: int,
    contract,
) -> tuple[list[dict], int | None, str]:
    """
    Prefer the latest approved immutable contract revision.

    The original contracts row remains the source fallback. This keeps
    Watchtower compatible with contracts that have never been revised,
    while ensuring approved Feature 3 changes are actually monitored.
    """
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # contract_versions is created by the approval layer. If it does
        # not exist yet, fall back cleanly to the original contract.
        try:
            cursor.execute(
                """
                SELECT id, version_number, clauses_json
                FROM contract_versions
                WHERE contract_id = ?
                  AND user_id = ?
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (contract_id, user_id),
            )
            revision = cursor.fetchone()
        except Exception:
            revision = None

        if revision is not None:
            try:
                revised_clauses = json.loads(revision["clauses_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                revised_clauses = []

            if isinstance(revised_clauses, list) and revised_clauses:
                return (
                    revised_clauses,
                    int(revision["id"]),
                    f"revision_{int(revision['version_number'])}",
                )

    finally:
        connection.close()

    try:
        original_clauses = json.loads(contract["clauses_json"] or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Contract clause data is invalid.") from exc

    if not isinstance(original_clauses, list):
        raise RuntimeError("Stored contract clauses are invalid.")

    return original_clauses, None, "original"


def _extract_clause_items(clause: dict[str, Any]) -> list[dict]:
    text = _text(clause)
    lower = _normalise(text)
    if not text:
        return []

    items: list[dict] = []

    # Recurring payment / invoice obligation.
    if (
        any(x in lower for x in ["per month", "monthly", "each month", "every month", "per year", "annually", "annual fee"])
        and any(x in lower for x in ["pay", "payment", "fee", "invoice", "subscription"])
    ):
        amount = MONEY_RE.search(text)
        cadence = "monthly" if any(x in lower for x in ["per month", "monthly", "each month", "every month"]) else "annual"
        items.append(_base_item(
            clause,
            item_type="payment",
            title="Recurring subscription payment",
            description="Monitor the recurring payment obligation stated in the contract.",
            trigger_type="recurring_due",
            rule={"cadence": cadence, "amount": amount.group(0) if amount else None},
            evidence_terms=["pay", "payment", cadence],
        ))

    # Late payment consequences are a separate signal because an event
    # such as a missed payment can trigger a distinct contractual result.
    if any(x in lower for x in ["late payment", "late payments", "overdue", "outstanding balance"]) and any(x in lower for x in ["interest", "penalty", "fee", "accrue"]):
        rate = PERCENT_RE.search(text)
        items.append(_base_item(
            clause,
            item_type="payment_consequence",
            title="Late-payment consequence",
            description="Monitor the contractual consequence attached to a late or overdue payment.",
            trigger_type="event_triggered",
            rule={"event": "late_payment", "rate": rate.group(0) if rate else None},
            evidence_terms=["late payment", "interest", "outstanding balance"],
        ))

    # Auto-renewal + notice window. This explicitly covers the previously
    # missed Clause 3 pattern.
    if any(x in lower for x in ["automatically renew", "auto-renew", "automatic renewal", "successive"]):
        notice = _extract_days(text)
        items.append(_base_item(
            clause,
            item_type="renewal",
            title="Non-renewal notice deadline",
            description="Monitor the notice window required to prevent automatic renewal.",
            trigger_type="deadline",
            rule={
                "event": "renewal_deadline",
                "notice_period": notice,
                "renewal": True,
            },
            evidence_terms=["automatically renew", "notice", "days"],
        ))

    # Cure / breach / termination trigger.
    if any(x in lower for x in ["opportunity to cure", "cure period", "days' prior written notice", "prior written notice"]):
        cure = _extract_days(text)
        trigger = "breach" if any(x in lower for x in ["violation", "breach", "default", "acceptable use policy"]) else "contractual_notice"
        items.append(_base_item(
            clause,
            item_type="cure_period",
            title="Cure / notice protection",
            description="Monitor the notice or cure period that applies before the stated contractual consequence.",
            trigger_type="event_triggered",
            rule={
                "event": trigger,
                "cure_period": cure,
            },
            evidence_terms=["notice", "cure", "violation" if "violation" in lower else "breach"],
        ))

    # Explicit expiration / term deadline where no renewal item already
    # captured it.
    if not any(i["item_type"] == "renewal" for i in items) and any(x in lower for x in ["expires", "expiration", "expiry", "end of the term", "term shall end"]):
        items.append(_base_item(
            clause,
            item_type="term_deadline",
            title="Contract term deadline",
            description="Monitor the contractual term or expiration condition stated in the clause.",
            trigger_type="deadline",
            rule={"event": "term_expiration"},
            evidence_terms=["term", "expires" if "expires" in lower else "expiration"],
        ))

    # Measurable thresholds are useful Watchtower signals even when they
    # are not payments or renewal dates.
    if (MONEY_RE.search(text) or PERCENT_RE.search(text)) and any(x in lower for x in ["exceed", "greater than", "less than", "threshold", "limit", "cap", "maximum", "minimum"]):
        items.append(_base_item(
            clause,
            item_type="threshold",
            title="Contractual threshold",
            description="Monitor the measurable threshold or limit stated in the clause.",
            trigger_type="threshold_crossed",
            rule={
                "amount": MONEY_RE.search(text).group(0) if MONEY_RE.search(text) else None,
                "percentage": PERCENT_RE.search(text).group(0) if PERCENT_RE.search(text) else None,
            },
            evidence_terms=["threshold", "limit", "cap"],
        ))

    return items


def _dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = (
            item.get("clause_id"),
            item.get("item_type"),
            item.get("title"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _candidate_decision(clause: dict[str, Any], items: list[dict]) -> dict:
    return {
        "clause_id": _clause_id(clause),
        "title": clause.get("title") or f"Clause {_clause_id(clause)}",
        "decision": "monitorable" if items else "not_monitorable",
        "item_count": len(items),
        "reason": (
            "Contains a concrete deadline, recurring obligation, trigger, consequence, or measurable threshold."
            if items
            else "No concrete monitorable obligation, trigger, deadline, consequence, or measurable threshold was detected."
        ),
    }


def extract_monitorable_items(contract_id: int, user_id: int) -> dict:
    contract = get_contract(contract_id, user_id)
    if contract is None:
        raise ValueError("Contract not found.")

    clauses, source_version_id, source_label = _load_contract_source(
        contract_id,
        user_id,
        contract,
    )

    all_items: list[dict] = []
    candidate_decisions: list[dict] = []

    for clause in clauses:
        clause_items = _extract_clause_items(clause)
        all_items.extend(clause_items)
        candidate_decisions.append(_candidate_decision(clause, clause_items))

    all_items = _dedupe(all_items)

    # Stable item IDs are useful to the frontend and to activation payloads.
    for index, item in enumerate(all_items, start=1):
        item["item_id"] = f"WT-{index:03d}"

    candidate_count = sum(1 for d in candidate_decisions if d["decision"] == "monitorable")

    return {
        "contract": {
            "id": int(contract["id"]),
            "title": contract["filename"] or f"Contract {contract_id}",
            "clause_count": len(clauses),
            "source_version_id": source_version_id,
            "source": source_label,
        },
        "items": all_items,
        "monitorable_items": all_items,
        "extraction_summary": {
            "clauses_considered": len(clauses),
            "candidate_clauses": candidate_count,
            "items_extracted": len(all_items),
            "candidate_decisions": candidate_decisions,
        },
    }
