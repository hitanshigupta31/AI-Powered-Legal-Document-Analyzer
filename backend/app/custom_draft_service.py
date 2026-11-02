# ============================================================
# CLAUSEGUARD - FOUNDER-DIRECTED CLAUSE DRAFTING
# Feature 3 / Layer 3
# ============================================================
"""
Turns a validated founder improvement plan into a proposed clause.

Position in Feature 3:

    stored contract analysis
        -> attention area
        -> founder intent
        -> THIS SERVICE
        -> proposed clause
        -> human approval
        -> exact application (later)

This service does NOT:
    - rerun contract parsing or risk analysis
    - decide what the founder wants
    - modify the database
    - apply a change
    - generate a final DOCX/PDF

Important distinction from draft_service.py:
    draft_service.py handles ClauseGuard-discovered negotiation
    candidates under conservative rule policies.

    This service handles an explicitly founder-authorized request.
    Therefore, a new term such as "30 days" is allowed only when it
    appears in the founder's structured intent.
"""

import hashlib
import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import (
    Groq,
    APIConnectionError,
    RateLimitError,
    APIStatusError,
    AuthenticationError,
)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "qwen/qwen3.8-27b",
)

MAX_CLAUSE_CHARS = 6000
MAX_RELATED_CLAUSES = 5
MAX_REQUIREMENTS = 12

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
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
    max_tokens: int = 2200,
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
                "AI returned an empty drafting response."
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
# TEXT / NORMALIZATION HELPERS
# ============================================================

def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalise_text(value: Any) -> str:
    text = _clean_text(value).lower()

    text = text.replace(
        "–",
        "-",
    ).replace(
        "—",
        "-",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r"[\"'`]",
        "",
        text,
    )

    return text.strip()


def _contains_phrase(
    text: str,
    phrase: str,
) -> bool:
    text_normalised = _normalise_text(text)
    phrase_normalised = _normalise_text(phrase)

    if not text_normalised or not phrase_normalised:
        return False

    return phrase_normalised in text_normalised


def _extract_money(text: str) -> set[str]:
    return {
        item.lower()
        for item in re.findall(
            r"\$\s*[\d,]+(?:\.\d+)?",
            text or "",
        )
    }


def _extract_percentages(text: str) -> set[str]:
    return {
        item.lower()
        for item in re.findall(
            r"\b\d+(?:\.\d+)?\s*%",
            text or "",
        )
    }


def _extract_dates(text: str) -> set[str]:
    values = set()

    patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
        r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b",
    ]

    for pattern in patterns:
        for match in re.findall(
            pattern,
            text or "",
            flags=re.IGNORECASE,
        ):
            values.add(
                _normalise_text(match)
            )

    return values


def _extract_durations(text: str) -> list[str]:
    """
    Capture duration phrases such as:
        30 days
        thirty days
        12 months
    """
    pattern = (
        r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
        r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
        r"eighty|ninety|\d+)"
        r"(?:\s*\(\s*\d+\s*\))?"
        r"\s*(?:calendar[\s-]+)?"
        r"(?:day|days|week|weeks|month|months|year|years)\b"
    )

    return [
        _normalise_text(match)
        for match in re.findall(
            pattern,
            text or "",
            flags=re.IGNORECASE,
        )
    ]


def _canonical_duration(value: str) -> str:
    text = _normalise_text(value)

    match = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
        r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
        r"eighty|ninety)"
        r"(?:\s*\(\s*\d+\s*\))?"
        r"[\s-]*(?:calendar[\s-]+)?"
        r"(day|days|week|weeks|month|months|year|years)\b",
        text,
    )

    if not match:
        return text

    number = match.group(1)
    unit = match.group(2).lower()

    if number in NUMBER_WORDS:
        number = str(NUMBER_WORDS[number])

    return f"{number} {unit}"


def _user_authorized_durations(
    explicit_terms: list[str],
    user_instruction: str,
) -> list[str]:
    source = (
        " ".join(explicit_terms)
        + " "
        + user_instruction
    )

    return _extract_durations(source)


# ============================================================
# FOUNDER REQUIREMENT VALIDATION
# ============================================================

