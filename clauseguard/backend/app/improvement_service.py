# ============================================================
# CLAUSEGUARD - CONTRACT IMPROVEMENT ASSESSMENT
# Feature 3 / Layer 1
# ============================================================
"""
Turns the existing clause/risk analysis into a contract-level list of
"Attention Areas" with controlled improvement strategies.

This layer:
    - works with any saved contract
    - does not ask the user to identify a clause
    - does not rewrite contract language
    - does not create/apply ChangeObjects
    - does not modify the database

Pipeline:
    stored contract analysis
        -> meaningful risk signals
        -> grouped attention areas
        -> controlled strategies
        -> optional AI wording refinement
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

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
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

MIN_IMPROVEMENT_SCORE = 35
MAX_ATTENTION_AREAS = 3


# ============================================================
# CONTROLLED IMPROVEMENT CATALOGUE
# ============================================================
# The LLM can choose only from these strategy IDs.
# Strategy wording is deterministic and therefore cannot be
# hallucinated by the LLM.
# ============================================================

IMPROVEMENT_CATALOGUE = {
    "termination": {
        "title": "Termination Rights",
        "strategies": {
            "TERM_01": (
                "Clarify termination triggers",
                "Review whether the circumstances that permit termination are defined clearly enough.",
            ),
            "TERM_02": (
                "Review termination discretion",
                "Consider whether broad unilateral discretion should be narrowed or defined more precisely.",
            ),
            "TERM_03": (
                "Review notice structure",
                "Consider whether situations requiring advance notice are distinguished from situations where immediate action may apply.",
            ),
            "TERM_04": (
                "Review balance between parties",
                "Compare the termination rights available to each party and review material differences in scope.",
            ),
        },
    },
    "indemnification": {
        "title": "Indemnification",
        "strategies": {
            "INDEM_01": (
                "Narrow indemnification scope",
                "Review whether the range of claims covered by the indemnification obligation is broader than necessary.",
            ),
            "INDEM_02": (
                "Clarify triggering circumstances",
                "Consider whether the circumstances that activate the indemnification obligation should be defined more clearly.",
            ),
            "INDEM_03": (
                "Review defense responsibilities",
                "Review how defense-related responsibilities interact with the indemnification obligation.",
            ),
            "INDEM_04": (
                "Review financial exposure",
                "Consider how the indemnification obligation interacts with the agreement's broader allocation of financial exposure.",
            ),
        },
    },
    "liability": {
        "title": "Liability & Financial Exposure",
        "strategies": {
            "LIAB_01": (
                "Review liability limits",
                "Review whether the agreement establishes a sufficiently clear limitation on the financial exposure described.",
            ),
            "LIAB_02": (
                "Check related liability provisions",
                "Review related provisions to understand how important obligations interact with the stated limitation.",
            ),
            "LIAB_03": (
                "Review fee exposure",
                "Consider whether attorney or legal-fee exposure is clearly defined and appropriately allocated.",
            ),
        },
    },
    "renewal": {
        "title": "Renewal & Exit Terms",
        "strategies": {
            "RENEW_01": (
                "Review automatic renewal",
                "Review whether the renewal mechanism provides sufficient visibility and control before the agreement continues.",
            ),
            "RENEW_02": (
                "Review non-renewal timing",
                "Consider whether the notice window for preventing renewal is practical and clearly communicated.",
            ),
            "RENEW_03": (
                "Review continuing fee obligations",
                "Review whether payment obligations continue after early exit and whether that consequence is clear.",
            ),
        },
    },
    "intellectual_property": {
        "title": "Intellectual Property",
        "strategies": {
            "IP_01": (
                "Narrow ownership transfer",
                "Review whether the intellectual-property assignment reaches only the materials intended to be transferred.",
            ),
            "IP_02": (
                "Protect pre-existing materials",
                "Review how the agreement treats intellectual property that existed before the relationship or engagement.",
            ),
        },
    },
    "confidentiality": {
        "title": "Confidentiality",
        "strategies": {
            "CONF_01": (
                "Review confidentiality duration",
                "Consider whether the duration of the confidentiality obligation is appropriate for the information covered.",
            ),
            "CONF_02": (
                "Clarify information scope",
                "Review whether the definition of confidential information is sufficiently precise.",
            ),
        },
    },
    "restrictive_covenant": {
        "title": "Post-Contract Restrictions",
        "strategies": {
            "RESTRICT_01": (
                "Review restriction scope",
                "Review the activities and relationships covered by the post-contract restriction.",
            ),
            "RESTRICT_02": (
                "Review restriction duration",
                "Consider whether the duration of the restriction is clearly defined and proportionate to its stated purpose.",
            ),
        },
    },
    "payment": {
        "title": "Payment Terms",
        "strategies": {
            "PAY_01": (
                "Review payment timing",
                "Review whether the payment period is practical for the party responsible for payment.",
            ),
            "PAY_02": (
                "Review payment discretion",
                "Consider whether one party has broad discretion to withhold, deduct, or determine amounts payable.",
            ),
        },
    },
    "dispute_resolution": {
        "title": "Dispute Resolution",
        "strategies": {
            "DISPUTE_01": (
                "Review dispute mechanism",
                "Review the mechanism selected for resolving disputes and whether its operation is clear.",
            ),
            "DISPUTE_02": (
                "Review available forums",
                "Consider how the selected dispute mechanism affects the forums and procedures available to the parties.",
            ),
        },
    },
    "general": {
        "title": "Contractual Restrictions",
        "strategies": {
            "GENERAL_01": (
                "Clarify the restriction",
                "Review whether the contractual restriction is stated clearly enough to avoid unnecessary uncertainty.",
            ),
        },
    },
}


FLAG_TO_AREA = {
    "Termination without meaningful notice": "termination",
    "Broad termination right": "termination",
    "Potentially one-sided termination": "termination",

    "Broad indemnification scope": "indemnification",
    "Defense and indemnity obligation": "indemnification",
    "Potentially uncapped liability": "indemnification",
    "Legal-fee exposure": "indemnification",

    "Potentially unlimited liability": "liability",

    "Automatic renewal": "renewal",
    "Extended non-renewal notice": "renewal",
    "Continuing fee obligation": "renewal",

    "Broad intellectual-property assignment": "intellectual_property",
    "Broad rights over pre-existing materials": "intellectual_property",

    "Long-lasting confidentiality obligation": "confidentiality",
    "Broad confidential-information scope": "confidentiality",

    "Non-compete restriction": "restrictive_covenant",
    "Time-limited post-termination restriction": "restrictive_covenant",

    "Extended payment period": "payment",
    "One-sided payment discretion": "payment",

    "Mandatory dispute-resolution mechanism": "dispute_resolution",

    "Potentially significant contractual restriction": "general",
}

FLAG_TO_STRATEGIES = {
    "Termination without meaningful notice": ["TERM_03"],
    "Broad termination right": ["TERM_01", "TERM_02"],
    "Potentially one-sided termination": ["TERM_04"],

    "Broad indemnification scope": ["INDEM_01"],
    "Defense and indemnity obligation": ["INDEM_03"],
    "Potentially uncapped liability": ["INDEM_04"],
    "Legal-fee exposure": ["INDEM_04"],

    "Potentially unlimited liability": ["LIAB_01"],

    "Automatic renewal": ["RENEW_01"],
    "Extended non-renewal notice": ["RENEW_02"],
    "Continuing fee obligation": ["RENEW_03"],

    "Broad intellectual-property assignment": ["IP_01"],
    "Broad rights over pre-existing materials": ["IP_02"],

    "Long-lasting confidentiality obligation": ["CONF_01"],
    "Broad confidential-information scope": ["CONF_02"],

    "Non-compete restriction": ["RESTRICT_01"],
    "Time-limited post-termination restriction": ["RESTRICT_02"],

    "Extended payment period": ["PAY_01"],
    "One-sided payment discretion": ["PAY_02"],

    "Mandatory dispute-resolution mechanism": ["DISPUTE_01", "DISPUTE_02"],

    "Potentially significant contractual restriction": ["GENERAL_01"],
}

# This is contextual rather than a stand-alone negative finding.
# It should not create an improvement area by itself.
CONTEXT_ONLY_FLAGS = {
    "Liability allocation provision",
}


# ============================================================
# HELPERS
# ============================================================

def _score(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _risk_level(value: Any) -> str:
    level = str(value or "").upper()
    if level == "CRITICAL":
        return "HIGH"
    if level in {"HIGH", "MEDIUM", "LOW"}:
        return level
    return "LOW"


def _area_for_flag(flag: str, clause_type: str) -> str:
    if flag in FLAG_TO_AREA:
        return FLAG_TO_AREA[flag]

    return {
        "Termination": "termination",
        "Indemnification": "indemnification",
        "Limitation of Liability": "liability",
        "Auto-Renewal": "renewal",
        "Intellectual Property": "intellectual_property",
        "Confidentiality": "confidentiality",
        "Restrictive Covenant": "restrictive_covenant",
        "Payment": "payment",
        "Dispute Resolution": "dispute_resolution",
    }.get(clause_type, "general")


def _strategy(area_key: str, strategy_id: str) -> Optional[dict]:
    area = IMPROVEMENT_CATALOGUE.get(area_key)
    if not area:
        return None

    item = area["strategies"].get(strategy_id)
    if not item:
        return None

    return {
        "strategy_id": strategy_id,
        "title": item[0],
        "description": item[1],
    }


def _safe_text(value: Any, limit: int = 1800) -> str:
    return str(value or "").strip()[:limit]


# ============================================================
# BUILD DETERMINISTIC GROUPS
# ============================================================

def _build_groups(clauses: list[dict]) -> dict[str, dict]:
    groups: dict[str, dict] = {}

    for clause in clauses:
        clause_id = str(clause.get("clause_id", ""))
        clause_title = str(
            clause.get("title") or f"Clause {clause_id}"
        )
        clause_type = str(
            clause.get("clause_type") or "Other"
        )
        risk_score = _score(clause.get("risk_score"))
        risk_level = _risk_level(clause.get("risk_level"))

        flags = clause.get("risk_flags") or []
        reasons = clause.get("risk_reasons") or []

        # Layer 1 is intentionally limited to HIGH/MEDIUM-style
        # attention areas. LOW findings remain available in the
        # underlying contract analysis but do not consume the founder's limited attention slots.
        if risk_level not in {"HIGH", "MEDIUM"}:
            continue

        if risk_score < MIN_IMPROVEMENT_SCORE:
            continue

        clause_signals = []

        for i, flag in enumerate(flags):
            if not isinstance(flag, str):
                continue

            if flag in CONTEXT_ONLY_FLAGS:
                continue

            area_key = _area_for_flag(flag, clause_type)
            reason = str(
                reasons[i]
                if i < len(reasons)
                else ""
            ).strip()

            groups.setdefault(
                area_key,
                {
                    "area_key": area_key,
                    "max_risk_score": 0,
                    "clause_ids": [],
                    "clauses": {},
                    "signals": [],
                },
            )

            group = groups[area_key]
            group["max_risk_score"] = max(
                group["max_risk_score"],
                risk_score,
            )

            if clause_id not in group["clause_ids"]:
                group["clause_ids"].append(clause_id)

            group["clauses"][clause_id] = {
                "clause_id": clause_id,
                "title": clause_title,
                "clause_type": clause_type,
                "text": _safe_text(
                    clause.get("text")
                ),
            }

            group["signals"].append(
                {
                    "clause_id": clause_id,
                    "flag": flag,
                    "reason": reason,
                }
            )

            clause_signals.append(flag)

        # A clause with only contextual flags should not create an area.
        if not clause_signals:
            continue

    return groups


def _default_strategy_ids(group: dict) -> list[str]:
    result = []

    for signal in group["signals"]:
        for strategy_id in FLAG_TO_STRATEGIES.get(
            signal["flag"],
            [],
        ):
            if strategy_id not in result:
                result.append(strategy_id)

    return result[:3]


def _area_without_ai(
    area_key: str,
    group: dict,
    index: int,
) -> dict:
    catalogue = IMPROVEMENT_CATALOGUE.get(
        area_key,
        IMPROVEMENT_CATALOGUE["general"],
    )

    strategies = []

    for strategy_id in _default_strategy_ids(group):
        item = _strategy(area_key, strategy_id)

        # A strategy may belong to a broader catalogue entry rather
        # than the exact area. Handle that below if necessary.
        if item:
            strategies.append(item)
            continue

        for fallback_area_key in IMPROVEMENT_CATALOGUE:
            item = _strategy(
                fallback_area_key,
                strategy_id,
            )
            if item:
                strategies.append(item)
                break

    if not strategies:
        strategies = [
            {
                "strategy_id": "GENERAL_01",
                "title": IMPROVEMENT_CATALOGUE["general"][
                    "strategies"
                ]["GENERAL_01"][0],
                "description": IMPROVEMENT_CATALOGUE["general"][
                    "strategies"
                ]["GENERAL_01"][1],
            }
        ]

    reasons = [
        s["reason"]
        for s in group["signals"]
        if s["reason"]
    ]

    affected_clauses = [
        group["clauses"][clause_id]
        for clause_id in group["clause_ids"]
    ]

    return {
        "area_id": f"IA-{index:03d}",
        "area_key": area_key,
        "title": catalogue["title"],
        "summary": (
            reasons[0]
            if reasons
            else "This area contains language that may warrant review."
        ),
        "why_review": (
            "The contract contains one or more signals in this area "
            "that may deserve attention before the agreement is finalized."
        ),
        "affected_clauses": affected_clauses,
        "signals": group["signals"],
        "strategies": strategies,
    }


# ============================================================
# GROQ REFINEMENT
# ============================================================

SYSTEM_PROMPT = """
You are ClauseGuard's contract improvement assessment assistant.

