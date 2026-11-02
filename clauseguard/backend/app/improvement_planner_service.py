# ============================================================
# CLAUSEGUARD - IMPROVEMENT PLAN / INTENT INTERPRETER
# Feature 3 / Layer 2
# ============================================================
"""
Turns a selected contract attention area + optional founder request into
an explicit, reviewable improvement plan.

This layer sits AFTER the contract-level attention assessment and BEFORE
exact clause rewriting.

Pipeline:
    stored contract analysis
        -> selected attention area
        -> selected strategies
        -> optional founder instruction
        -> structured improvement intent

This service does NOT:
    - rerun contract analysis
    - rewrite contract language
    - create ChangeObjects
    - modify the database
    - apply changes

The purpose of this layer is to bridge:
    "This area needs attention"
into:
    "Here is what the founder wants to achieve in this area."
"""

import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from groq import (
    Groq,
    APIConnectionError,
    RateLimitError,
    APIStatusError,
    AuthenticationError,
)

from app.improvement_service import (
    IMPROVEMENT_CATALOGUE,
    FLAG_TO_AREA,
    CONTEXT_ONLY_FLAGS,
)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

MAX_CLAUSE_CHARS = 3500
MAX_CLARIFICATIONS = 3
MAX_DIRECTIONS = 5


# ============================================================
# AREA -> CLAUSE TYPE FALLBACKS
# ============================================================

AREA_CLAUSE_TYPES = {
    "termination": {"Termination"},
    "indemnification": {"Indemnification"},
    "liability": {"Limitation of Liability"},
    "renewal": {"Auto-Renewal"},
    "intellectual_property": {"Intellectual Property"},
    "confidentiality": {"Confidentiality"},
    "restrictive_covenant": {"Restrictive Covenant"},
    "payment": {"Payment"},
    "dispute_resolution": {"Dispute Resolution"},
    "general": set(),
}


# ============================================================
# HELPERS
# ============================================================

def _normalise_area_key(value: str) -> str:
    value = (value or "").strip().lower()

    aliases = {
        "termination rights": "termination",
        "termination": "termination",
        "indemnity": "indemnification",
        "indemnification": "indemnification",
        "liability": "liability",
        "liability & financial exposure": "liability",
        "renewal": "renewal",
        "renewal & exit terms": "renewal",
        "intellectual property": "intellectual_property",
        "confidentiality": "confidentiality",
        "post-contract restrictions": "restrictive_covenant",
        "restrictive covenant": "restrictive_covenant",
        "payment terms": "payment",
        "payment": "payment",
        "dispute resolution": "dispute_resolution",
        "contractual restrictions": "general",
        "general": "general",
    }

    return aliases.get(value, value)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _get_strategy(area_key: str, strategy_id: str) -> Optional[dict]:
    area = IMPROVEMENT_CATALOGUE.get(area_key)
    if not area:
        return None

    item = area.get("strategies", {}).get(strategy_id)
    if not item:
        return None

    title, description = item

    return {
        "strategy_id": strategy_id,
        "title": title,
        "description": description,
    }


def _default_strategy_ids(area_key: str) -> list[str]:
    area = IMPROVEMENT_CATALOGUE.get(area_key)
    if not area:
        return []

    return list(area.get("strategies", {}).keys())[:3]


def _clause_belongs_to_area(
    clause: dict,
    area_key: str,
) -> bool:
    """Resolve a clause to an area using stored signals first."""

    flags = clause.get("risk_flags", [])
    if isinstance(flags, list):
        for flag in flags:
            flag = _clean_text(flag)
            if not flag or flag in CONTEXT_ONLY_FLAGS:
                continue

            if FLAG_TO_AREA.get(flag) == area_key:
                return True

    clause_type = _clean_text(
        clause.get("clause_type", "Other")
    )

    if clause_type in AREA_CLAUSE_TYPES.get(area_key, set()):
        return True

    return area_key == "general" and clause_type == "Other"


def _find_affected_clauses(
    clauses: list[dict],
    area_key: str,
) -> list[dict]:
    result = []

    for clause in clauses:
        if not isinstance(clause, dict):
            continue

        if not _clause_belongs_to_area(clause, area_key):
            continue

        result.append({
            "clause_id": str(clause.get("clause_id", "")),
            "title": _clean_text(
                clause.get("title", "")
            ),
            "clause_type": _clean_text(
                clause.get("clause_type", "Other")
            ),
            "text": _clean_text(
                clause.get("text", "")
            )[:MAX_CLAUSE_CHARS],
            "risk_flags": [
                _clean_text(flag)
                for flag in clause.get("risk_flags", [])
                if _clean_text(flag)
                and _clean_text(flag) not in CONTEXT_ONLY_FLAGS
            ],
            "risk_reasons": [
                _clean_text(reason)
                for reason in clause.get("risk_reasons", [])
                if _clean_text(reason)
            ],
        })

    return result