def _requirement_satisfied(
    requirement: str,
    proposed_text: str,
) -> bool:
    """
    Deterministic check that an explicit founder term/direction
    actually appears in or is strongly represented by the draft.

    We intentionally keep this conservative.
    """

    requirement_normalised = _normalise_text(
        requirement
    )

    proposed_normalised = _normalise_text(
        proposed_text
    )

    if not requirement_normalised:
        return True

    # Direct textual grounding is preferred.
    if requirement_normalised in proposed_normalised:
        return True

    # Common duration formulation:
    # "30 days to cure" / "30-day period to cure"
    duration_match = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
        r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
        r"eighty|ninety)[\s-]*(?:calendar[\s-]+)?days?\b",
        requirement_normalised,
    )

    if duration_match:
        requirement_duration = _canonical_duration(
            duration_match.group(0)
        )
        proposed_durations = {
            _canonical_duration(item)
            for item in _extract_durations(proposed_text)
        }

        if requirement_duration in proposed_durations:
            if "cure" not in requirement_normalised:
                return True

            return "cure" in proposed_normalised

    return False


def _validate_founder_requirements(
    plan: dict,
    proposed_text: str,
) -> tuple[bool, list[str]]:
    errors = []

    explicit_terms = plan.get(
        "explicit_terms",
        [],
    )

    if not isinstance(
        explicit_terms,
        list,
    ):
        explicit_terms = []

    explicit_terms = [
        _clean_text(item)
        for item in explicit_terms
        if _clean_text(item)
    ][:MAX_REQUIREMENTS]

    for requirement in explicit_terms:
        if not _requirement_satisfied(
            requirement,
            proposed_text,
        ):
            errors.append(
                "Explicit founder requirement is not reflected "
                f"in the proposed clause: {requirement}"
            )

    return (
        len(errors) == 0,
        errors,
    )


# ============================================================
# SAFETY VALIDATION
# ============================================================

def _validate_no_unapproved_new_financial_or_date_terms(
    original_text: str,
    proposed_text: str,
    plan: dict,
    user_instruction: str,
) -> list[str]:

    errors = []

    # New monetary amounts may only come from an explicit founder
    # requirement. There is no reason for the drafting model to
    # invent a dollar amount.
    original_money = _extract_money(
        original_text
    )

    proposed_money = _extract_money(
        proposed_text
    )

    new_money = (
        proposed_money
        - original_money
    )

    authorized_money = _extract_money(
        user_instruction
    )

    unauthorized_money = (
        new_money
        - authorized_money
    )

    if unauthorized_money:
        errors.append(
            "Proposal introduces an unapproved monetary amount: "
            + ", ".join(
                sorted(unauthorized_money)
            )
        )

    # New percentages are treated the same way.
    original_percentages = _extract_percentages(
        original_text
    )

    proposed_percentages = _extract_percentages(
        proposed_text
    )

    new_percentages = (
        proposed_percentages
        - original_percentages
    )

    authorized_percentages = _extract_percentages(
        user_instruction
    )

    unauthorized_percentages = (
        new_percentages
        - authorized_percentages
    )

    if unauthorized_percentages:
        errors.append(
            "Proposal introduces an unapproved percentage: "
            + ", ".join(
                sorted(unauthorized_percentages)
            )
        )

    # New dates must also originate in the founder request.
    original_dates = _extract_dates(
        original_text
    )

    proposed_dates = _extract_dates(
        proposed_text
    )

    new_dates = (
        proposed_dates
        - original_dates
    )

    authorized_dates = _extract_dates(
        user_instruction
    )

    unauthorized_dates = (
        new_dates
        - authorized_dates
    )

    if unauthorized_dates:
        errors.append(
            "Proposal introduces an unapproved date: "
            + ", ".join(
                sorted(unauthorized_dates)
            )
        )

    # New duration phrases must either already exist in the source
    # clause or be explicitly authorized by the founder.
    original_durations = {
        _canonical_duration(item)
        for item in _extract_durations(original_text)
    }

    proposed_durations = {
        _canonical_duration(item)
        for item in _extract_durations(proposed_text)
    }

    new_durations = (
        proposed_durations
        - original_durations
    )

    authorized_durations = {
        _canonical_duration(item)
        for item in _user_authorized_durations(
            plan.get(
                "explicit_terms",
                []
            ),
            user_instruction,
        )
    }

    for duration in new_durations:
        if duration not in authorized_durations:
            errors.append(
                "Proposal introduces an unapproved duration: "
                f"{duration}"
            )

    return errors