Your role is to summarize existing contractual signals, not rewrite
the contract.

The deterministic engine has already identified the possible
improvement areas and supplied the evidence.

Rules:
- Use only supplied signals and clause text.
- Do not invent facts, parties, amounts, dates, durations,
  thresholds, obligations, exceptions, triggers or procedures.
- Do not say that a provision is illegal, invalid, unenforceable,
  unlawful, or legally required.
- Do not call anything an industry or market standard.
- Do not produce replacement contract language.
- Do not introduce exact numerical recommendations.
- Use cautious language such as "may warrant review" or
  "may create exposure".
- Keep the explanation understandable to a non-lawyer.
- Use only the supplied area_key and strategy IDs.

Return ONLY JSON:
{
  "areas": [
    {
      "area_key": "...",
      "summary": "...",
      "why_review": "...",
      "strategy_ids": ["...", "..."]
    }
  ]
}
"""


def _get_client() -> Groq:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "Missing GROQ_API_KEY environment variable."
        )
    return Groq(api_key=GROQ_API_KEY)


def _call_groq(
    messages: list[dict],
    max_tokens: int = 1800,
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
            raise RuntimeError("AI returned an empty response.")
        return content

    except RateLimitError as exc:
        raise RuntimeError("AI service rate limited.") from exc

    except APIStatusError as exc:
        status = getattr(exc, "status_code", 0)
        if status == 401:
            raise RuntimeError("AI authentication failed.") from exc
        raise RuntimeError(
            f"AI provider error ({status})."
        ) from exc

    except APIConnectionError as exc:
        raise RuntimeError(
            "Could not connect to AI provider."
        ) from exc

    except AuthenticationError as exc:
        raise RuntimeError("AI authentication failed.") from exc

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
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _llm_source(groups: dict[str, dict]) -> dict:
    result = []

    for area_key, group in sorted(
        groups.items(),
        key=lambda item: -item[1]["max_risk_score"],
    )[:MAX_ATTENTION_AREAS]:
        result.append(
            {
                "area_key": area_key,
                "title": IMPROVEMENT_CATALOGUE.get(
                    area_key,
                    IMPROVEMENT_CATALOGUE["general"],
                )["title"],
                        "allowed_strategy_ids": _default_strategy_ids(group),
                "signals": group["signals"],
                "clauses": list(group["clauses"].values()),
            }
        )

    return {"areas": result}


def _refine_with_llm(groups: dict[str, dict]) -> dict:
    source = _llm_source(groups)

    prompt = f"""