def _selected_strategies(
    area_key: str,
    strategy_ids: Optional[list[str]],
) -> list[dict]:
    requested = strategy_ids or _default_strategy_ids(area_key)
    result = []
    seen = set()

    for strategy_id in requested:
        strategy_id = _clean_text(strategy_id)
        if not strategy_id or strategy_id in seen:
            continue

        strategy = _get_strategy(area_key, strategy_id)
        if strategy:
            result.append(strategy)
            seen.add(strategy_id)

    return result[:5]


def _contains_case_insensitive(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return phrase.lower() in text.lower()


def _validate_interpretation(
    data: Any,
    area_key: str,
    affected_clauses: list[dict],
    strategies: list[dict],
    user_instruction: str,
) -> dict:
    """Validate and normalize the LLM interpretation."""

    if not isinstance(data, dict):
        raise ValueError("AI interpretation is not a JSON object.")

    allowed_clause_ids = {
        str(item["clause_id"])
        for item in affected_clauses
    }

    allowed_strategy_ids = {
        item["strategy_id"]
        for item in strategies
    }

    objective = _clean_text(
        data.get("objective", "")
    )

    directions = data.get("requested_directions", [])
    if not isinstance(directions, list):
        directions = []

    explicit_terms = data.get("explicit_terms", [])
    if not isinstance(explicit_terms, list):
        explicit_terms = []

    ambiguities = data.get("ambiguities", [])
    if not isinstance(ambiguities, list):
        ambiguities = []

    clause_ids = data.get("affected_clause_ids", [])
    if not isinstance(clause_ids, list):
        clause_ids = []

    chosen_strategy_ids = data.get("strategy_ids", [])
    if not isinstance(chosen_strategy_ids, list):
        chosen_strategy_ids = []

    cleaned_clause_ids = [
        str(item).strip()
        for item in clause_ids
        if str(item).strip() in allowed_clause_ids
    ]

    if not cleaned_clause_ids:
        cleaned_clause_ids = [
            str(item["clause_id"])
            for item in affected_clauses
        ]

    cleaned_strategy_ids = [
        str(item).strip()
        for item in chosen_strategy_ids
        if str(item).strip() in allowed_strategy_ids
    ]

    if not cleaned_strategy_ids:
        cleaned_strategy_ids = [
            item["strategy_id"]
            for item in strategies[:3]
        ]

    cleaned_directions = []
    for item in directions:
        text = _clean_text(item)
        if text and text not in cleaned_directions:
            cleaned_directions.append(text)

    cleaned_explicit_terms = []
    for item in explicit_terms:
        text = _clean_text(item)
        if not text:
            continue

        # Explicit terms must actually originate in the user's instruction.
        if _contains_case_insensitive(user_instruction, text):
            cleaned_explicit_terms.append(text)

    cleaned_ambiguities = []
    for item in ambiguities:
        text = _clean_text(item)
        if text and text not in cleaned_ambiguities:
            cleaned_ambiguities.append(text)

    # --------------------------------------------------------
    # REMOVE NON-BLOCKING AMBIGUITIES
    #
    # The interpreter should ask for clarification only when a
    # missing decision genuinely prevents a faithful draft.
    # A user-supplied duration already gives us a usable cure
    # period. Likewise, a qualitative exception supplied by the
    # founder (for example, "serious security threat") should be
    # preserved rather than forcing the founder to define it again.
    # --------------------------------------------------------

    lowered_instruction = user_instruction.lower()

    filtered_ambiguities = []

    for ambiguity in cleaned_ambiguities:
        lowered = ambiguity.lower()

        non_blocking = False

        # Example: the user explicitly says "30 days ... before
        # termination". Do not ask whether that is a minimum or
        # fixed window; the drafting stage can express the direct
        # request faithfully as a cure period.
        duration_match = re.search(
            r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+days?\b",
            lowered_instruction,
        )

        if duration_match and (
            "minimum" in lowered
            or "fixed window" in lowered
            or "terminate earlier" in lowered
            or "earlier than" in lowered
        ) and "before termination" in lowered_instruction:
            non_blocking = True

        # A qualitative trigger explicitly supplied by the founder
        # does not need to be redefined at the intent stage.
        if (
            "definition" in lowered
            or "criteria" in lowered
        ):
            quoted_terms = re.findall(
                r"[\"']([^\"']+)[\"']",
                ambiguity,
            )

            if any(
                term.strip().lower() in lowered_instruction
                for term in quoted_terms
                if term.strip()
            ):
                non_blocking = True

        if not non_blocking:
            filtered_ambiguities.append(ambiguity)

    cleaned_directions = cleaned_directions[:MAX_DIRECTIONS]
    cleaned_ambiguities = filtered_ambiguities[:MAX_CLARIFICATIONS]

    status = (
        "needs_clarification"
        if cleaned_ambiguities
        else "ready_for_drafting"
    )

    if not objective:
        objective = (
            "Improve the selected contract area according to the founder's request."
            if user_instruction
            else "Review and improve the selected contract area."
        )

    return {
        "objective": objective,
        "requested_directions": cleaned_directions,
        "explicit_terms": cleaned_explicit_terms,
        "ambiguities": cleaned_ambiguities,
        "affected_clause_ids": cleaned_clause_ids,
        "strategy_ids": cleaned_strategy_ids,
        "status": status,
    }


# ============================================================
# GROQ
# ============================================================

def _get_client() -> Groq:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "Missing GROQ_API_KEY environment variable."
        )

    return Groq(api_key=GROQ_API_KEY)