def _validate_no_unrelated_legal_mechanisms(
    original_text: str,
    proposed_text: str,
    plan: dict,
) -> list[str]:
    """
    Block obvious new mechanisms unless the founder actually
    requested them or they already existed in the source clause.

    This is deliberately narrow; we do not attempt to implement
    a full legal-language parser.
    """

    errors = []

    original_lower = _normalise_text(
        original_text
    )

    proposed_lower = _normalise_text(
        proposed_text
    )

    founder_source = _normalise_text(
        " ".join(
            plan.get(
                "explicit_terms",
                []
            )
        )
        + " "
        + " ".join(
            plan.get(
                "requested_directions",
                []
            )
        )
    )

    mechanisms = {
        "arbitration": r"\barbitration\b",
        "jury waiver": r"\b(?:waive|waiver of)\s+(?:a\s+)?jury\b",
        "attorney fees": r"\battorneys?'?\s+fees\b",
        "liquidated damages": r"\bliquidated damages\b",
        "specific performance": r"\bspecific performance\b",
        "injunction": r"\binjunction\b",
        "governing law": r"\bgoverning law\b",
        "indemnification": r"\bindemnif(?:y|ication|ies|ied)\b",
    }

    for label, pattern in mechanisms.items():
        original_has = bool(
            re.search(
                pattern,
                original_lower,
            )
        )

        proposed_has = bool(
            re.search(
                pattern,
                proposed_lower,
            )
        )

        founder_requested = bool(
            re.search(
                pattern,
                founder_source,
            )
        )

        if (
            proposed_has
            and not original_has
            and not founder_requested
        ):
            errors.append(
                "Proposal introduces an unrelated legal mechanism: "
                f"{label}"
            )

    return errors


def validate_founder_draft(
    original_text: str,
    proposed_text: str,
    plan: dict,
    user_instruction: str,
) -> tuple[bool, list[str]]:
    """
    Validate the proposed clause against the founder's
    authorized intent and the original source.
    """

    errors = []

    original_text = _clean_text(
        original_text
    )

    proposed_text = _clean_text(
        proposed_text
    )

    if not original_text:
        errors.append(
            "Original clause is empty."
        )
        return False, errors

    if not proposed_text:
        errors.append(
            "Proposed clause is empty."
        )
        return False, errors

    if _normalise_text(
        original_text
    ) == _normalise_text(
        proposed_text
    ):
        errors.append(
            "The proposed clause does not change the original clause."
        )

    requirement_valid, requirement_errors = (
        _validate_founder_requirements(
            plan,
            proposed_text,
        )
    )

    if not requirement_valid:
        errors.extend(
            requirement_errors
        )

    errors.extend(
        _validate_no_unapproved_new_financial_or_date_terms(
            original_text,
            proposed_text,
            plan,
            user_instruction,
        )
    )

    errors.extend(
        _validate_no_unrelated_legal_mechanisms(
            original_text,
            proposed_text,
            plan,
        )
    )

    return (
        len(errors) == 0,
        errors,
    )


# ============================================================
# DRAFTING PROMPT
# ============================================================

DRAFT_SYSTEM_PROMPT = """
You are ClauseGuard's founder-directed contract drafting engine.

Your job is to draft ONE proposed replacement for the supplied
contract clause.

The founder has already explicitly stated what they want.
Treat those explicit requirements as authorized drafting instructions.

You must remain faithful to the source clause and the supplied
contract evidence.

RULES:

1. Draft only the targeted clause.
2. Preserve the original parties, defined terms, subject matter,
   existing rights, and factual structure unless the founder explicitly
   requested a change to them.
3. Incorporate every explicit founder requirement.
4. Do not invent facts, amounts, dates, durations, thresholds,
   procedures, obligations, exceptions, or legal mechanisms that the
   founder did not request and that were not already present.
5. A new term is allowed only when it is explicitly supplied by the
   founder or already exists in the source clause.
6. Do not silently add "market standard" language.
7. Do not add unrelated protections simply because they might be useful.
8. Do not rewrite the entire agreement.
9. Keep the drafting style reasonably consistent with the source clause.
10. The result must be a replacement clause, not commentary.
11. The reason must explain the requested change in plain English and
    stay grounded in the source clause and founder request.
12. Do not make legal conclusions such as claiming a provision is
    legally required or universally standard.

Return ONLY JSON:

{
  "change_type": "modify",
  "proposed_text": "...",
  "reason": "...",
  "requirements_addressed": ["...", "..."],
  "preserved_facts": ["..."],
  "risk_notes": ["..."]
}
"""


