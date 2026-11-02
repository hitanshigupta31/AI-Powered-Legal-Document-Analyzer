# ============================================================
# CLAUSEGUARD - DRAFT SERVICE
# Controlled AI-assisted contract negotiation
# ============================================================

import json
import re
import os
from typing import Any,Optional
from dataclasses import dataclass, asdict

from dotenv import load_dotenv
from groq import (
    Groq,
    APIConnectionError,
    RateLimitError,
    APIStatusError,
    AuthenticationError,
)

load_dotenv()


# ============================================================
# GROQ CONFIGURATION
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "qwen/qwen3.8-27b"
)

if not GROQ_API_KEY:
    raise RuntimeError(
        "Missing GROQ_API_KEY environment variable."
    )

groq_client = Groq(
    api_key=GROQ_API_KEY
)


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Candidate:
    rule_id: str
    clause_id: str
    issue: str
    reason: str
    evidence: list[str]
    change_policy: dict


@dataclass
class CrossClauseEvidence:
    clause_id: str
    clause_type: str
    text: str
    relationship: str


@dataclass
class ChangeObject:
    change_id: str
    clause_id: str
    clause_title: str
    rule_id: str
    issue: str
    change_type: str
    negotiation_objective: str
    original_text: str
    proposed_text: str
    reason: str
    evidence: list[dict]
    preserved_facts: list[str]
    risk_notes: list[str]
    change_recommended: bool
    status: str = "proposed"
    validated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NoChangeCandidate:
    candidate_id: str
    clause_id: str
    issue: str
    change_recommended: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DraftAnalysisResult:
    success: bool
    contract: dict
    negotiation_objective: str
    analysis_summary: dict
    changes: list[dict]
    no_change_candidates: list[dict]


# ============================================================
# CHANGE POLICY HELPERS
# ============================================================

def default_change_policy() -> dict:
    """
    Conservative fallback policy.

    If a rule does not explicitly define what the AI is allowed
    to change, we prefer NO NEW LEGAL MECHANISMS.
    """

    return {
        "allowed_operations": [
            "remove_existing_language",
            "modify_existing_language",
            "narrow_existing_scope",
        ],

        "allowed_targets": [],

        "allow_new_terms": False,
        "allow_new_notice_period": False,
        "allow_new_cure_period": False,
        "allow_new_obligations": False,
        "allow_new_conditions": False,
        "allow_new_exceptions": False,
        "allow_new_triggers": False,
        "allow_new_monetary_amounts": False,
        "allow_new_procedures": False,
    }


# ============================================================
# NEGOTIATION RULE ENGINE
# ============================================================