def _call_groq(
    messages: list[dict],
    max_tokens: int = 1400,
) -> str:
    try:
        response = _get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "AI returned an empty response."
            )

        return content

    except RateLimitError as exc:
        raise RuntimeError(
            "AI service rate limited."
        ) from exc

    except APIStatusError as exc:
        status = getattr(exc, "status_code", 0)

        if status == 401:
            raise RuntimeError(
                "AI authentication failed."
            ) from exc

        raise RuntimeError(
            f"AI provider error ({status})."
        ) from exc

    except APIConnectionError as exc:
        raise RuntimeError(
            "Could not connect to AI provider."
        ) from exc

    except AuthenticationError as exc:
        raise RuntimeError(
            "AI authentication failed."
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Could not connect to Groq: {exc}"
        ) from exc


def _clean_json(raw: str) -> str:
    text = (raw or "").strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return text.strip()


# ============================================================
# LLM INTENT INTERPRETATION
# ============================================================

INTENT_SYSTEM_PROMPT = """
You are ClauseGuard's contract customization intent interpreter.

Your task is NOT to rewrite a contract clause.
Your task is to understand what the founder wants to achieve.

You receive:
- one selected contract improvement area;
- the strategies available for that area;
- the actual contract clauses and deterministic findings;
- optionally, the founder's natural-language request.

STRICT RULES:

1. Stay grounded in the supplied contract text and supplied findings.
2. Do not invent facts about the contract.
3. Do not invent dates, amounts, durations, thresholds, obligations,
   exceptions, legal triggers, or procedures.
4. If the founder explicitly provides a term such as "30 days",
   you may record it as an explicit user requirement.
5. Do not turn a vague request into a specific contractual term.
6. Do not draft replacement language.
7. Do not select a strategy that is not supplied.
8. affected_clause_ids must come only from supplied clause IDs.
9. requested_directions describe what the founder wants changed,
   not exact new contractual language.
10. ambiguities should contain only decisions that are genuinely
    missing from the founder's request and that materially block a faithful
    draft. Do not ask the founder to define a qualitative term they
    explicitly supplied unless the missing definition is essential to
    interpret the requested change.
11. A clear statement such as "30 days to cure before termination" is
    sufficient to record a 30-day cure period. Do not ask whether that
    means a minimum or fixed window unless the wording itself is unclear.
12. Preserve explicitly supplied qualitative conditions such as
    "serious security threat" as user requirements; do not invent a
    more specific definition at this stage.
13. Do not provide legal conclusions or claim a specific outcome is
    legally required.

Examples:

Founder:
"I don't want the provider to terminate us whenever they want."

Good interpretation:
- objective: reduce unilateral termination authority
- no invented notice period
- ambiguity may remain about whether the founder wants notice,
  cure rights, narrower triggers, or another protection.

Founder:
"Give us 30 days to cure an AUP violation before termination."

Good interpretation:
- explicit term: "30 days"
- requested direction: add a cure period for the identified violation
- no invented additional conditions.

Return ONLY JSON:
{
  "objective": "...",
  "requested_directions": ["..."],
  "explicit_terms": ["..."],
  "ambiguities": ["..."],
  "affected_clause_ids": ["..."],
  "strategy_ids": ["...", "..." ]
}
"""


