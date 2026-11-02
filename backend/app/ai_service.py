# ============================================================
# CLAUSEGUARD - AI SERVICE
# ============================================================

import json
import re
import os
import time
from typing import Any

from dotenv import load_dotenv
from groq import Groq
from groq import APIConnectionError, RateLimitError, APIStatusError, AuthenticationError

load_dotenv()

# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

# Groq Configuration (Primary Provider)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

# Hugging Face (Legacy/Fallback - Optional)
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL")
HF_PROVIDER = os.getenv("HF_PROVIDER", "auto")

# Validate Groq configuration (Primary)
if not GROQ_API_KEY:
    raise RuntimeError("Missing GROQ_API_KEY environment variable.")
if not GROQ_MODEL:
    raise RuntimeError("Missing GROQ_MODEL environment variable.")

# Initialize Groq Client (Primary Provider)
try:
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as exc:
    raise RuntimeError(f"Failed to initialize Groq client: {exc}") from exc

# Optional Hugging Face Fallback (if configured)
hf_client = None
if HF_TOKEN and HF_MODEL:
    try:
        from huggingface_hub import InferenceClient
        hf_client = InferenceClient(provider=HF_PROVIDER, api_key=HF_TOKEN)
    except Exception:
        hf_client = None  # Fallback disabled if not properly configured

import time


# ============================================================
# CLAUSE INSIGHT SCHEMA (for /api/ai/clause-insight)
# ============================================================

INSIGHT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "ClauseInsight",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "meaning": {"type": "string"},
                "why_it_matters": {"type": "string"},
                "what_to_review": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "negotiation_suggestion": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "suggested_rewrite": {"type": "string"}
            },
            "required": [
                "meaning", "why_it_matters", "what_to_review",
                "negotiation_suggestion", "suggested_rewrite"
            ],
            "additionalProperties": False
        }
    }
}


# ============================================================
# CLAUSE INSIGHT SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are ClauseGuard, a contract-analysis assistant.

Analyze exactly ONE contract clause using the supplied EVIDENCE PACKAGE.

The evidence package contains structured information extracted by the
ClauseGuard deterministic pipeline. It includes the clause text, its
classified type, risk assessment, and specific risk signals with reasons.

Your job is to:
1. Explain the clause in plain English using ONLY the supplied evidence.
2. Explain why it may matter based on the evidence.
3. Identify practical review points grounded in the evidence.
4. Suggest practical negotiation improvements based on the evidence.
5. Produce a safer alternative version of the clause.