NEGOTIATION_RULES = [

    # --------------------------------------------------------
    # INDEMNIFICATION
    # --------------------------------------------------------

    {
        "rule_id": "INDEMNITY_SCOPE_01",

        "clause_types": [
            "Indemnification"
        ],

        "patterns": [
            "any and all claims",
            "any and all",
            "all claims",
            "any claims",
        ],

        "issue": "Broad indemnification scope",

        "reason_template": (
            "The indemnification language uses broad phrasing "
            "('{matched}') that may extend beyond the scope "
            "needed for the identified obligation."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "remove_existing_language",
                "modify_existing_language",
                "narrow_existing_scope",
            ],

            "allowed_targets": [
                "scope_language"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    {
        "rule_id": "INDEMNITY_SCOPE_02",

        "clause_types": [
            "Indemnification"
        ],

        "patterns": [
            "unlimited",
            "not subject to any monetary cap",
            "without limitation",
            "no monetary cap",
            "without limitation as to amount",
        ],

        "issue": (
            "Potentially uncapped indemnification liability"
        ),

        "reason_template": (
            "The indemnification obligation contains language "
            "indicating that it is not limited ('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "remove_existing_language",
            ],

            "allowed_targets": [
                "limitation_language"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    {
        "rule_id": "INDEMNITY_SCOPE_03",

        "clause_types": [
            "Indemnification"
        ],

        "patterns": [
            "indemnify, defend, and hold harmless",
            "indemnify and hold harmless",
            "hold harmless",
        ],

        "issue": "Defense and indemnity obligation",

        "reason_template": (
            "The clause imposes an indemnity/defense obligation "
            "using the phrase '{matched}'."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "remove_existing_language",
            ],

            "allowed_targets": [
                "defense_language",
                "indemnity_language",
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    # --------------------------------------------------------
    # LIABILITY
    # --------------------------------------------------------

    {
        "rule_id": "LIABILITY_CAP_01",

        "clause_types": [
            "Limitation of Liability",
            "Indemnification"
        ],

        "patterns": [
            "unlimited liability",
            "unlimited",
            "not subject to any monetary cap",
            "no monetary cap",
        ],

        "issue": "Missing or ineffective liability cap",

        "reason_template": (
            "The clause contains language suggesting "
            "unlimited liability ('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "remove_existing_language",
            ],

            "allowed_targets": [
                "liability_scope",
                "limitation_language",
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    {
        "rule_id": "LIABILITY_CAP_02",

        "clause_types": [
            "Limitation of Liability"
        ],

        "patterns": [
            "does not apply to indemnif",
            "exclude.*indemnif",
            "indemnif.*exclud",
            "cap.*not apply.*indemnif",
        ],

        "issue": (
            "Liability cap excludes indemnification claims"
        ),

        "reason_template": (
            "The liability limitation appears to exclude "
            "indemnification claims ('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "remove_existing_language",
            ],

            "allowed_targets": [
                "exclusion_language"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    # --------------------------------------------------------
    # TERMINATION
    # --------------------------------------------------------

    {
        "rule_id": "TERMINATION_NOTICE_01",

        "clause_types": [
            "Termination"
        ],

        "patterns": [
            "without notice",
            "without prior notice",
            "immediately and without notice",
            "immediately",
        ],

        "issue": (
            "Termination without meaningful notice"
        ),

        "reason_template": (
            "The termination clause contains language allowing "
            "action without notice ('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "remove_existing_language",
                "modify_existing_language",
            ],

            "allowed_targets": [
                "notice_language"
            ],

            # IMPORTANT:
            # We deliberately do NOT allow the AI to invent
            # "10 days", "30 days", cure periods, etc.
            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    {
        "rule_id": "TERMINATION_NOTICE_02",

        "clause_types": [
            "Termination"
        ],

        "patterns": [
            "at any time",
            "for any reason",
            "for no reason",
            "without cause",
            "sole discretion",
        ],

        "issue": (
            "Broad unilateral termination right"
        ),

        "reason_template": (
            "The termination right uses broad unilateral "
            "language ('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "remove_existing_language",
            ],

            "allowed_targets": [
                "discretion_language",
                "termination_scope"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    # --------------------------------------------------------
    # CONFIDENTIALITY
    # --------------------------------------------------------

    {
        "rule_id": "CONFIDENTIALITY_DURATION_01",

        "clause_types": [
            "Confidentiality"
        ],

        "patterns": [
            "perpetual",
            "at all times",
            "survive termination",
            "indefinitely",
        ],

        "issue": (
            "Indefinite confidentiality obligation"
        ),

        "reason_template": (
            "The confidentiality obligation contains "
            "potentially indefinite duration language ('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "narrow_existing_scope",
            ],

            "allowed_targets": [
                "duration_language"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    {
        "rule_id": "CONFIDENTIALITY_SCOPE_01",

        "clause_types": [
            "Confidentiality"
        ],

        "patterns": [
            "all confidential information",
            "non-public information",
            "trade secrets",
        ],

        "issue": (
            "Broad confidential information definition"
        ),

        "reason_template": (
            "The confidentiality language uses broad scope "
            "('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "narrow_existing_scope",
            ],

            "allowed_targets": [
                "scope_language"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    # --------------------------------------------------------
    # PAYMENT
    # --------------------------------------------------------

    {
        "rule_id": "PAYMENT_TERMS_01",

        "clause_types": [
            "Payment"
        ],

        "patterns": [
            "net 60",
            "net sixty",
            "net 90",
            "ninety days",
            "60 days",
        ],

        "issue": "Extended payment period",

        "reason_template": (
            "The payment terms contain an extended period "
            "('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language"
            ],

            "allowed_targets": [
                "payment_period"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    # --------------------------------------------------------
    # RESTRICTIVE COVENANT
    # --------------------------------------------------------

    {
        "rule_id": "NONCOMPETE_SCOPE_01",

        "clause_types": [
            "Restrictive Covenant"
        ],

        "patterns": [
            "non-compete",
            "non compete",
            "noncompetition",
            "competing business",
        ],

        "issue": (
            "Non-compete restriction present"
        ),

        "reason_template": (
            "The clause contains a restrictive covenant "
            "('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language",
                "narrow_existing_scope",
            ],

            "allowed_targets": [
                "restriction_scope"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },

    # --------------------------------------------------------
    # AMBIGUOUS OBLIGATION
    # --------------------------------------------------------

    {
        "rule_id": "AMBIGUOUS_OBLIGATION_01",

        "clause_types": [
            "Indemnification",
            "Termination",
            "Confidentiality",
            "Restrictive Covenant",
            "Payment",
            "Services",
            "Other"
        ],

        "patterns": [
            "reasonable efforts",
            "best efforts",
            "commercially reasonable",
            "material adverse",
            "in good faith",
        ],

        "issue": (
            "Ambiguous obligation standard"
        ),

        "reason_template": (
            "The clause uses an ambiguous standard ('{matched}')."
        ),

        "change_type": "modify",

        "change_policy": {
            "allowed_operations": [
                "modify_existing_language"
            ],

            "allowed_targets": [
                "standard_language"
            ],

            "allow_new_terms": False,
            "allow_new_notice_period": False,
            "allow_new_cure_period": False,
            "allow_new_obligations": False,
            "allow_new_conditions": False,
            "allow_new_exceptions": False,
            "allow_new_triggers": False,
            "allow_new_monetary_amounts": False,
            "allow_new_procedures": False,
        },
    },
]


# ============================================================
# RULE LOOKUP
# ============================================================

def _get_rule(
    rule_id: str
) -> Optional[dict]:

    for rule in NEGOTIATION_RULES:

        if rule["rule_id"] == rule_id:
            return rule

    return None


def _get_change_policy(
    rule_id: str
) -> dict:

    rule = _get_rule(rule_id)

    if not rule:
        return default_change_policy()

    policy = rule.get(
        "change_policy"
    )

    if not policy:
        return default_change_policy()

    return policy


# ============================================================
# CANDIDATE DETECTION
# ============================================================

def find_negotiation_candidates(
    clauses: list[dict]
) -> list[Candidate]:

    candidates = []

    for clause in clauses:

        clause_id = str(
            clause.get(
                "clause_id",
                ""
            )
        )

        clause_type = clause.get(
            "clause_type",
            "Other"
        )

        text = clause.get(
            "text",
            ""
        )

        text_lower = text.lower()

        for rule in NEGOTIATION_RULES:

            if clause_type not in rule[
                "clause_types"
            ]:
                continue

            for pattern in rule[
                "patterns"
            ]:

                # Negative patterns
                if "negative_patterns" in rule:

                    excluded = False

                    for neg_pattern in rule[
                        "negative_patterns"
                    ]:

                        if re.search(
                            neg_pattern,
                            text_lower,
                            re.IGNORECASE
                        ):

                            excluded = True
                            break

                    if excluded:
                        continue

                if re.search(
                    pattern,
                    text_lower,
                    re.IGNORECASE
                ):

                    matched = _extract_matched_text(
                        text,
                        pattern
                    )

                    reason = rule[
                        "reason_template"
                    ].format(
                        matched=matched
                    )

                    evidence = (
                        _extract_evidence_sentences(
                            text,
                            pattern
                        )
                    )

                    candidates.append(
                        Candidate(
                            rule_id=rule[
                                "rule_id"
                            ],

                            clause_id=
                                clause_id,

                            issue=
                                rule["issue"],

                            reason=
                                reason,

                            evidence=
                                evidence,

                            change_policy=
                                rule.get(
                                    "change_policy",
                                    default_change_policy()
                                )
                        )
                    )

                    break

    return candidates


def _extract_matched_text(
    text: str,
    pattern: str
) -> str:

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(0)

    return pattern


def _extract_evidence_sentences(
    text: str,
    pattern: str
) -> list[str]:

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    evidence = []

    for sentence in sentences:

        if re.search(
            pattern,
            sentence,
            re.IGNORECASE
        ):

            evidence.append(
                sentence.strip()
            )

    return evidence[:3]


# ============================================================
# CROSS-CLAUSE ANALYSIS
# ============================================================

CLAUSE_RELATIONSHIPS = {

    "Indemnification": [
        "Limitation of Liability",
        "Termination",
        "Payment"
    ],

    "Limitation of Liability": [
        "Indemnification",
        "Termination"
    ],

    "Termination": [
        "Indemnification",
        "Limitation of Liability",
        "Confidentiality",
        "Restrictive Covenant",
        "Payment"
    ],

    "Confidentiality": [
        "Termination",
        "Intellectual Property",
        "Restrictive Covenant"
    ],

    "Restrictive Covenant": [
        "Termination",
        "Confidentiality",
        "Payment"
    ],

    "Payment": [
        "Termination",
        "Indemnification",
        "Limitation of Liability"
    ],

    "Intellectual Property": [
        "Termination",
        "Confidentiality",
        "Payment"
    ],
}


def find_related_clauses(
    target_clause: dict,
    all_clauses: list[dict]
) -> list[CrossClauseEvidence]:

    target_type = target_clause.get(
        "clause_type",
        ""
    )

    target_id = str(
        target_clause.get(
            "clause_id",
            ""
        )
    )

    related_types = CLAUSE_RELATIONSHIPS.get(
        target_type,
        []
    )

    evidence = []

    for clause in all_clauses:

        clause_id = str(
            clause.get(
                "clause_id",
                ""
            )
        )

        if clause_id == target_id:
            continue

        if clause.get(
            "clause_type"
        ) in related_types:

            evidence.append(
                CrossClauseEvidence(
                    clause_id=clause_id,

                    clause_type=clause.get(
                        "clause_type",
                        ""
                    ),

                    text=clause.get(
                        "text",
                        ""
                    )[:500],

                    relationship=
                        _describe_relationship(
                            target_type,
                            clause.get(
                                "clause_type"
                            )
                        )
                )
            )

    return evidence[:5]


def _describe_relationship(
    type1: str,
    type2: str
) -> str:

    relationships = {

        (
            "Indemnification",
            "Limitation of Liability"
        ):
            "Indemnification obligations may exceed liability cap",

        (
            "Limitation of Liability",
            "Indemnification"
        ):
            "Liability cap may not cover indemnification claims",

        (
            "Indemnification",
            "Termination"
        ):
            "Indemnification may survive termination",

        (
            "Termination",
            "Indemnification"
        ):
            "Termination may trigger indemnification obligations",

        (
            "Termination",
            "Confidentiality"
        ):
            "Confidentiality obligations survive termination",

        (
            "Confidentiality",
            "Termination"
        ):
            "Termination does not end confidentiality",

        (
            "Restrictive Covenant",
            "Termination"
        ):
            "Restrictions activate on termination",

        (
            "Termination",
            "Restrictive Covenant"
        ):
            "Termination triggers non-compete",

        (
            "Termination",
            "Limitation of Liability"
        ):
            "Termination may affect liability exposure",

        (
            "Limitation of Liability",
            "Termination"
        ):
            "Liability cap applies post-termination",

        (
            "Intellectual Property",
            "Termination"
        ):
            "IP ownership survives termination",

        (
            "Termination",
            "Intellectual Property"
        ):
            "Termination triggers IP transfer",
    }

    return relationships.get(
        (type1, type2),
        f"Related to {type2}"
    )


# ============================================================
# LLM PROMPT
# ============================================================

DRAFT_SYSTEM_PROMPT = """
You are ClauseGuard, an AI contract negotiation assistant.

You do NOT rewrite contracts freely.

You operate inside an explicit CHANGE POLICY supplied by the
deterministic negotiation engine.

Your job is to produce the smallest defensible modification
that addresses the detected contractual issue.

CORE PRINCIPLE:

The rule engine decides WHAT KIND of change is permitted.

You decide HOW to formulate that permitted change.

You MUST NOT invent new legal mechanisms.

STRICT RULES:

1. Preserve parties, roles, dates, amounts, definitions,
   durations, geographic scope and existing obligations unless
   the supplied change policy explicitly permits modification.

2. Do not invent:
   - notice periods
   - cure periods
   - monetary amounts
   - new obligations
   - new conditions
   - new exceptions
   - new triggers
   - new procedural requirements
   - governing law
   - jurisdiction
   - venue
   - arbitration

3. If the policy says a category is forbidden, do not introduce it.

4. Prefer editing existing language over writing a new clause.

5. You do NOT need to solve every detected issue. If at least one
   detected issue can be safely addressed by modifying existing
   language within the policy, propose that smallest change and
   leave the other issue unresolved. Only return false when no
   defensible modification is available.

6. Do not claim that a proposed term is "standard industry
   practice" unless the contract evidence supplied actually
   establishes that fact.

7. Do not use external market assumptions.

8. The proposal must remain grounded in the supplied contract.

9. preserved_facts is optional supporting metadata, not a second
   representation of the contract. Prefer returning an empty list.
   Only include a preserved fact when it is a short, concrete fact
   whose wording is directly supported by the supplied clause text.
   Do not write meta-statements such as "remains unchanged",
   "the parties remain", or "the trigger remains".

9. A related clause is evidence, not permission to rewrite it.

10. Do not silently change the legal trigger of an obligation.

Return ONLY JSON:

{
  "change_recommended": true/false,
  "reason": "...",
  "proposed_text": "...",
  "preserved_facts": [],
  "risk_notes": [],
  "change_type": "modify|remove|add"
}
"""


# ============================================================
# GROQ
# ============================================================

def call_groq_draft(
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1200
) -> str:

    try:

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_object"
            }
        )

        return response.choices[
            0
        ].message.content

    except RateLimitError as exc:

        raise RuntimeError(
            "AI service rate limited."
        ) from exc

    except APIStatusError as exc:

        status = getattr(
            exc,
            "status_code",
            0
        )

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


def _clean_json_text(
    raw_text: str
) -> str:

    if not raw_text:
        return ""

    text = raw_text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


# ============================================================
# DRAFT GENERATION
# ============================================================

def generate_draft_proposal(
    contract_data: dict,
    target_clause: dict,
    related_evidence: list[CrossClauseEvidence],
    candidates: list[Candidate],
    negotiation_objective: str
) -> dict:

    """
    Generate ONE proposal for ONE clause.

    Multiple rule signals belonging to the same clause are
    combined into one evidence package.
    """

    clause_text = target_clause.get(
        "text",
        ""
    )

    clause_type = target_clause.get(
        "clause_type",
        "Other"
    )

    clause_title = target_clause.get(
        "title",
        f"Clause {target_clause.get('clause_id', '')}"
    )

    # --------------------------------------------------------
    # Combine policies conservatively
    #
    # A capability is allowed only when EVERY applicable
    # candidate permits it.
    # --------------------------------------------------------

    policies = [
        candidate.change_policy
        for candidate in candidates
    ]

    combined_policy = _combine_change_policies(
        policies
    )

    evidence_package = {

        "target_clause": {
            "clause_id":
                target_clause.get("clause_id"),

            "clause_type":
                clause_type,

            "clause_title":
                clause_title,

            "text":
                clause_text,
        },

        "detected_issues": [

            {
                "rule_id":
                    candidate.rule_id,

                "issue":
                    candidate.issue,

                "reason":
                    candidate.reason,

                "evidence":
                    candidate.evidence
            }

            for candidate in candidates
        ],

        "change_policy":
            combined_policy,

        "related_clauses": [

            {
                "clause_id":
                    evidence.clause_id,

                "clause_type":
                    evidence.clause_type,

                "text":
                    evidence.text,

                "relationship":
                    evidence.relationship
            }

            for evidence in related_evidence
        ],

        "negotiation_objective":
            negotiation_objective
    }

    user_prompt = f"""
Analyze this contractual issue for negotiation.

EVIDENCE PACKAGE:

{json.dumps(
    evidence_package,
    ensure_ascii=False,
    indent=2
)}

Your proposal MUST remain inside the supplied CHANGE POLICY.

IMPORTANT:

If the policy forbids a new notice period, do not create one.

If the policy forbids a cure period, do not create one.

MULTIPLE DETECTED ISSUES:
- Treat each detected issue independently.
- Some issues may be addressable by modifying existing language even when another issue is not.
- Do NOT return false merely because one detected issue would require a forbidden new mechanism.
- For this clause, first identify which detected issue has an allowed target and allowed operation.
- If an allowed target can be modified without introducing a forbidden mechanism, make that smallest modification and leave the unaddressable issue unresolved.
- In particular, a broad discretion issue can be addressed by modifying the existing discretion language; it does not require inventing a notice period or cure period.

If the policy forbids new triggers, do not add breach,
negligence, materiality, intent, causation, or similar
conditions.

If a safe revision is impossible within the policy,
return change_recommended=false.

REASONING STYLE:
- Keep "reason" concise and user-facing.
- Explain the contractual issue and why the proposed wording addresses it.
- Do not discuss these instructions, the change policy, prompt constraints,
  or what you "cannot" do.
- Do not claim that a term is an industry or market standard unless that fact
  is explicitly supported by the supplied contract evidence.
- Do not claim a cross-clause legal effect unless the supplied clause text
  actually supports that conclusion.

PRESERVED FACTS:
- Each preserved fact must be directly grounded in the supplied contract text.
- Use concrete facts such as parties, existing rights, existing triggers,
  existing amounts, and existing obligations.
- Do not invent a fact merely to justify the rewrite.
- When modifying an allowed target, prefer changing or removing the exact existing phrase identified by that rule's evidence.
- Do not attempt to solve an unaddressable issue by introducing a new legal mechanism.

Return ONLY:

{{
  "change_recommended": true/false,
  "reason": "...",
  "proposed_text": "...",
  "preserved_facts": [],
  "risk_notes": [],
  "change_type": "modify|remove|add"
}}
"""

    raw_content = call_groq_draft(
        [
            {
                "role": "system",
                "content": DRAFT_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    )

    cleaned = _clean_json_text(
        raw_content
    )

    try:

        parsed = json.loads(
            cleaned
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "LLM returned invalid JSON."
        ) from exc

    required = [
        "change_recommended",
        "reason",
        "proposed_text",
        "preserved_facts",
        "risk_notes",
        "change_type"
    ]

    for field in required:

        if field not in parsed:

            raise RuntimeError(
                f"LLM response missing: {field}"
            )

    return parsed


# ============================================================
# POLICY COMBINATION
# ============================================================

def _combine_change_policies(
    policies: list[dict]
) -> dict:

    if not policies:
        return default_change_policy()

    combined = default_change_policy()

    # --------------------------------------------------------
    # Operations:
    # intersection = only operations every rule permits
    # --------------------------------------------------------

    operation_sets = [
        set(
            policy.get(
                "allowed_operations",
                []
            )
        )
        for policy in policies
    ]

    common_operations = (
        set.intersection(
            *operation_sets
        )
        if operation_sets
        else set()
    )

    combined[
        "allowed_operations"
    ] = sorted(
        common_operations
    )

    # --------------------------------------------------------
    # Targets:
    # union is safe because targets describe where the
    # applicable rules permit the AI to work.
    # --------------------------------------------------------

    targets = set()

    for policy in policies:

        targets.update(
            policy.get(
                "allowed_targets",
                []
            )
        )

    combined[
        "allowed_targets"
    ] = sorted(targets)

    # --------------------------------------------------------
    # Boolean permissions:
    # ALL rules must permit a capability.
    # --------------------------------------------------------

    boolean_fields = [

        "allow_new_terms",
        "allow_new_notice_period",
        "allow_new_cure_period",
        "allow_new_obligations",
        "allow_new_conditions",
        "allow_new_exceptions",
        "allow_new_triggers",
        "allow_new_monetary_amounts",
        "allow_new_procedures",
    ]

    for field in boolean_fields:

        combined[field] = all(
            policy.get(
                field,
                False
            )
            for policy in policies
        )

    return combined


# ============================================================
# VALIDATION
# ============================================================

def validate_proposal(
    proposal: dict,
    target_clause: dict,
    candidates: list[Candidate],
    related_evidence: list[CrossClauseEvidence]
) -> tuple[bool, list[str]]:

    errors = []

    original_text = target_clause.get(
        "text",
        ""
    ).strip()

    if not original_text:

        errors.append(
            "Target clause contains no source text."
        )

        return False, errors

    policy = _combine_change_policies(
        [
            candidate.change_policy
            for candidate in candidates
        ]
    )

    if not proposal.get(
        "change_recommended"
    ):

        return True, []

    proposed_text = proposal.get(
        "proposed_text",
        ""
    ).strip()

    if not proposed_text:

        errors.append(
            "change_recommended=true but proposed_text is empty."
        )

        return False, errors

    # --------------------------------------------------------
    # Policy enforcement
    # --------------------------------------------------------

    errors.extend(
        _validate_change_policy(
            original_text,
            proposed_text,
            policy
        )
    )

    # --------------------------------------------------------
    # Evidence validation
    # --------------------------------------------------------

    evidence_valid, evidence_errors = _validate_evidence(
        proposal,
        target_clause,
        related_evidence
    )

    if not evidence_valid:
        errors.extend(evidence_errors)

    # Explanation quality is part of hard validation. A proposal can be
    # textually safe but still misleading if its rationale relies on
    # unsupported market claims or exposes internal prompt mechanics.
    errors.extend(_validate_explanation(proposal))

    return (
        len(errors) == 0,
        errors
    )


def _validate_change_policy(
    original_text: str,
    proposed_text: str,
    policy: dict
) -> list[str]:

    errors = []

    original_lower = original_text.lower()
    proposed_lower = proposed_text.lower()

    # --------------------------------------------------------
    # New notice periods
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_notice_period",
        False
    ):

        notice_pattern = (
            r"\b\d+\s*"
            r"(?:day|days|week|weeks|month|months)"
            r"\s+(?:prior\s+)?notice\b"
        )

        if (
            re.search(
                notice_pattern,
                proposed_lower
            )
            and not re.search(
                notice_pattern,
                original_lower
            )
        ):

            errors.append(
                "Proposal introduces a new notice period."
            )

    # --------------------------------------------------------
    # Cure periods
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_cure_period",
        False
    ):

        cure_patterns = [

            r"\bcure period\b",

            r"\b\d+\s*day[s]?\s+to\s+cure\b",

            r"\bperiod\s+to\s+cure\b",

            r"\bopportunity\s+to\s+cure\b",
        ]

        for pattern in cure_patterns:

            if (
                re.search(
                    pattern,
                    proposed_lower
                )
                and not re.search(
                    pattern,
                    original_lower
                )
            ):

                errors.append(
                    "Proposal introduces a new cure period."
                )

                break

    # --------------------------------------------------------
    # New monetary amounts
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_monetary_amounts",
        False
    ):

        original_amounts = set(
            re.findall(
                r"\$[\d,]+(?:\.\d+)?",
                original_text
            )
        )

        proposed_amounts = set(
            re.findall(
                r"\$[\d,]+(?:\.\d+)?",
                proposed_text
            )
        )

        new_amounts = (
            proposed_amounts
            - original_amounts
        )

        if new_amounts:

            errors.append(
                "Proposal introduces new monetary amount(s): "
                + ", ".join(
                    sorted(new_amounts)
                )
            )

    # --------------------------------------------------------
    # New legal mechanisms
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_conditions",
        False
    ):

        condition_patterns = [

            r"\bprovided that\b",

            r"\bsubject to\b",

            r"\bon the condition that\b",

            r"\bif and only if\b",
        ]

        for pattern in condition_patterns:

            if (
                re.search(
                    pattern,
                    proposed_lower
                )
                and not re.search(
                    pattern,
                    original_lower
                )
            ):

                errors.append(
                    "Proposal introduces a new condition: "
                    f"{pattern}"
                )

    # --------------------------------------------------------
    # New procedural language
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_procedures",
        False
    ):

        procedure_patterns = [

            r"\bin writing\b",

            r"\bwritten notice\b",

            r"\bnotify\b",

            r"\bnotification\b",

            r"\bdispute resolution\b",

            r"\barbitration\b",

            r"\bmediation\b",
        ]

        for pattern in procedure_patterns:

            if (
                re.search(
                    pattern,
                    proposed_lower
                )
                and not re.search(
                    pattern,
                    original_lower
                )
            ):

                errors.append(
                    "Proposal introduces new procedural language: "
                    f"{pattern}"
                )

    # --------------------------------------------------------
    # New legal triggers
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_triggers",
        False
    ):

        trigger_patterns = [

            r"\bbreach\b",

            r"\bnegligence\b",

            r"\bnegligent\b",

            r"\bwillful misconduct\b",

            r"\bmaterial breach\b",

            r"\bintentional misconduct\b",

            r"\bcaused by\b",

            r"\bto the extent caused\b",
        ]

        for pattern in trigger_patterns:

            if (
                re.search(
                    pattern,
                    proposed_lower
                )
                and not re.search(
                    pattern,
                    original_lower
                )
            ):

                errors.append(
                    "Proposal introduces a new legal trigger: "
                    f"{pattern}"
                )

    # --------------------------------------------------------
    # New exception language
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_exceptions",
        False
    ):

        exception_patterns = [

            r"\bexcept\b",

            r"\bexcept that\b",

            r"\bunless\b",

            r"\bprovided however\b",

            r"\bnotwithstanding\b",
        ]

        for pattern in exception_patterns:

            if (
                re.search(
                    pattern,
                    proposed_lower
                )
                and not re.search(
                    pattern,
                    original_lower
                )
            ):

                errors.append(
                    "Proposal introduces a new exception: "
                    f"{pattern}"
                )

    # --------------------------------------------------------
    # New obligations
    # --------------------------------------------------------

    if not policy.get(
        "allow_new_obligations",
        False
    ):

        obligation_patterns = [

            r"\bshall provide\b",

            r"\bshall notify\b",

            r"\bshall deliver\b",

            r"\bshall maintain\b",

            r"\bshall obtain\b",

            r"\bmust provide\b",

            r"\bmust notify\b",
        ]

        for pattern in obligation_patterns:

            if (
                re.search(
                    pattern,
                    proposed_lower
                )
                and not re.search(
                    pattern,
                    original_lower
                )
            ):

                errors.append(
                    "Proposal introduces a new obligation: "
                    f"{pattern}"
                )

    return errors


# ============================================================
# EVIDENCE VALIDATION
# ============================================================

_GENERIC_FACT_WORDS = {
    "parties", "party", "obligation", "obligations", "trigger",
    "condition", "conditions", "definition", "defined", "right",
    "rights", "scope", "language", "clause", "contract", "term",
    "terms", "item", "items", "covered", "coverage", "standard",
    "fact", "facts", "existing", "current", "original", "text"
}


def _normalise_evidence_text(text: str) -> str:
    """Normalize contract/evidence text for conservative matching."""
    text = (text or "").lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fact_anchor_words(fact: str) -> list[str]:
    """Extract meaningful anchors from an LLM-described preserved fact."""
    words = re.findall(r"\b[a-z0-9]{3,}\b", _normalise_evidence_text(fact))
    return [word for word in words if word not in _GENERIC_FACT_WORDS]


def _contains_fact_in_source(fact: str, source_texts: list[str]) -> bool:
    """
    Check whether a preserved fact is grounded in supplied contract text.

    The previous validator required every four-letter word in the fact to
    appear in the source. That incorrectly rejected legitimate summaries such
    as "Service definition" because "definition" is a descriptor rather than
    contract content. We now require meaningful anchors instead.
    """
    anchors = _fact_anchor_words(fact)

    if not anchors:
        return True

    normalized_sources = [
        _normalise_evidence_text(text)
        for text in source_texts
        if text
    ]

    if not normalized_sources:
        return False

    for source in normalized_sources:
        source_words = set(source.split())
        matched = sum(1 for anchor in anchors if anchor in source_words)

        # For short facts, all meaningful anchors should be present.
        if len(anchors) <= 2 and matched == len(anchors):
            return True

        # For longer summaries, require a strong majority while avoiding
        # false rejection from harmless wording differences.
        if len(anchors) > 2 and matched / len(anchors) >= 0.70:
            return True

    return False


def _dedupe_evidence_items(items: list[dict]) -> list[dict]:
    """Remove duplicate evidence while preserving order."""
    seen = set()
    result = []

    for item in items:
        key = (
            str(item.get("clause_id", "")),
            _normalise_evidence_text(item.get("text", "")),
            item.get("relationship", "")
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def _validate_explanation(proposal: dict) -> list[str]:
    """Reject explanations that contain unsupported market/legal assertions."""
    errors = []

    explanation_parts = []
    explanation_parts.append(str(proposal.get("reason", "")))
    explanation_parts.extend(
        str(note) for note in proposal.get("risk_notes", [])
    )

    explanation = " ".join(explanation_parts).lower()

    unsupported_claim_patterns = [
        (r"\bstandard industry practice\b", "unsupported industry-practice claim"),
        (r"\bindustry standard\b", "unsupported industry-standard claim"),
        (r"\bmarket standard\b", "unsupported market-standard claim"),
        (r"\bstandard commercial practice\b", "unsupported commercial-practice claim"),
        (r"\bcommon industry practice\b", "unsupported industry-practice claim"),
        (r"\bstandard negotiation point\b", "unsupported negotiation-standard claim"),
        (r"\bstandard contractual interpretation\b", "unsupported interpretation claim"),
    ]

    for pattern, description in unsupported_claim_patterns:
        if re.search(pattern, explanation):
            errors.append(f"Explanation contains an {description}.")

    # Do not allow the model to expose internal prompt/policy mechanics as the
    # user-facing legal rationale.
    meta_patterns = [
        r"\bthe change policy permits\b",
        r"\bthe policy forbids\b",
        r"\bwithin the strict constraints\b",
        r"\bi cannot specify\b",
        r"\bi cannot add\b",
        r"\bthe most defensible modification within\b",
        r"\bas instructed\b",
    ]

    for pattern in meta_patterns:
        if re.search(pattern, explanation):
            errors.append("Explanation exposes internal drafting-policy mechanics.")
            break

    return errors


def _validate_evidence(
    proposal: dict,
    target_clause: dict,
    related_evidence: list[CrossClauseEvidence]
) -> tuple[bool, list[str]]:
    """Validate preserved facts and evidence against actual contract text."""
    errors = []

    target_text = target_clause.get("text", "")
    source_texts = [target_text]
    source_texts.extend(
        evidence.text
        for evidence in related_evidence
        if evidence.text
    )

    preserved = proposal.get("preserved_facts", [])

    if not isinstance(preserved, list):
        errors.append("preserved_facts must be a list.")
        return False, errors

    for fact in preserved:
        if not isinstance(fact, str) or not fact.strip():
            errors.append("A preserved fact is empty or invalid.")
            continue

        # Preserved facts are supporting metadata, not a second source of
        # truth. If the model supplies one, require it to correspond to an
        # actual phrase in the supplied contract text. This prevents
        # paraphrased hallucinations such as "claims arise out of breach".
        fact_normalized = _normalise_evidence_text(fact)
        grounded = any(
            fact_normalized
            and fact_normalized in _normalise_evidence_text(source)
            for source in source_texts
            if source
        )

        if not grounded:
            errors.append(
                f"Preserved fact is not grounded in supplied contract text: {fact}"
            )

    return len(errors) == 0, errors


# ============================================================
# DETERMINISTIC SAFE FALLBACKS
# ============================================================

def _build_deterministic_safe_fallback(
    target_clause: dict,
    candidates: list[Candidate]
) -> Optional[dict]:
    """
    Build a minimal, rule-authorized fallback when the LLM cannot
    produce a proposal that survives hard validation.

    This is deliberately narrow: it only removes or modifies
    language already identified by the deterministic rule engine.
    It never invents a notice period, cure period, amount, trigger,
    exception, procedure, or new contractual obligation.
    """
    original_text = target_clause.get("text", "")
    if not original_text.strip():
        return None

    rule_ids = {candidate.rule_id for candidate in candidates}
    proposed_text = original_text
    reason = ""
    change_type = "modify"

    # Clause-level termination fallback:
    # remove the existing "sole discretion" qualifier rather than
    # inventing a notice/cure mechanism.
    if "TERMINATION_NOTICE_02" in rule_ids:
        pattern = re.compile(r"\bin\s+its\s+sole\s+discretion\b", re.IGNORECASE)
        if pattern.search(proposed_text):
            proposed_text = pattern.sub("", proposed_text, count=1)
            proposed_text = re.sub(r"\s{2,}", " ", proposed_text).strip()
            reason = (
                "The clause grants termination authority using the phrase "
                "\"sole discretion\". Removing that qualifier narrows the "
                "existing termination language without adding a new notice "
                "period, cure period, or other contractual mechanism."
            )

    # Indemnification fallback:
    # remove existing breadth/limitation language. This is a true
    # narrowing of language already present in the contract.
    if proposed_text == original_text and (
        "INDEMNITY_SCOPE_01" in rule_ids
        or "INDEMNITY_SCOPE_02" in rule_ids
    ):
        changed = False

        if "INDEMNITY_SCOPE_01" in rule_ids:
            updated = re.sub(
                r"\bany\s+and\s+all\s+claims\b",
                "claims",
                proposed_text,
                count=1,
                flags=re.IGNORECASE
            )
            if updated != proposed_text:
                proposed_text = updated
                changed = True

        if "INDEMNITY_SCOPE_02" in rule_ids:
            updated = re.sub(
                r",?\s*without\s+limitation\s+as\s+to\s+amount\s+or\s+type\s+of\s+damages\.?",
                ".",
                proposed_text,
                count=1,
                flags=re.IGNORECASE
            )
            if updated != proposed_text:
                proposed_text = re.sub(r"\s{2,}", " ", updated).strip()
                changed = True

        if changed:
            reason = (
                "The indemnification clause contains existing language that "
                "broadens the scope of the obligation. The proposed wording "
                "removes that existing breadth without introducing a new legal "
                "trigger, condition, amount, exception, or procedure."
            )

    if proposed_text == original_text:
        return None

    return {
        "change_recommended": True,
        "reason": reason,
        "proposed_text": proposed_text,
        "preserved_facts": [],
        "risk_notes": [
            "This fallback makes only a narrow modification to existing contract language."
        ],
        "change_type": change_type,
    }


# ============================================================
# ANALYZE CONTRACT
# ============================================================

def analyze_contract_for_draft(
    contract_id: int,
    contract_row,
    negotiation_objective: str = "protect_my_side"
) -> DraftAnalysisResult:

    valid_objectives = [
        "protect_my_side",
        "balanced",
        "reduce_business_risk"
    ]

    if negotiation_objective not in valid_objectives:

        negotiation_objective = (
            "protect_my_side"
        )

    # --------------------------------------------------------
    # IMPORTANT:
    # sqlite3.Row must use [] access.
    # --------------------------------------------------------

    clauses = json.loads(
        contract_row["clauses_json"]
    )

    summary_json = (
        contract_row["summary_json"]
    )

    summary = (
        json.loads(summary_json)
        if summary_json
        else {}
    )

    filename = (
        contract_row["filename"]
        or "Unknown"
    )

    contract_title = (
        filename
        .replace(".pdf", "")
        .replace(".docx", "")
        .replace("_", " ")
        .title()
    )

    # --------------------------------------------------------
    # Find raw candidates
    # --------------------------------------------------------

    raw_candidates = (
        find_negotiation_candidates(
            clauses
        )
    )

    # --------------------------------------------------------
    # GROUP CANDIDATES BY CLAUSE
    #
    # This prevents multiple independent AI rewrites of the
    # same clause.
    # --------------------------------------------------------

    candidates_by_clause = {}

    for candidate in raw_candidates:

        candidates_by_clause.setdefault(
            candidate.clause_id,
            []
        ).append(candidate)

    changes = []

    no_change_candidates = []

    change_counter = 0

    # --------------------------------------------------------
    # One AI proposal per clause
    # --------------------------------------------------------

    for clause_id, candidates in (
        candidates_by_clause.items()
    ):

        target_clause = None

        for clause in clauses:

            if (
                str(
                    clause.get(
                        "clause_id"
                    )
                )
                == clause_id
            ):

                target_clause = clause
                break

        if not target_clause:
            continue

        related_evidence = (
            find_related_clauses(
                target_clause,
                clauses
            )
        )

        try:

            llm_response = (
                generate_draft_proposal(
                    contract_data={
                        "clauses": clauses,
                        "summary": summary
                    },

                    target_clause=
                        target_clause,

                    related_evidence=
                        related_evidence,

                    candidates=
                        candidates,

                    negotiation_objective=
                        negotiation_objective
                )
            )

        except Exception as error:

            no_change_candidates.append(
                NoChangeCandidate(
                    candidate_id=(
                        f"NC-{len(no_change_candidates) + 1:03d}"
                    ),

                    clause_id=
                        clause_id,

                    issue=
                        "; ".join(
                            candidate.issue
                            for candidate in candidates
                        ),

                    reason=
                        f"AI analysis failed: {error}"
                ).to_dict()
            )

            continue

        # ----------------------------------------------------
        # HARD VALIDATION
        # ----------------------------------------------------

        is_valid, validation_errors = (
            validate_proposal(
                llm_response,
                target_clause,
                candidates,
                related_evidence
            )
        )

        # ----------------------------------------------------
        # DETERMINISTIC FALLBACK
        # ----------------------------------------------------
        # If the model declines the change or proposes text that
        # fails hard validation, try one narrow deterministic
        # modification based only on the rule engine's permitted
        # operations. This prevents an otherwise useful negotiation
        # engine from depending entirely on LLM drafting behavior.

        if not is_valid or not llm_response.get("change_recommended"):
            fallback = _build_deterministic_safe_fallback(
                target_clause,
                candidates
            )

            if fallback is not None:
                fallback_valid, fallback_errors = validate_proposal(
                    fallback,
                    target_clause,
                    candidates,
                    related_evidence
                )

                if fallback_valid:
                    llm_response = fallback
                    is_valid = True
                    validation_errors = []
                else:
                    validation_errors = fallback_errors

        if not is_valid:
            no_change_candidates.append(
                NoChangeCandidate(
                    candidate_id=(
                        f"NC-{len(no_change_candidates) + 1:03d}"
                    ),
                    clause_id=clause_id,
                    issue="; ".join(
                        candidate.issue
                        for candidate in candidates
                    ),
                    reason=(
                        "Validation failed: "
                        + "; ".join(validation_errors)
                    )
                ).to_dict()
            )
            continue

        # ----------------------------------------------------
        # NO CHANGE
        # ----------------------------------------------------

        if not llm_response.get("change_recommended"):
            no_change_candidates.append(
                NoChangeCandidate(
                    candidate_id=(
                        f"NC-{len(no_change_candidates) + 1:03d}"
                    ),
                    clause_id=clause_id,
                    issue="; ".join(
                        candidate.issue
                        for candidate in candidates
                    ),
                    reason=llm_response.get(
                        "reason",
                        "No safe change is available within the permitted scope."
                    )
                ).to_dict()
            )
            continue

        # ----------------------------------------------------
        # CREATE ONE CHANGE OBJECT
        # ----------------------------------------------------

        change_counter += 1

        change_id = (
            f"CH-{change_counter:03d}"
        )

        evidence_list = []

        # Target evidence
        for candidate in candidates:

            for evidence_text in (
                candidate.evidence
            ):

                evidence_list.append(
                    {
                        "clause_id":
                            clause_id,

                        "text":
                            evidence_text,

                        "relationship":
                            "target_clause"
                    }
                )

        # Related evidence
        for evidence in related_evidence:

            evidence_list.append(
                {
                    "clause_id":
                        evidence.clause_id,

                    "text":
                        evidence.text,

                    "relationship":
                        "related_clause"
                }
            )

        evidence_list = _dedupe_evidence_items(evidence_list)

        change = ChangeObject(

            change_id=
                change_id,

            clause_id=
                clause_id,

            clause_title=
                target_clause.get(
                    "title",
                    f"Clause {clause_id}"
                ),

            # If several rules contributed, preserve them
            # in the primary field while keeping the actual
            # issue combined.
            rule_id=
                "+".join(
                    candidate.rule_id
                    for candidate in candidates
                ),

            issue=
                "; ".join(
                    candidate.issue
                    for candidate in candidates
                ),

            change_type=
                llm_response.get(
                    "change_type",
                    "modify"
                ),

            negotiation_objective=
                negotiation_objective,

            original_text=
                target_clause.get(
                    "text",
                    ""
                ),

            proposed_text=
                llm_response.get(
                    "proposed_text",
                    ""
                ),

            reason=
                llm_response.get(
                    "reason",
                    ""
                ),

            evidence=
                evidence_list,

            preserved_facts=
                llm_response.get(
                    "preserved_facts",
                    []
                ),

            risk_notes=
                llm_response.get(
                    "risk_notes",
                    []
                ),

            change_recommended=
                True,

            status=
                "proposed",

            validated=
                True
        )

        changes.append(
            change.to_dict()
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    analysis_summary = {

        "clauses_reviewed":
            len(clauses),

        "candidates_found":
            len(raw_candidates),

        "clauses_requiring_review":
            len(candidates_by_clause),

        "changes_recommended":
            len(changes),

        "no_change_candidates":
            len(no_change_candidates)
    }

    contract_info = {

        "id":
            contract_id,

        "title":
            contract_title,

        "clause_count":
            len(clauses)
    }

    return DraftAnalysisResult(

        success=True,

        contract=
            contract_info,

        negotiation_objective=
            negotiation_objective,

        analysis_summary=
            analysis_summary,

        changes=
            changes,

        no_change_candidates=
            no_change_candidates
    )


# ============================================================
# APPLY APPROVED CHANGES
# ============================================================

def apply_approved_changes(
    contract_id: int,
    contract_row,
    approved_change_ids: list[str]
) -> dict:

    """
    Apply approved changes.

    NOTE:
    This currently regenerates proposals. We will replace this
    with persisted Change Objects before the frontend approval
    workflow is built.
    """

    clauses = json.loads(
        contract_row["clauses_json"]
    )

    analysis = analyze_contract_for_draft(
        contract_id,
        contract_row,
        "protect_my_side"
    )

    change_map = {
        change["change_id"]:
            change

        for change in analysis.changes
    }

    applied_changes = []

    revised_clauses_data = [
        dict(clause)
        for clause in clauses
    ]

    for change_id in approved_change_ids:

        if change_id not in change_map:
            continue

        change = change_map[
            change_id
        ]

        for index, clause in enumerate(
            revised_clauses_data
        ):

            if (
                str(
                    clause.get(
                        "clause_id"
                    )
                )
                == change[
                    "clause_id"
                ]
            ):

                revised_clauses_data[
                    index
                ] = dict(clause)

                revised_clauses_data[
                    index
                ]["text"] = (
                    change[
                        "proposed_text"
                    ]
                )

                revised_clauses_data[
                    index
                ]["draft_change_applied"] = (
                    True
                )

                revised_clauses_data[
                    index
                ]["draft_change_id"] = (
                    change_id
                )

                applied_changes.append(
                    change_id
                )

                break

    revised_clauses = [
        clause

        for clause in revised_clauses_data

        if clause.get(
            "draft_change_applied"
        )
    ]

    return {

        "success":
            True,

        "contract": {

            "id":
                contract_id,

            "filename":
                contract_row["filename"]
                or "Unknown",

            "clause_count":
                len(clauses)
        },

        "applied_changes":
            applied_changes,

        "revised_clauses":
            revised_clauses,

        "original_contract_preserved":
            True
    }