Here is the deterministic assessment data:

{json.dumps(source, ensure_ascii=False, indent=2)}

For each supplied area, write:
1. a concise plain-English summary of what the supplied signals show;
2. a concise explanation of why this area deserves the founder's attention;
3. choose up to three strategy IDs from the supplied list that are most relevant.

The output is intentionally a shortlist of the most important areas, not
a complete list of every risk in the contract. Do not use priority labels
or risk scores in the explanation.

Do not add facts or recommendations that are not supported by
the supplied data. Do not rewrite clauses.

Return only JSON.
"""

    parsed = json.loads(
        _clean_json(
            _call_groq(
                [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ]
            )
        )
    )

    if not isinstance(parsed, dict):
        raise RuntimeError("Unexpected AI response.")

    if not isinstance(parsed.get("areas"), list):
        raise RuntimeError("AI response missing areas.")

    return parsed


def _valid_refinement(
    refined: dict,
    groups: dict[str, dict],
) -> bool:
    areas = refined.get("areas")
    if not isinstance(areas, list):
        return False

    allowed_keys = set(groups)
    seen = set()

    blocked = (
        "industry standard",
        "market standard",
        "legally required",
        "illegal",
        "invalid",
        "unenforceable",
        "unlawful",
        "guaranteed",
    )

    for area in areas:
        if not isinstance(area, dict):
            return False

        key = str(area.get("area_key", "")).strip()
        if key not in allowed_keys or key in seen:
            return False

        seen.add(key)

        summary = str(area.get("summary", "")).strip()
        why = str(area.get("why_review", "")).strip()

        if not summary or not why:
            return False

        if len(summary) > 700 or len(why) > 700:
            return False

        combined = f"{summary} {why}".lower()

        if any(term in combined for term in blocked):
            return False

        # Numeric recommendations belong to the later drafting layer.
        if re.search(
            r"\b\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|years?|%|percent)\b",
            combined,
            re.IGNORECASE,
        ):
            return False

        allowed_strategy_ids = set(
            _default_strategy_ids(groups[key])
        )

        ids = area.get("strategy_ids")
        if not isinstance(ids, list) or len(ids) > 3:
            return False

        if any(
            strategy_id not in allowed_strategy_ids
            for strategy_id in ids
        ):
            return False

    return True


def _apply_refinement(
    groups: dict[str, dict],
    refined: dict,
) -> list[dict]:
    refined_by_key = {
        area["area_key"]: area
        for area in refined.get("areas", [])
    }

    sorted_groups = sorted(
        groups.values(),
        key=lambda group: -group["max_risk_score"],
    )[:MAX_ATTENTION_AREAS]

    result = []

    for index, group in enumerate(sorted_groups, start=1):
        key = group["area_key"]
        base = _area_without_ai(
            key,
            group,
            index,
        )

        refined_area = refined_by_key.get(key)

        if refined_area:
            base["summary"] = refined_area["summary"]
            base["why_review"] = refined_area["why_review"]

            strategy_ids = refined_area.get(
                "strategy_ids",
                [],
            )

            chosen = []

            for strategy_id in strategy_ids:
                item = _strategy(key, strategy_id)

                if item:
                    chosen.append(item)
                    continue

                for fallback_key in IMPROVEMENT_CATALOGUE:
                    item = _strategy(
                        fallback_key,
                        strategy_id,
                    )
                    if item:
                        chosen.append(item)
                        break

            if chosen:
                base["strategies"] = chosen

        result.append(base)

    return result


# ============================================================
# RESPONSE
# ============================================================

def _response(
    contract_id: int,
    title: str,
    clauses: list[dict],
    areas: list[dict],
    mode: str,
) -> dict:
    return {
        "success": True,
        "assessment_mode": mode,
        "contract": {
            "id": contract_id,
            "title": title,
            "clause_count": len(clauses),
        },
        "assessment_summary": {
            "attention_area_count": len(areas),
        },
        "attention_areas": areas,
    }


# ============================================================
# PUBLIC API
# ============================================================

def analyze_contract_for_improvements(
    contract_id: int,
    contract_row: Any,
) -> dict:
    """
    Analyze a saved contract and return contract-level
    attention areas.

    Reads:
        contracts.clauses_json

    Does not:
        - rerun parsing
        - modify the contract
        - write to the database
        - create ChangeObjects
    """

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

    filename = str(
        contract_row["filename"]
        or "Untitled Contract"
    )

    title = Path(filename).stem.replace(
        "_",
        " ",
    ).strip() or "Untitled Contract"

    groups = _build_groups(clauses)

    if not groups:
        return _response(
            contract_id,
            title,
            clauses,
            [],
            "no_major_signals",
        )

    try:
        refined = _refine_with_llm(groups)

        if _valid_refinement(
            refined,
            groups,
        ):
            return _response(
                contract_id,
                title,
                clauses,
                _apply_refinement(
                    groups,
                    refined,
                ),
                "ai_refined",
            )

    except Exception as exc:
        print(
            f"[IMPROVEMENTS] AI refinement failed: {exc}"
        )

    # Safe fallback: the deterministic engine still returns
    # useful output without relying on the LLM.
    sorted_groups = sorted(
        groups.values(),
        key=lambda group: -group["max_risk_score"],
    )[:MAX_ATTENTION_AREAS]

    areas = [
        _area_without_ai(
            group["area_key"],
            group,
            index,
        )
        for index, group in enumerate(
            sorted_groups,
            start=1,
        )
    ]

    return _response(
        contract_id,
        title,
        clauses,
        areas,
        "deterministic_fallback",
    )