IMPORTANT OUTPUT RULES:
- Return ONLY one valid JSON object.
- Do NOT use markdown.
- Do NOT use ```json.
- Do NOT write anything before or after the JSON.
- Do NOT include reasoning.
- Do NOT include comments.
- Do NOT invent facts that are not supported by the evidence package.
- Clearly distinguish evidence from interpretation.
- Keep every explanation concise.
- Keep "what_to_review" to 2 to 4 short points.
- Keep "negotiation_suggestion" to 1 to 3 practical suggestions.

SOURCE FIDELITY (STRICT - VIOLATIONS INVALIDATE OUTPUT):
- Use the supplied clause text and evidence package as the ONLY factual source.
- Do NOT invent dates, amounts, parties, roles, obligations, exceptions,
  thresholds, conditions, durations, or events not present in the clause
  or evidence.
- Do NOT claim ClauseGuard detected a risk when the evidence shows
  risk_signals is empty and why_flagged is empty.
- Do NOT present speculative implications as established facts.

INTERPRETATION BOUNDARIES:
- You may explain plausible implications of contract language.
- Clearly distinguish interpretation from facts explicitly stated in
  the clause or evidence.
- Label interpretation as "may" or "could" — never as certainty.

NEGOTIATION SUGGESTIONS:
- Negotiation suggestions are recommendations, not existing contract
  facts.
- They must be based on the actual clause text and evidence.
- Do not suggest changes that assume facts not in evidence.
- Do not reference employee roles, seniority, tenure, or any party
  characteristics unless explicitly stated in the clause.
- Frame suggestions as "Consider..." or "Evaluate..." not as facts.

REWRITE CONSTRAINTS (STRICT - VIOLATIONS INVALIDATE OUTPUT):
- Rewrite ONLY the provided clause.
- Preserve the original parties exactly as written.
- Preserve the original subject matter exactly.
- Preserve the original scope exactly.
- Preserve the original duration exactly (e.g., if clause says "18 months",
  rewrite MUST say "18 months" — do NOT change to "12 months" or any other).
- Preserve geographic scope exactly.
- Preserve existing conditions exactly.
- Preserve existing factual structure unless the supplied evidence
  explicitly supports a change.
- Do NOT introduce a new party, role, obligation, exception, condition,
  threshold, duration, or requirement merely because it sounds legally
  sensible.
- Do NOT add "provided that", "subject to", "except", "including but not
  limited to", or similar qualifying language unless in the source.
- Do NOT add cooperation, notice, definition, or procedural requirements
  not in the source clause.
- Do NOT add notice periods, timeframes, or procedural steps not in source.
- Do NOT add "for cause", "material breach", "material obligations" or
  similar legal distinctions not in source.
- If specific risk signals are detected (e.g., "Termination without
  meaningful notice"), you may make ONLY the minimal textual adjustment
  that directly addresses that specific signal using language already
  present in the clause or evidence.
- Prefer minimal, source-faithful edits over creative rewrites.
- If the clause is already reasonably balanced, return it nearly unchanged.

CONCRETE REWRITE EXAMPLES (FOLLOW THESE PATTERNS):

Example 1 - Termination clause with "without notice" and "without cause":
  Source: "Employee's employment may be terminated by either party at any time,
  without prior notice and without cause, subject to applicable law."
  Risk signals: ["Termination without meaningful notice", "Broad termination right"]
  Correct rewrite: "Employee's employment may be terminated by either party at any
  time, without prior notice and without cause, subject to applicable law."
  (Nearly identical — do NOT add notice periods, cause definitions, cure rights,
  writing requirements, or anti-discrimination language.)

Example 2 - Non-compete with 18-month duration and "regardless of reason":
  Source: "Employee shall not compete for 18 months within the United States,
  regardless of the reason for termination."
  Risk signals: ["Time-limited post-termination restriction"]
  Correct rewrite: "Employee shall not compete for 18 months within the United
  States, regardless of the reason for termination."
  (Duration and termination-reason language preserved exactly — do NOT add
  "unless termination is due to cause" or any exception clauses.)

Example 3 - Indemnification with no risk signals:
  Source: "Company shall indemnify Employee for actions in good faith."
  Risk signals: []
  Correct rewrite: "Company shall indemnify Employee for actions in good faith."
  (Identical — no added conditions.)

ABSOLUTE PROHIBITIONS FOR TERMINATION CLAUSES:
- NEVER add "provided that", "except that", "subject to", or similar clauses
- NEVER add "communicated in writing", "written notice", "in writing"
- NEVER add "discriminatory", "retaliatory", "protected characteristics"
- NEVER add "anti-discrimination", "statutory protections", "legal protections"
- If the source says "without prior notice and without cause, subject to applicable law",
  the rewrite MUST end at "applicable law." with no additional text.

FORBIDDEN IN REWRITES (AUTOMATIC FAILURE):
- "long-term or senior employees" (unless in source)
- "reasonable notice" (unless in source)
- "anti-discrimination" (unless in source)
- "good faith" definitions (unless in source)
- "directly competes" instead of "competes" (unless in source)
- New conditions like "provided such actions were not taken in violation
  of the Company's policies" (unless in source)
- Any duration change (18 months → 12 months, etc.)
- Any geographic scope change

NO DETECTED RISK (when risk_signals is empty and why_flagged is empty):
- Do NOT invent a specific detected risk.
- Do NOT claim the clause is problematic merely because you can imagine
  a possible concern.
- You may provide neutral review/clarification points, but MUST
  distinguish them from detected risks.
- Do NOT generate a rewrite that adds obligations not in the source.
- If no risk detected, the rewrite should be nearly identical to the
  source clause.

The JSON must have exactly these fields:

{
  "meaning": "plain-English explanation",
  "why_it_matters": "why this clause could matter",
  "what_to_review": [
    "review point 1",
    "review point 2"
  ],
  "negotiation_suggestion": [
    "suggestion 1",
    "suggestion 2"
  ],
  "suggested_rewrite": "full alternative clause wording"
}
"""


INSIGHT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "ClauseInsight",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "meaning": {"type": "string"},
                "why_it_matters": {"type": "string"},
                "what_to_review": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "negotiation_suggestion": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "suggested_rewrite": {"type": "string"}
            },
            "required": [
                "meaning", "why_it_matters", "what_to_review",
                "negotiation_suggestion", "suggested_rewrite"
            ],
            "additionalProperties": False
        }
    }
}


def _clean_json_text(raw_text: str) -> str:
    """
    Clean common formatting problems before JSON parsing.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # Remove markdown code fences if the model ignored instructions.
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    # Find the first JSON object.
    start = text.find("{")

    if start == -1:
        return text

    text = text[start:]

    # Keep only the outermost JSON object if extra text follows it.
    depth = 0
    in_string = False
    escape = False
    end = None

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                end = index + 1
                break

    if end is not None:
        text = text[:end]

    return text.strip()


def _ensure_valid_shape(data: Any) -> dict:
    """
    Ensure the parsed model output matches the structure expected
    by the frontend.
    """
    if not isinstance(data, dict):
        raise ValueError("AI response is not a JSON object.")

    meaning = data.get("meaning", "")
    why_it_matters = data.get("why_it_matters", "")
    what_to_review = data.get("what_to_review", [])
    negotiation_suggestion = data.get("negotiation_suggestion", [])
    suggested_rewrite = data.get("suggested_rewrite", "")

    if not isinstance(meaning, str):
        meaning = str(meaning)

    if not isinstance(why_it_matters, str):
        why_it_matters = str(why_it_matters)

    if not isinstance(what_to_review, list):
        what_to_review = [str(what_to_review)]

    if not isinstance(negotiation_suggestion, list):
        negotiation_suggestion = [str(negotiation_suggestion)]

    if not isinstance(suggested_rewrite, str):
        suggested_rewrite = str(suggested_rewrite)

    return {
        "meaning": meaning.strip(),
        "why_it_matters": why_it_matters.strip(),
        "what_to_review": [
            str(item).strip()
            for item in what_to_review
            if str(item).strip()
        ],
        "negotiation_suggestion": [
            str(item).strip()
            for item in negotiation_suggestion
            if str(item).strip()
        ],
        "suggested_rewrite": suggested_rewrite.strip(),
    }


# ============================================================
# GROQ INFERENCE HELPER (Primary Provider)
# ============================================================

def _call_groq(
    messages: list,
    response_format: dict = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
    model: str = None
) -> str:
    """
    Call Groq API with proper error handling.
    Returns raw content string (caller handles JSON parsing).
    """
    if model is None:
        model = GROQ_MODEL

    # Determine if we need strict JSON schema or can use simpler JSON mode
    # The qwen/qwen3.8-27b model may not support strict JSON schema format
    use_strict_schema = response_format and response_format.get("type") == "json_schema"
    
    # Prepare request parameters
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    if response_format:
        # For clause insight endpoint with strict schema, try JSON object mode first
        # if the model doesn't support strict JSON schema
        if use_strict_schema:
            # Try with JSON object mode first (more widely supported)
            # The schema validation will be done manually after
            kwargs["response_format"] = {"type": "json_object"}
        else:
            kwargs["response_format"] = response_format
    
    start_time = time.time()
    print(f"[AI] Groq request started - model={model}, temp={temperature}")

    try:
        response = groq_client.chat.completions.create(**{
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **({"response_format": kwargs.get("response_format")} if kwargs.get("response_format") else {})
        })
        elapsed = time.time() - start_time
        print(f"[AI] Groq response received - elapsed={elapsed:.1f}s")

    except RateLimitError as exc:
        elapsed = time.time() - start_time
        print(f"[AI] Groq rate limit (429) after {elapsed:.1f}s: {exc}")
        raise RuntimeError("AI service rate limited. Please try again shortly.") from exc

    except APIStatusError as exc:
        elapsed = time.time() - start_time
        status = getattr(exc, 'status_code', 0)
        print(f"[AI] Groq API error ({status}) after {elapsed:.1f}s: {exc}")
        if status == 401:
            raise RuntimeError("AI authentication failed. Check GROQ_API_KEY.") from exc
        elif status >= 500:
            raise RuntimeError("AI provider temporarily unavailable. Please try again.") from exc
        else:
            raise RuntimeError(f"AI provider error ({status}): {exc}") from exc

    except APIConnectionError as exc:
        elapsed = time.time() - start_time
        print(f"[AI] Groq connection error after {elapsed:.1f}s: {exc}")
        raise RuntimeError("Could not connect to AI provider. Check network.") from exc

    except AuthenticationError as exc:
        elapsed = time.time() - start_time
        print(f"[AI] Groq auth error after {elapsed:.1f}s: {exc}")
        raise RuntimeError("AI authentication failed. Check GROQ_API_KEY.") from exc

    except Exception as exc:
        elapsed = time.time() - start_time
        print(f"[AI] Groq unexpected error after {elapsed:.1f}s: {exc}")
        raise RuntimeError(f"Could not connect to Groq: {exc}") from exc

    # Extract content
    try:
        raw_content = response.choices[0].message.content
    except Exception as exc:
        raise RuntimeError("Failed to extract content from Groq response.") from exc

    if not raw_content:
        raise RuntimeError("Groq returned an empty response.")

    return raw_content


def _clean_json_text(raw_text: str) -> str:
    """
    Clean common formatting problems before JSON parsing.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # Remove markdown code fences if the model ignored instructions.
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    # Find the first JSON object.
    start = text.find("{")

    if start == -1:
        return text

    text = text[start:]

    # Keep only the outermost JSON object if extra text follows it.
    depth = 0
    in_string = False
    escape = False
    end = None

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                end = index + 1
                break

    if end is not None:
        text = text[:end]

    return text.strip()


def _ensure_valid_shape(data: Any) -> dict:
    """
    Ensure the parsed model output matches the structure expected
    by the frontend.
    """
    if not isinstance(data, dict):
        raise ValueError("AI response is not a JSON object.")

    meaning = data.get("meaning", "")
    why_it_matters = data.get("why_it_matters", "")
    what_to_review = data.get("what_to_review", [])
    negotiation_suggestion = data.get("negotiation_suggestion", [])
    suggested_rewrite = data.get("suggested_rewrite", "")

    if not isinstance(meaning, str):
        meaning = str(meaning)

    if not isinstance(why_it_matters, str):
        why_it_matters = str(why_it_matters)

    if not isinstance(what_to_review, list):
        what_to_review = [str(what_to_review)]

    if not isinstance(negotiation_suggestion, list):
        negotiation_suggestion = [str(negotiation_suggestion)]

    if not isinstance(suggested_rewrite, str):
        suggested_rewrite = str(suggested_rewrite)

    return {
        "meaning": meaning.strip(),
        "why_it_matters": why_it_matters.strip(),
        "what_to_review": [
            str(item).strip()
            for item in what_to_review
            if str(item).strip()
        ],
        "negotiation_suggestion": [
            str(item).strip()
            for item in negotiation_suggestion
            if str(item).strip()
        ],
        "suggested_rewrite": suggested_rewrite.strip(),
    }


def generate_clause_insight(clause: dict) -> dict:
    """
    Send one clause to the Groq model and return structured AI insight.
    Uses JSON object mode with manual schema validation.
    """
    clause_text = str(clause.get("text", "")).strip()

    if not clause_text:
        raise ValueError("The selected clause is empty.")

    # Truncate very long clauses to keep prompt small
    MAX_CLAUSE_CHARS = 3000
    if len(clause_text) > MAX_CLAUSE_CHARS:
        clause_text = clause_text[:MAX_CLAUSE_CHARS] + "\n\n[TRUNCATED]"

    # Build evidence package from existing pipeline outputs
    evidence = {
        "clause_text": clause_text,
        "clause_type": clause.get("clause_type", "Other"),
        "page_number": clause.get("page_number"),
        "risk_level": clause.get("risk_level", "Unknown"),
        "risk_signals": clause.get("risk_flags", []),
        "why_flagged": clause.get("risk_reasons", []),
    }

    user_prompt = f"""
Analyze this contract clause using the evidence package below.

EVIDENCE PACKAGE:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

Contract clause:
{clause_text}

Return ONLY a valid JSON object with exactly these fields:
{{
  "meaning": "plain-English explanation",
  "why_it_matters": "why this clause could matter",
  "what_to_review": ["review point 1", "review point 2"],
  "negotiation_suggestion": ["suggestion 1", "suggestion 2"],
  "suggested_rewrite": "full alternative clause wording"
}}

Rules:
- Return ONLY one valid JSON object.
- Do NOT use markdown, code fences, or any extra text.
- Do NOT invent facts not supported by the evidence package.
- Keep "what_to_review" to 2 to 4 short points.
- Keep "negotiation_suggestion" to 1 to 3 practical suggestions.
- Preserve original parties, scope, duration, and geographic scope exactly.
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    import time
    start_time = time.time()
    print(f"[AI] Groq clause insight started - clause_id={clause.get('clause_id')}, type={clause.get('clause_type')}")

    try:
        raw_content = _call_groq(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=800
        )
        elapsed = time.time() - start_time
        print(f"[AI] Groq clause insight completed - elapsed={elapsed:.1f}s")
    except RuntimeError as exc:
        elapsed = time.time() - start_time
        print(f"[AI] Groq clause insight failed after {elapsed:.1f}s: {exc}")
        raise

    if not raw_content:
        raise RuntimeError("Groq returned an empty response.")

    cleaned_content = _clean_json_text(raw_content)

    try:
        parsed = json.loads(cleaned_content)
    except json.JSONDecodeError as exc:
        preview = raw_content[:2000]
        raise RuntimeError(
            f"Groq returned invalid JSON. JSON error: {exc}. Raw response preview: {preview}"
        ) from exc

    # Validate required fields
    required_fields = ["meaning", "why_it_matters", "what_to_review", "negotiation_suggestion", "suggested_rewrite"]
    for field in required_fields:
        if field not in parsed:
            raise RuntimeError(f"Groq response missing required field: {field}")

    # Validate types
    if not isinstance(parsed.get("meaning"), str):
        raise RuntimeError("Field 'meaning' must be a string")
    if not isinstance(parsed.get("why_it_matters"), str):
        raise RuntimeError("Field 'why_it_matters' must be a string")
    if not isinstance(parsed.get("what_to_review"), list):
        raise RuntimeError("Field 'what_to_review' must be a list")
    if not isinstance(parsed.get("negotiation_suggestion"), list):
        raise RuntimeError("Field 'negotiation_suggestion' must be a list")
    if not isinstance(parsed.get("suggested_rewrite"), str):
        raise RuntimeError("Field 'suggested_rewrite' must be a string")

    return _ensure_valid_shape(parsed)


# ============================================================
# CHAT AI SERVICE (for /api/ai/contract-chat)
# ============================================================

CHAT_SYSTEM_PROMPT = """
You are ClauseGuard, a contract assistant that helps users understand
their uploaded contract.

You have access to the user's contract through retrieved clauses.
You also maintain conversation context.

Your job is to:
1. Answer the user's question directly and in plain English.
2. Use contract evidence when the question is about their specific contract.
3. Use general legal knowledge when the question is about general concepts.
4. Combine both when the question asks for both (hybrid).
5. Distinguish clearly between general knowledge and contract-specific facts.
6. Never fabricate contract facts, clauses, dates, amounts, or citations.
7. If the contract doesn't contain the answer, say so honestly.

CORE PRINCIPLES:

PARTY/ROLE FIDELITY (CRITICAL):
- Rights, duties, permissions, restrictions, and obligations MUST remain
  attached to the exact party/role stated in the clause.
- If a clause says "Company may terminate...", do NOT infer that
  "Contractor may terminate..." or "you may terminate...".
- If a clause says "Employee shall...", do NOT reinterpret as
  "Company shall..." or "you shall...".
- Preserve: party identity, role, subject, object, direction of
  obligation, permissions, restrictions.
- When answering about "your" rights, map "you" to the correct party
  based on the contract context — do not assume.

CRITICAL - PARTY MAPPING FOR "YOU"/"I":
The user is asking from their perspective ("I", "my", "me"). You MUST
determine which contract party the user represents based on the
retrieved clauses:
- If clauses reference "Contractor", "Consultant", "Employee", "Vendor" —
  the user is likely that party.
- If clauses reference "Company", "Employer", "Client", "Client" —
  the user is likely the Company.
- NEVER assume the user is the Company unless the contract clearly
  identifies them as such.
- When the user asks "Can I terminate?", map "I" to the correct party
  role and check if THAT PARTY has termination rights.

FACT / INTERPRETATION / GENERAL LEGAL CONTEXT / UNKNOWN (CRITICAL):
Distinguish these FOUR categories in EVERY answer:

A. CONTRACT FACT
Explicitly present in supplied evidence. Quote or paraphrase closely.
Label: "The contract states..." or "The clause provides..."

B. CONTRACT INFERENCE
What can reasonably be inferred from the contract wording.
Label: "This suggests..." or "This may mean..."

C. GENERAL LEGAL CONTEXT
Possible legal consequences that depend on applicable law, not the
contract text. These are NOT contract provisions.
Label: "As a general legal matter..." or "Under applicable law..."

D. UNKNOWN
Something the available contract evidence does NOT establish.
Say explicitly: "The contract does not specify..." or "I could not find..."

CRITICAL RULES:
- NEVER present C (General Legal Context) as if it were A (Contract Fact).
- NEVER silently jump from A to an unsupported conclusion.
- If the contract gives Company a right, do NOT infer the user has that right.
- If the contract is silent on a topic, say so — do not infer.

CROSS-CLAUSE SYNTHESIS:
When multiple clauses are relevant (e.g., Termination + Intellectual Property):
- Synthesize, don't just list.
- Explain how the clauses relate: "The Termination clause says X.
  The Intellectual Property clause says Y. Together, this means Z."
- Every claim must be tied to a specific cited clause.
- Do not cite a clause that doesn't support the statement.

GENERAL vs CONTRACT KNOWLEDGE:
- "What does indemnification mean?" → General knowledge only. No fake
  contract citation. Optionally add: "In your contract, the relevant
  clause..." if one exists.
- "What does indemnification mean in my contract?" → Hybrid.
  Structure as:
  GENERAL MEANING: ...
  IN YOUR CONTRACT: ... (with cited evidence)
  Make the distinction visually clear.

MISSING INFORMATION:
If the contract does not establish an answer:
- Do not invent.
- Do not infer unsupported rights.
- Explicitly state what was and was not found.
- Example: "I couldn't find a severance provision. The termination
  clause only mentions payment for work completed up to termination."
  (Not: "There is no severance.")

CONVERSATION CONTEXT:
- Use recent history for follow-ups.
- If previous question was about Company's termination right, and user
  asks "How much notice do I need?", do NOT transfer Company's
  "without notice" to the user. Retrieve the correct clause or state
  it's not found.

OUT-OF-SCOPE (MANDATORY):
If the user asks something unrelated to contracts or legal concepts
(e.g., "Recommend a sci-fi book," "What is the capital of France,"
"How do I write a Python script?"), you MUST:
1. Do NOT answer the unrelated question.
2. Do NOT provide recommendations, explanations, or partial answers.
3. Return ONLY a brief scope boundary:

"I'm focused on your contract and legal concepts related to it. Ask me about a clause, obligation, risk, or legal term in your contract."

ALLOWED TOPICS (answer normally):
1. Questions about the uploaded contract (clauses, obligations, rights, risks).
2. General legal concepts that help the user understand contracts (e.g., "What is indemnification?").
3. Hybrid questions connecting a legal concept to the uploaded contract (e.g., "What does indemnification mean in my contract?").
4. Follow-up questions based on the current contract conversation.

REJECTED TOPICS (return scope boundary only):
- General recommendations (books, movies, products, services)
- Coding / programming questions
- Entertainment / trivia / geography / general knowledge
- Unrelated personal advice
- Arbitrary ChatGPT-style requests

For legal questions not specific to the uploaded contract:
- General legal knowledge may be used but must be clearly distinguished from contract facts.

ANSWER STYLE:
- Direct answer first, plain English, concise.
- Explain legal concepts naturally, use examples/analogies when helpful.
- Do not sound like a legal textbook.
- Friendly tone but evidence-faithful — friendliness does not
  increase certainty.

OUTPUT FORMAT:
Return a JSON object with exactly these fields:

{
  "answer": "your natural language response to the user",
  "answer_type": "general | contract | hybrid",
  "grounded": true/false,
  "sources": [
    {
      "clause_id": "...",
      "clause_type": "...",
      "page_number": 1,
      "evidence": "exact supporting text from clause"
    }
  ],
  "follow_up_suggestions": [
    "suggested follow-up question 1",
    "suggested follow-up question 2"
  ]
}

Rules:
- answer: conversational, plain English, direct answer first
- answer_type: must be one of the three values
- grounded: true only if contract evidence was used
- sources: only include when grounded=true, max 5 sources
- follow_up_suggestions: 1-3 relevant suggestions, empty if not applicable
"""


CHAT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "ContractChatResponse",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "answer_type": {
                    "type": "string",
                    "enum": ["general", "contract", "hybrid"]
                },
                "grounded": {"type": "boolean"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "clause_id": {"type": "string"},
                            "clause_type": {"type": "string"},
                            "page_number": {"type": ["integer", "null"]},
                            "evidence": {"type": "string"}
                        },
                        "required": ["clause_id", "clause_type", "evidence"],
                        "additionalProperties": False
                    }
                },
                "follow_up_suggestions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": [
                "answer", "answer_type", "grounded", "follow_up_suggestions"
            ],
            "additionalProperties": False
        }
    }
}


def _extract_key_terms(text: str) -> list:
    """
    Extract meaningful terms from a question for clause retrieval.
    Simple keyword extraction - no embeddings needed.
    """
    import re
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off',
        'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
        'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most',
        'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
        'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now',
        'what', 'does', 'do', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'having', 'my', 'your', 'his', 'her', 'its',
        'our', 'their', 'this', 'that', 'these', 'those', 'am', 'i', 'me',
        'you', 'he', 'she', 'it', 'we', 'they', 'them', 'his', 'hers',
        'ours', 'theirs', 'mine', 'yours'
    }
    
    # Extract words, keep legal terms
    words = re.findall(r'\b[a-zA-Z][a-zA-Z\-]+\b', text.lower())
    key_terms = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Also extract phrases that might be legal concepts
    legal_phrases = [
        'indemnification', 'non-compete', 'non compete', 'termination',
        'liability', 'confidentiality', 'intellectual property', 'payment',
        'auto renewal', 'auto-renewal', 'dispute resolution', 'arbitration',
        'governing law', 'assignment', 'warranty', 'force majeure',
        'severance', 'notice period', 'cause', 'material breach',
        'restrictive covenant', 'non solicitation', 'non-solicitation'
    ]
    
    for phrase in legal_phrases:
        if phrase in text.lower():
            key_terms.append(phrase)
    
    return list(set(key_terms))


# Mapping from common terms to clause types for better retrieval
TERM_TO_CLAUSE_TYPE = {
    'non-compete': 'restrictive covenant',
    'non compete': 'restrictive covenant',
    'noncompetition': 'restrictive covenant',
    'non-solicitation': 'restrictive covenant',
    'non solicitation': 'restrictive covenant',
    'restrictive covenant': 'restrictive covenant',
    'indemnif': 'indemnification',
    'termination': 'termination',
    'liability': 'limitation of liability',
    'confidential': 'confidentiality',
    'intellectual property': 'intellectual property',
    'payment': 'payment',
    'auto renew': 'auto-renewal',
    'auto-renewal': 'auto-renewal',
    'dispute': 'dispute resolution',
    'arbitration': 'dispute resolution',
    'governing law': 'governing law',
    'assignment': 'assignment',
    'warranty': 'warranties',
    'force majeure': 'force majeure',
    'severance': 'termination',
    'notice period': 'termination',
    'cause': 'termination',
    'material breach': 'termination',
    'work': 'intellectual property',
    'work product': 'intellectual property',
    'deliverable': 'intellectual property',
    'ownership': 'intellectual property',
    'assign': 'intellectual property',
}


# Clause relationship mapping for cross-clause retrieval
CLAUSE_RELATIONSHIPS = {
    'termination': ['intellectual property', 'payment', 'confidentiality', 'indemnification'],
    'intellectual property': ['termination', 'confidentiality', 'payment'],
    'payment': ['termination', 'intellectual property', 'indemnification'],
    'indemnification': ['termination', 'limitation of liability', 'payment'],
    'confidentiality': ['termination', 'intellectual property', 'non-compete'],
    'restrictive covenant': ['termination', 'confidentiality', 'payment'],
    'limitation of liability': ['indemnification', 'termination'],
    'non-compete': ['termination', 'confidentiality'],
}


def _retrieve_relevant_clauses(clauses: list, question: str, max_clauses: int = 5) -> list:
    """
    Retrieve relevant clauses based on keyword matching and clause relationships.
    Returns top matching clauses with relevance scores.
    """
    key_terms = _extract_key_terms(question)
    
    if not key_terms:
        return []
    
    # Detect if this is a general concept question (e.g., "What does X mean?")
    is_general_concept = _is_general_concept_question(question)
    
    scored_clauses = []
    question_lower = question.lower()
    
    # Detect if question spans multiple conceptual areas (cross-clause)
    cross_clause_topics = _detect_cross_clause_topics(key_terms, question_lower)
    
    for clause in clauses:
        clause_text = clause.get("text", "").lower()
        clause_type = clause.get("clause_type", "").lower()
        
        score = 0
        
        # Score based on key term matches in clause text
        for term in key_terms:
            if term in clause_text:
                score += 2
            if term in clause_type:
                score += 3
        
        # Boost for exact clause type matches
        if clause_type in question_lower:
            score += 5
        
        # Boost for term-to-clause-type mapping matches
        for term in key_terms:
            mapped_type = TERM_TO_CLAUSE_TYPE.get(term)
            if mapped_type and mapped_type in clause_type:
                score += 4
        
        # Check risk flags for relevance
        risk_flags = clause.get("risk_flags", [])
        for flag in risk_flags:
            flag_lower = flag.lower()
            for term in key_terms:
                if term in flag_lower:
                    score += 1
        
        # Cross-clause boost: only for non-general questions that span multiple topics
        if cross_clause_topics and not is_general_concept:
            for topic in cross_clause_topics:
                related_types = CLAUSE_RELATIONSHIPS.get(topic, [])
                if clause_type in related_types:
                    score += 3
        
        # Entity/role awareness: boost clauses mentioning relevant parties
        # (e.g., if question asks about "my work", boost IP clauses)
        if _question_involves_entity(question_lower, clause_text):
            score += 2
        
        if score > 0:
            scored_clauses.append((score, clause))
    
    # Sort by score descending
    scored_clauses.sort(key=lambda x: x[0], reverse=True)
    
    # For general concept questions, only return the top most relevant clause
    # (highest scoring clause of the matching type)
    if is_general_concept and scored_clauses:
        top_score = scored_clauses[0][0]
        # Return only clauses with the top score (or very close)
        filtered = [c for s, c in scored_clauses if s >= top_score - 1]
        return filtered[:max_clauses]
    
    # Return top clauses
    return [clause for score, clause in scored_clauses[:max_clauses]]


def _is_general_concept_question(question: str) -> bool:
    """
    Detect if the question is asking for a general legal concept definition.
    """
    question_lower = question.lower().strip()
    
    # Patterns for general concept questions
    general_patterns = [
        r"^what does\s+\w+\s+mean",
        r"^what is\s+\w+",
        r"^define\s+\w+",
        r"^explain\s+\w+",
        r"^what does\s+\w+\s+refer to",
    ]
    
    import re
    for pattern in general_patterns:
        if re.search(pattern, question_lower):
            return True
    
    return False


def _detect_cross_clause_topics(key_terms: list, question_lower: str) -> list:
    """
    Detect if the question spans multiple conceptual clause areas.
    Returns list of primary clause types the question touches.
    """
    topics = []
    
    # Termination-related
    if any(t in key_terms for t in ['terminat', 'termination', 'end', 'cancel', 'expire']):
        topics.append('termination')
    
    # IP/Work-related
    if any(t in key_terms for t in ['work', 'intellectual property', 'ownership', 'assign', 'deliverable', 'work product', 'my work', 'created']):
        topics.append('intellectual property')
    
    # Payment-related
    if any(t in key_terms for t in ['pay', 'payment', 'salary', 'compensation', 'fee', 'invoice', 'severance', 'owed']):
        topics.append('payment')
    
    # Indemnification
    if any(t in key_terms for t in ['indemnif', 'indemnification', 'hold harmless', 'liable', 'liability']):
        topics.append('indemnification')
    
    # Confidentiality
    if any(t in key_terms for t in ['confidential', 'secret', 'proprietary', 'disclose', 'nda']):
        topics.append('confidentiality')
    
    # Restrictive covenant / non-compete
    if any(t in key_terms for t in ['non-compete', 'non compete', 'restrictive covenant', 'compete', 'solicit', 'after i leave', 'post-employment']):
        topics.append('restrictive covenant')
    
    # Limitation of liability
    if any(t in key_terms for t in ['limitation of liability', 'limited liability', 'cap on liability']):
        topics.append('limitation of liability')
    
    # Notice
    if any(t in key_terms for t in ['notice', 'notify', 'inform']):
        if 'termination' not in topics:
            topics.append('termination')
    
    return list(set(topics))


def _question_involves_entity(question_lower: str, clause_text: str) -> bool:
    """
    Check if the question asks about a specific entity/role that appears in the clause.
    """
    # Check for first-person references in question
    first_person = any(p in question_lower for p in [' my ', 'i ', 'me ', 'myself ', 'our ', 'we '])
    
    if not first_person:
        return False
    
    # Check if clause mentions parties that could be the user
    user_roles = ['employee', 'contractor', 'consultant', 'party', 'you', 'your']
    company_roles = ['company', 'employer', 'client', 'organization', 'firm']
    
    clause_lower = clause_text.lower()
    
    # If question uses first person and clause mentions relevant roles
    if any(role in clause_lower for role in user_roles + company_roles):
        return True
    
    return False


def generate_contract_chat(
    contract_data: dict,
    user_question: str,
    conversation_history: list
) -> dict:
    """
    Generate a chat response for Ask Your Contract feature.
    
    Args:
        contract_data: The full contract analysis result with clauses
        user_question: The user's current question
        conversation_history: List of recent messages (role, content)
    
    Returns:
        Structured response with answer, answer_type, grounded, sources, follow_up_suggestions
    """
    clauses = contract_data.get("clauses", [])
    
    # Retrieve relevant clauses
    relevant_clauses = _retrieve_relevant_clauses(clauses, user_question, max_clauses=5)
    
    # Determine if question is contract-related
    contract_keywords = [
        'my contract', 'this contract', 'the contract', 'in the contract',
        'my agreement', 'this agreement', 'the agreement', 'in the agreement',
        'clause', 'section', 'provision', 'term', 'what does', 'how does',
        'can i', 'what happens', 'what if', 'notice', 'terminate', 'termination',
        'indemnif', 'liability', 'non-compete', 'non compete', 'confidential',
        'intellectual property', 'payment', 'auto renew', 'dispute',
        'arbitration', 'governing law', 'assignment', 'warranty',
        'force majeure', 'severance', 'severability', 'restrictive covenant'
    ]
    
    question_lower = user_question.lower()
    is_contract_question = any(kw in question_lower for kw in contract_keywords)
    
    # Also check if follow-up to previous contract discussion
    if not is_contract_question and conversation_history:
        for msg in conversation_history[-3:]:
            if msg.get("grounded") or msg.get("answer_type") in ["contract", "hybrid"]:
                is_contract_question = True
                break
    
    # Build evidence package from relevant clauses
    evidence_package = []
    for clause in relevant_clauses:
        evidence_package.append({
            "clause_id": clause.get("clause_id"),
            "clause_type": clause.get("clause_type"),
            "page_number": clause.get("page_number"),
            "text": clause.get("text"),
            "risk_flags": clause.get("risk_flags", []),
            "risk_reasons": clause.get("risk_reasons", [])
        })
    
    # Build conversation context
    context_messages = []
    for msg in conversation_history[-6:]:  # Last 6 messages (3 turns)
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ["user", "assistant"] and content:
            context_messages.append({"role": role, "content": content})
    
    # Detect cross-clause topics for prompt guidance
    cross_clause_topics = _detect_cross_clause_topics(_extract_key_terms(user_question), user_question.lower())
    
    # Build user prompt
    if relevant_clauses:
        evidence_text = json.dumps(evidence_package, ensure_ascii=False, indent=2)
        
        # Add guidance for multi-clause synthesis when relevant
        synthesis_guidance = ""
        if len(relevant_clauses) > 1 and cross_clause_topics:
            synthesis_guidance = f"""
IMPORTANT: This question spans multiple clause areas: {', '.join(cross_clause_topics)}.
The retrieved clauses cover different aspects. You MUST:
1. Synthesize the relationship between the clauses.
2. Explain how they work together (e.g., "The Termination clause says X. The Intellectual Property clause says Y. Together, this means Z.").
3. Cite each clause specifically for the claims it supports.
4. Do NOT dump separate summaries — synthesize.
"""
        else:
            synthesis_guidance = ""
        
        evidence_text = json.dumps(evidence_package, ensure_ascii=False, indent=2)
        evidence_section = f"""
RETRIEVED CONTRACT EVIDENCE:
{evidence_text}

The above clauses are the most relevant to the user's question based on
keyword matching. Use ONLY these clauses for contract-specific facts.
{synthesis_guidance}
"""
    else:
        evidence_section = """
RETRIEVED CONTRACT EVIDENCE:
[No relevant clauses found for this question]

No contract clauses were retrieved that match the user's question.
If the question is contract-specific, you must acknowledge that the
information is not found in the contract.
"""
    
    history_text = ""
    if context_messages:
        history_text = "\nCONVERSATION HISTORY:\n"
        for msg in context_messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role_label}: {msg['content']}\n"
    
    user_prompt = f"""
{evidence_section}

{history_text}

CURRENT QUESTION:
{user_question}

Answer the user's question following the system prompt instructions.
Return ONLY the required JSON object.
"""
    
    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    import time
    start_time = time.time()
    print(f"[CHAT] Groq request started - question_len={len(user_question)}, relevant_clauses={len(relevant_clauses)}")
    
    try:
        raw_content = _call_groq(
            messages=[
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format=CHAT_SCHEMA,
            temperature=0.1,
            max_tokens=1000
        )
        elapsed = time.time() - start_time
        print(f"[CHAT] Groq response received - elapsed={elapsed:.1f}s")
    except RuntimeError as exc:
        elapsed = time.time() - start_time
        print(f"[CHAT] Groq request failed after {elapsed:.1f}s: {exc}")
        raise
    
    if not raw_content:
        raise RuntimeError("Groq returned an empty response.")
    
    cleaned_content = _clean_json_text(raw_content)
    
    try:
        parsed = json.loads(cleaned_content)
    except json.JSONDecodeError as exc:
        preview = raw_content[:2000]
        raise RuntimeError(
            f"Groq returned invalid structured JSON. JSON error: {exc}. Raw response preview: {preview}"
        ) from exc
    
    # Validate and ensure shape
    answer = parsed.get("answer", "").strip()
    answer_type = parsed.get("answer_type", "general")
    grounded = parsed.get("grounded", False)
    sources = parsed.get("sources", [])
    follow_up_suggestions = parsed.get("follow_up_suggestions", [])
    
    # Handle missing sources field (model may omit it)
    if not isinstance(sources, list):
        sources = []
    
    # Validate answer_type
    if answer_type not in ["general", "contract", "hybrid"]:
        answer_type = "general"
    
    # If no relevant clauses but marked as contract/hybrid, downgrade
    if not relevant_clauses and answer_type in ["contract", "hybrid"]:
        answer_type = "general"
        grounded = False
        sources = []
    
    # Ensure sources have correct structure
    validated_sources = []
    for src in sources:
        if isinstance(src, dict):
            validated_sources.append({
                "clause_id": str(src.get("clause_id", "")),
                "clause_type": str(src.get("clause_type", "")),
                "page_number": src.get("page_number"),
                "evidence": str(src.get("evidence", ""))
            })
    
    # Limit follow-ups
    if not isinstance(follow_up_suggestions, list):
        follow_up_suggestions = []
    follow_up_suggestions = [str(s).strip() for s in follow_up_suggestions if str(s).strip()][:3]
    
    return {
        "answer": answer,
        "answer_type": answer_type,
        "grounded": grounded and len(validated_sources) > 0,
        "sources": validated_sources,
        "follow_up_suggestions": follow_up_suggestions
    }