def _build_draft_payload(
    plan_result: dict,
) -> dict:
    area = plan_result.get(
        "area",
        {}
    )

    plan = plan_result.get(
        "improvement_plan",
        {}
    )

    clauses = plan_result.get(
        "affected_clauses",
        []
    )

    strategies = plan_result.get(
        "selected_strategies",
        []
    )

    return {
        "area": {
            "area_key": _clean_text(
                area.get(
                    "area_key",
                    ""
                )
            ),
            "title": _clean_text(
                area.get(
                    "title",
                    ""
                )
            ),
        },
        "founder_request": _clean_text(
            plan_result.get(
                "user_request",
                ""
            )
        ),
        "improvement_plan": {
            "objective": _clean_text(
                plan.get(
                    "objective",
                    ""
                )
            ),
            "requested_directions": [
                _clean_text(item)
                for item in plan.get(
                    "requested_directions",
                    []
                )
                if _clean_text(item)
            ],
            "explicit_terms": [
                _clean_text(item)
                for item in plan.get(
                    "explicit_terms",
                    []
                )
                if _clean_text(item)
            ],
            "affected_clause_ids": [
                str(item)
                for item in plan.get(
                    "affected_clause_ids",
                    []
                )
            ],
        },
        "selected_strategies": strategies,
        "affected_clauses": clauses[:MAX_RELATED_CLAUSES],
    }


def _parse_and_validate_model_response(
    raw: str,
) -> dict:
    cleaned = _clean_json(
        raw
    )

    try:
        data = json.loads(
            cleaned
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "AI returned invalid JSON for clause drafting."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "AI returned an invalid drafting object."
        )

    proposed_text = _clean_text(
        data.get(
            "proposed_text",
            ""
        )
    )

    reason = _clean_text(
        data.get(
            "reason",
            ""
        )
    )

    change_type = _clean_text(
        data.get(
            "change_type",
            "modify"
        )
    ) or "modify"

    requirements_addressed = data.get(
        "requirements_addressed",
        []
    )

    preserved_facts = data.get(
        "preserved_facts",
        []
    )

    risk_notes = data.get(
        "risk_notes",
        []
    )

    if not isinstance(
        requirements_addressed,
        list
    ):
        requirements_addressed = []

    if not isinstance(
        preserved_facts,
        list
    ):
        preserved_facts = []

    if not isinstance(
        risk_notes,
        list
    ):
        risk_notes = []

    return {
        "change_type": change_type,
        "proposed_text": proposed_text,
        "reason": reason,
        "requirements_addressed": [
            _clean_text(item)
            for item in requirements_addressed
            if _clean_text(item)
        ][:MAX_REQUIREMENTS],
        "preserved_facts": [
            _clean_text(item)
            for item in preserved_facts
            if _clean_text(item)
        ][:MAX_REQUIREMENTS],
        "risk_notes": [
            _clean_text(item)
            for item in risk_notes
            if _clean_text(item)
        ][:MAX_REQUIREMENTS],
    }


# ============================================================
# PUBLIC API
# ============================================================