def _interpret_with_llm(
    area_key: str,
    area_title: str,
    affected_clauses: list[dict],
    strategies: list[dict],
    user_instruction: str,
) -> dict:
    payload = {
        "area_key": area_key,
        "area_title": area_title,
        "user_instruction": user_instruction,
        "available_strategies": strategies,
        "affected_clauses": affected_clauses,
    }

    raw = _call_groq([
        {
            "role": "system",
            "content": INTENT_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
        },
    ])

    cleaned = _clean_json(raw)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "AI returned invalid JSON for the improvement plan."
        ) from exc

    return _validate_interpretation(
        parsed,
        area_key,
        affected_clauses,
        strategies,
        user_instruction,
    )


# ============================================================
# PUBLIC API
# ============================================================

def build_improvement_plan(
    contract_id: int,
    contract_row: Any,
    area_key: str,
    strategy_ids: Optional[list[str]] = None,
    user_instruction: str = "",
) -> dict:
    """
    Build a structured improvement plan for one attention area.

    No contract text is modified.
    """

    area_key = _normalise_area_key(area_key)

    if area_key not in IMPROVEMENT_CATALOGUE:
        raise ValueError(
            f"Unknown improvement area: {area_key}"
        )

    try:
        clauses = json.loads(
            contract_row["clauses_json"]
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
        KeyError,
    ) as exc:
        raise RuntimeError(
            "Failed to load stored contract analysis."
        ) from exc

    if not isinstance(clauses, list):
        raise RuntimeError(
            "Stored clause analysis is invalid."
        )

    area_title = IMPROVEMENT_CATALOGUE[area_key]["title"]
    affected_clauses = _find_affected_clauses(
        clauses,
        area_key,
    )

    if not affected_clauses:
        raise ValueError(
            "No contract clauses were found for the selected improvement area."
        )

    strategies = _selected_strategies(
        area_key,
        strategy_ids,
    )

    if not strategies:
        raise ValueError(
            "No valid strategies were supplied for the selected improvement area."
        )

    user_instruction = _clean_text(user_instruction)

    # With no founder request, return a planning context rather than
    # pretending that the user's objective is already known.
    if not user_instruction:
        return {
            "success": True,
            "contract_id": contract_id,
            "area": {
                "area_key": area_key,
                "title": area_title,
            },
            "selected_strategies": strategies,
            "affected_clauses": affected_clauses,
            "user_request": "",
            "improvement_plan": {
                "objective": "Review and improve this contract area.",
                "requested_directions": [
                    item["title"]
                    for item in strategies[:3]
                ],
                "explicit_terms": [],
                "ambiguities": [
                    "What outcome would you like to achieve in this area?"
                ],
                "affected_clause_ids": [
                    item["clause_id"]
                    for item in affected_clauses
                ],
                "strategy_ids": [
                    item["strategy_id"]
                    for item in strategies
                ],
                "status": "needs_user_direction",
            },
        }

    try:
        plan = _interpret_with_llm(
            area_key=area_key,
            area_title=area_title,
            affected_clauses=affected_clauses,
            strategies=strategies,
            user_instruction=user_instruction,
        )

        mode = "ai_interpreted"

    except Exception as exc:
        print(
            f"[IMPROVEMENT PLAN] AI interpretation failed: {exc}"
        )

        # Safe deterministic fallback: preserve the founder's request
        # verbatim and do not pretend we know more than was supplied.
        plan = {
            "objective": "Understand and address the founder's stated concern in this area.",
            "requested_directions": [
                item["title"]
                for item in strategies[:3]
            ],
            "explicit_terms": [],
            "ambiguities": [
                "The founder's request could not be interpreted automatically; review the request before drafting."
            ],
            "affected_clause_ids": [
                item["clause_id"]
                for item in affected_clauses
            ],
            "strategy_ids": [
                item["strategy_id"]
                for item in strategies
            ],
            "status": "needs_clarification",
        }

        mode = "deterministic_fallback"

    return {
        "success": True,
        "contract_id": contract_id,
        "area": {
            "area_key": area_key,
            "title": area_title,
        },
        "selected_strategies": strategies,
        "affected_clauses": affected_clauses,
        "user_request": user_instruction,
        "improvement_plan": plan,
        "plan_mode": mode,
    }