def draft_founder_requested_change(
    contract_id: int,
    plan_result: dict,
) -> dict:
    """
    Generate one founder-directed proposed clause.

    The plan_result is the exact output of build_improvement_plan().
    """

    if not isinstance(
        plan_result,
        dict,
    ):
        raise ValueError(
            "Improvement plan is invalid."
        )

    plan = plan_result.get(
        "improvement_plan",
        {}
    )

    if not isinstance(
        plan,
        dict,
    ):
        raise ValueError(
            "Improvement plan is invalid."
        )

    if plan.get(
        "status"
    ) != "ready_for_drafting":
        return {
            "success": True,
            "drafting_status": "blocked",
            "reason": (
                "The founder's request is not sufficiently resolved "
                "for drafting."
            ),
            "improvement_plan": plan_result,
        }

    clauses = plan_result.get(
        "affected_clauses",
        []
    )

    clause_ids = {
        str(item)
        for item in plan.get(
            "affected_clause_ids",
            []
        )
    }

    target_clauses = [
        clause
        for clause in clauses
        if str(
            clause.get(
                "clause_id",
                ""
            )
        ) in clause_ids
    ]

    if not target_clauses:
        raise ValueError(
            "No target clause is available for drafting."
        )

    # V1 intentionally drafts ONE clause at a time.
    target_clause = target_clauses[0]

    original_text = _clean_text(
        target_clause.get(
            "text",
            ""
        )
    )

    if not original_text:
        raise ValueError(
            "Target clause contains no source text."
        )

    payload = _build_draft_payload(
        plan_result
    )

    raw = _call_groq([
        {
            "role": "system",
            "content": DRAFT_SYSTEM_PROMPT,
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

    proposal = _parse_and_validate_model_response(
        raw
    )

    user_instruction = _clean_text(
        plan_result.get(
            "user_request",
            ""
        )
    )

    valid, validation_errors = (
        validate_founder_draft(
            original_text=original_text,
            proposed_text=proposal["proposed_text"],
            plan=plan,
            user_instruction=user_instruction,
        )
    )

    if not valid:
        return {
            "success": True,
            "drafting_status": "validation_failed",
            "contract_id": contract_id,
            "area": plan_result.get(
                "area",
                {}
            ),
            "target_clause": {
                "clause_id": str(
                    target_clause.get(
                        "clause_id",
                        ""
                    )
                ),
                "title": _clean_text(
                    target_clause.get(
                        "title",
                        ""
                    )
                ),
            },
            "original_text": original_text,
            "proposal": proposal,
            "validation": {
                "passed": False,
                "errors": validation_errors,
            },
        }

    # Generate a stable founder-directed ID for this exact proposal.
    #
    # The ID is deterministic for the same contract/clause/request/draft,
    # so retrying an unapproved request updates the same proposal. A
    # materially different request or proposed text produces a different ID.
    fingerprint = "|".join(
        [
            str(contract_id),
            str(
                target_clause.get(
                    "clause_id",
                    "",
                )
            ),
            _normalise_text(
                user_instruction
            ),
            _normalise_text(
                proposal["proposed_text"]
            ),
        ]
    )

    digest = hashlib.sha256(
        fingerprint.encode(
            "utf-8"
        )
    ).hexdigest()[:8].upper()

    change_id = f"UC-{digest}"

    change_object = {
        "change_id": change_id,
        "source": "user_requested",
        "contract_id": contract_id,
        "clause_id": str(
            target_clause.get(
                "clause_id",
                ""
            )
        ),
        "clause_title": _clean_text(
            target_clause.get(
                "title",
                f"Clause {target_clause.get('clause_id', '')}"
            )
        ),
        "rule_id": "USER_REQUESTED",
        "issue": _clean_text(
            plan.get(
                "objective",
                ""
            )
        ),
        "change_type": proposal["change_type"],
        "negotiation_objective": "founder_directed",
        "original_text": original_text,
        "proposed_text": proposal["proposed_text"],
        "reason": proposal["reason"],
        "evidence": [
            {
                "clause_id": str(
                    target_clause.get(
                        "clause_id",
                        ""
                    )
                ),
                "text": original_text,
                "relationship": "target_clause",
            }
        ],
        "preserved_facts": proposal[
            "preserved_facts"
        ],
        "risk_notes": proposal[
            "risk_notes"
        ],
        "requirements_addressed": proposal[
            "requirements_addressed"
        ],
        "user_requirements": plan.get(
            "explicit_terms",
            []
        ),
        "change_recommended": True,
        "status": "proposed",
        "validated": True,
    }

    return {
        "success": True,
        "drafting_status": "drafted",
        "contract_id": contract_id,
        "area": plan_result.get(
            "area",
            {}
        ),
        "target_clause": {
            "clause_id": str(
                target_clause.get(
                    "clause_id",
                    ""
                )
            ),
            "title": _clean_text(
                target_clause.get(
                    "title",
                    f"Clause {target_clause.get('clause_id', '')}"
                )
            ),
        },
        "founder_request": user_instruction,
        "improvement_plan": plan,
        "change": change_object,
        "validation": {
            "passed": True,
            "errors": [],
        },
    }
