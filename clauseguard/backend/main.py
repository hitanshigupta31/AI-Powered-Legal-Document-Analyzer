# ============================================================
# MAIN FASTAPI APPLICATION
# ============================================================
from app.ai_service import generate_clause_insight, generate_contract_chat
from app.draft_service import analyze_contract_for_draft
from app.approval_service import (
    initialize_approval_schema,
    persist_change_proposal,
    get_draft_changes,
    set_change_status,
    apply_approved_changes_exact,
    get_contract_revisions,
    get_contract_revision,
    get_change_ledger,
)
from app.improvement_service import analyze_contract_for_improvements
from app.improvement_planner_service import build_improvement_plan
from app.custom_draft_service import draft_founder_requested_change
from app.watchtower_service import initialize_watchtower_schema
from app.watchtower_extractor import extract_monitorable_items
from app.watchtower_runtime_service import (
    activate_watchtower,
    get_watchtower,
    record_watch_event,
    get_watch_events,
    get_watch_alerts,
    get_watch_evaluations,
    close_watch_alert,
    record_watch_decision,
    get_watch_decisions,
    get_latest_watch_decisions,
)
from pathlib import Path
import re
import shutil
import tempfile
import json
from typing import Optional, Any

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)

from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from app.auth import (
    SESSION_COOKIE_NAME,
    create_login_session,
    get_current_user_from_cookie,
    hash_password,
    logout_session,
    require_user,
    verify_password,
)

from app.database import (
    create_user,
    delete_expired_sessions,
    get_user_by_email,
    initialize_database,
    save_contract,
    get_contract,
    get_user_contracts,
    save_chat_message,
    get_chat_history,
    delete_chat_history,
)

from app.document_parser import parse_document
from app.pipeline import analyze_document


# ============================================================
# PATHS
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

FRONTEND_DIR = PROJECT_DIR / "frontend"

TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"


# ============================================================
# CHECK DIRECTORIES
# ============================================================

if not TEMPLATES_DIR.exists():

    raise RuntimeError(
        f"Templates directory not found: {TEMPLATES_DIR}"
    )


if not STATIC_DIR.exists():

    raise RuntimeError(
        f"Static directory not found: {STATIC_DIR}"
    )


# ============================================================
# FRONTEND FILES
# ============================================================

LOGIN_PAGE = TEMPLATES_DIR / "login.html"
REGISTER_PAGE = TEMPLATES_DIR / "register.html"
INDEX_PAGE = TEMPLATES_DIR / "index.html"


if not LOGIN_PAGE.exists():

    raise RuntimeError(
        f"Login page not found: {LOGIN_PAGE}"
    )


if not REGISTER_PAGE.exists():

    raise RuntimeError(
        f"Register page not found: {REGISTER_PAGE}"
    )


if not INDEX_PAGE.exists():

    raise RuntimeError(
        f"Index page not found: {INDEX_PAGE}"
    )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="ClauseGuard",
    description=(
        "Contract intelligence and clause-level risk analysis."
    ),
    version="1.0.0"
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(STATIC_DIR)
    ),
    name="static"
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup_event():

    initialize_database()

    initialize_approval_schema()

    initialize_watchtower_schema()

    delete_expired_sessions()


# ============================================================
# REQUEST MODELS
# ============================================================

class ContractRequest(BaseModel):

    text: str


class RegisterRequest(BaseModel):

    name: str
    email: str
    password: str


class LoginRequest(BaseModel):

    email: str
    password: str


class ContractChatRequest(BaseModel):
    contract_id: int
    question: str


class ContractChatResponse(BaseModel):
    answer: str
    answer_type: str
    grounded: bool
    sources: list
    follow_up_suggestions: list


class DraftAnalyzeRequest(BaseModel):
    contract_id: int
    negotiation_objective: str = "protect_my_side"


class ImprovementPlanRequest(BaseModel):

    area_key: str
    strategy_ids: Optional[list[str]] = None
    user_instruction: str = ""


class FounderDraftRequest(BaseModel):

    area_key: str
    strategy_ids: Optional[list[str]] = None
    user_instruction: str = ""


class DraftApplyRequest(BaseModel):
    contract_id: int
    approved_changes: list[str]


class WatchtowerActivationRequest(BaseModel):
    watch_items: list[dict] = []


class WatchtowerEventRequest(BaseModel):
    event_type: str
    event_date: Optional[str] = None
    description: str
    observed_value: Optional[float] = None
    observed_unit: Optional[str] = None
    evidence: Optional[dict] = None


class WatchtowerDecisionRequest(BaseModel):
    watch_item_id: int
    decision: str


# ============================================================
# EMAIL HELPERS
# ============================================================

def normalize_email(
    email: str
) -> str:

    return email.strip().lower()


def validate_email(
    email: str
) -> bool:

    pattern = (
        r"^[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9.-]+\."
        r"[A-Za-z]{2,}$"
    )

    return bool(
        re.match(
            pattern,
            email
        )
    )


# ============================================================
# DOCUMENT TEXT NORMALIZATION
# ============================================================

def normalize_extracted_text(
    parsed_document: Any
) -> str:
    """
    Convert the output of parse_document() into one
    continuous text string that can be passed to the
    clause segmentation pipeline.

    Current parser behavior:

        PDF:
            [
                {
                    "page_number": 1,
                    "text": "..."
                },
                {
                    "page_number": 2,
                    "text": "..."
                }
            ]

        DOCX:
            [
                {
                    "page_number": None,
                    "text": "..."
                }
            ]

    The analyzer requires a plain string.
    """

    # --------------------------------------------------------
    # CASE 1:
    # Parser already returned a string.
    # --------------------------------------------------------

    if isinstance(
        parsed_document,
        str
    ):

        return parsed_document.strip()


    # --------------------------------------------------------
    # CASE 2:
    # Parser returned a list.
    # --------------------------------------------------------

    if isinstance(
        parsed_document,
        list
    ):

        page_texts = []


        for item in parsed_document:

            # ------------------------------------------------
            # Expected structure:
            #
            # {
            #     "page_number": ...,
            #     "text": "..."
            # }
            # ------------------------------------------------

            if isinstance(
                item,
                dict
            ):

                page_text = item.get(
                    "text",
                    ""
                )


                if page_text is None:
                    continue


                page_text = str(
                    page_text
                ).strip()


                if page_text:

                    page_texts.append(
                        page_text
                    )


            # ------------------------------------------------
            # Also support a plain string item just in case
            # the parser is changed later.
            # ------------------------------------------------

            elif isinstance(
                item,
                str
            ):

                item_text = item.strip()


                if item_text:

                    page_texts.append(
                        item_text
                    )


        # ----------------------------------------------------
        # Join pages with real newlines.
        #
        # This is important because the clause segmenter
        # detects numbered headings at the beginning of lines.
        # ----------------------------------------------------

        return "\n\n".join(
            page_texts
        ).strip()


    # --------------------------------------------------------
    # CASE 3:
    # None / unexpected type.
    # --------------------------------------------------------

    if parsed_document is None:

        return ""


    return str(
        parsed_document
    ).strip()


# ============================================================
# BUILD ANALYSIS SUMMARY
# ============================================================

def build_summary(
    clauses
):

    high = sum(
        1
        for clause in clauses
        if str(
            clause.get(
                "risk_level",
                ""
            )
        ).upper() == "HIGH"
    )


    medium = sum(
        1
        for clause in clauses
        if str(
            clause.get(
                "risk_level",
                ""
            )
        ).upper() == "MEDIUM"
    )


    low = sum(
        1
        for clause in clauses
        if str(
            clause.get(
                "risk_level",
                ""
            )
        ).upper() == "LOW"
    )


    attention = (
        high +
        medium
    )


    scores = [
        float(
            clause.get(
                "risk_score",
                0
            )
        )

        for clause in clauses

        if isinstance(
            clause.get(
                "risk_score"
            ),
            (int, float)
        )
    ]


    if scores:

        overall_score = round(
            sum(scores) / len(scores)
        )

    else:

        overall_score = 0


    priority_findings = sorted(
        clauses,

        key=lambda clause:
            float(
                clause.get(
                    "risk_score",
                    0
                )
            ),

        reverse=True
    )[:5]


    return {
        "overall_score":
            overall_score,

        "high_risk_count":
            high,

        "medium_risk_count":
            medium,

        "low_risk_count":
            low,

        "attention_count":
            attention,

        "priority_findings":
            priority_findings
    }


# ============================================================
# ROOT / DASHBOARD
# ============================================================

@app.get("/app")
@app.get("/")
def root(
    session_cookie: Optional[str] = Cookie(
        default=None,
        alias=SESSION_COOKIE_NAME
    )
):

    user = get_current_user_from_cookie(
        session_cookie
    )


    if user is None:

        return RedirectResponse(
            url="/login",
            status_code=303
        )


    return FileResponse(
        INDEX_PAGE
    )


# ============================================================
# LOGIN PAGE
# ============================================================

@app.get("/login")
def login_page():

    return FileResponse(
        LOGIN_PAGE
    )


# ============================================================
# REGISTER PAGE
# ============================================================

@app.get("/register")
def register_page():

    return FileResponse(
        REGISTER_PAGE
    )


# ============================================================
# REGISTER API
# ============================================================

@app.post("/api/auth/register")
def register_user(
    payload: RegisterRequest
):

    name = payload.name.strip()

    email = normalize_email(
        payload.email
    )

    password = payload.password


    # --------------------------------------------------------
    # NAME VALIDATION
    # --------------------------------------------------------

    if len(name) < 2:

        raise HTTPException(
            status_code=400,
            detail="Please enter your name."
        )


    if len(name) > 100:

        raise HTTPException(
            status_code=400,
            detail="Name is too long."
        )


    # --------------------------------------------------------
    # EMAIL VALIDATION
    # --------------------------------------------------------

    if not validate_email(
        email
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Please enter a valid email address."
            )
        )


    # --------------------------------------------------------
    # PASSWORD VALIDATION
    # --------------------------------------------------------

    if len(password) < 8:

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least "
                "8 characters long."
            )
        )


    # --------------------------------------------------------
    # CHECK EXISTING ACCOUNT
    # --------------------------------------------------------

    existing_user = get_user_by_email(
        email
    )


    if existing_user is not None:

        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this email "
                "already exists."
            )
        )


    # --------------------------------------------------------
    # HASH PASSWORD
    # --------------------------------------------------------

    password_hash = hash_password(
        password
    )


    # --------------------------------------------------------
    # CREATE USER
    # --------------------------------------------------------

    try:

        user_id = create_user(
            name=name,
            email=email,
            password_hash=password_hash
        )

    except Exception as error:

        print(
            "REGISTER ERROR:",
            error
        )

        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this email "
                "already exists."
            )
        )


    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Registration does NOT create a login session.
    # User must explicitly sign in.
    # --------------------------------------------------------

    return {
        "message":
            "Account created successfully.",

        "user": {
            "id":
                user_id,

            "name":
                name,

            "email":
                email
        }
    }


# ============================================================
# LOGIN API
# ============================================================

@app.post("/api/auth/login")
def login_user(
    payload: LoginRequest
):

    email = normalize_email(
        payload.email
    )

    password = payload.password


    # --------------------------------------------------------
    # FIND USER
    # --------------------------------------------------------

    user = get_user_by_email(
        email
    )


    if user is None:

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid email or password."
            )
        )


    # --------------------------------------------------------
    # VERIFY PASSWORD
    # --------------------------------------------------------

    if not verify_password(
        password,
        user["password_hash"]
    ):

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid email or password."
            )
        )


    # --------------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------------

    session_token = create_login_session(
        int(
            user["id"]
        )
    )


    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    response = JSONResponse(
        {
            "message":
                "Login successful.",

            "user": {
                "id":
                    int(
                        user["id"]
                    ),

                "name":
                    user["name"],

                "email":
                    user["email"]
            }
        }
    )


    response.set_cookie(
        key=SESSION_COOKIE_NAME,

        value=session_token,

        httponly=True,

        samesite="lax",

        secure=False,

        max_age=60 * 60 * 24 * 7,

        path="/"
    )


    return response


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/api/auth/me")
def current_user(
    user=Depends(
        require_user
    )
):

    return {
        "authenticated":
            True,

        "user": {
            "id":
                int(
                    user["id"]
                ),

            "name":
                user["name"],

            "email":
                user["email"],

            "created_at":
                user["created_at"]
        }
    }


# ============================================================
# LOGOUT API
# ============================================================

@app.post("/api/auth/logout")
def logout(
    session_cookie: Optional[str] = Cookie(
        default=None,
        alias=SESSION_COOKIE_NAME
    )
):

    if session_cookie:

        logout_session(
            session_cookie
        )


    response = JSONResponse(
        {
            "message":
                "Logged out successfully."
        }
    )


    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/"
    )


    return response


# ============================================================
# LOGOUT GET ROUTE
# ============================================================

@app.get("/logout")
def logout_get(
    session_cookie: Optional[str] = Cookie(
        default=None,
        alias=SESSION_COOKIE_NAME
    )
):

    if session_cookie:

        logout_session(
            session_cookie
        )


    response = RedirectResponse(
        url="/login",
        status_code=303
    )


    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/"
    )


    return response
# ============================================================
# AI CLAUSE INSIGHT
# ============================================================

@app.post("/api/ai/clause-insight")
def clause_insight(
    clause: dict,
    user=Depends(require_user)
):

    try:

        insight = generate_clause_insight(
            clause
        )

        return {
            "success": True,
            "insight": insight
        }

    except RuntimeError as error:

        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except Exception as error:

        print(
            "AI ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="AI analysis failed."
        )


# ============================================================
# AI CONTRACT CHAT (Ask Your Contract)
# ============================================================

@app.post("/api/ai/contract-chat")
def contract_chat(
    payload: ContractChatRequest,
    user=Depends(require_user)
):
    """
    Ask Your Contract - conversational assistant for contract questions.
    
    Retrieves relevant clauses from the user's contract and generates
    a grounded response with source citations.
    """
    user_id = int(user["id"])
    contract_id = payload.contract_id
    question = payload.question.strip()
    
    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )
    
    # Verify contract belongs to user
    contract_row = get_contract(contract_id, user_id)
    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )
    
    # Parse contract data
    import json
    try:
        clauses = json.loads(contract_row["clauses_json"])
        summary = json.loads(contract_row["summary_json"]) if contract_row["summary_json"] else {}
    except Exception as exc:
        print(f"[CHAT] Failed to parse contract data: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load contract data."
        )
    
    contract_data = {
        "clauses": clauses,
        "summary": summary
    }
    
    # Get conversation history
    history_rows = get_chat_history(contract_id, user_id, limit=20)
    conversation_history = []
    for row in history_rows:
        conversation_history.append({
            "role": row["role"],
            "content": row["content"],
            "answer_type": row["answer_type"],
            "grounded": bool(row["grounded"])
        })
    
    # Save user message
    save_chat_message(
        contract_id=contract_id,
        user_id=user_id,
        role="user",
        content=question
    )
    
    try:
        # Generate AI response
        response = generate_contract_chat(
            contract_data=contract_data,
            user_question=question,
            conversation_history=conversation_history
        )
        
        # Save assistant message
        save_chat_message(
            contract_id=contract_id,
            user_id=user_id,
            role="assistant",
            content=response["answer"],
            answer_type=response["answer_type"],
            grounded=response["grounded"],
            sources=response["sources"],
            follow_up_suggestions=response["follow_up_suggestions"]
        )
        
        return {
            "success": True,
            "answer": response["answer"],
            "answer_type": response["answer_type"],
            "grounded": response["grounded"],
            "sources": response["sources"],
            "follow_up_suggestions": response["follow_up_suggestions"]
        }
        
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        )
    except Exception as error:
        print(f"[CHAT] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Chat analysis failed."
        )


# ============================================================
# AI DRAFT - CONTRACT NEGOTIATION
# ============================================================

@app.post("/api/ai/draft/analyze")
def draft_analyze(
    payload: DraftAnalyzeRequest,
    user=Depends(require_user)
):
    """
    Analyze a contract for negotiation opportunities.
    
    Uses rule engine + LLM to identify clauses that may warrant
    negotiated changes based on the specified objective.
    
    Returns structured Change Objects for each recommended change,
    plus candidates where no change was recommended.
    """
    user_id = int(user["id"])
    contract_id = payload.contract_id
    negotiation_objective = payload.negotiation_objective
    
    # Verify contract belongs to user
    contract_row = get_contract(contract_id, user_id)
    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )
    
    try:
        result = analyze_contract_for_draft(
            contract_id=contract_id,
            contract_row=contract_row,
            negotiation_objective=negotiation_objective
        )
        
        return {
            "success": True,
            "contract": result.contract,
            "negotiation_objective": result.negotiation_objective,
            "analysis_summary": result.analysis_summary,
            "changes": result.changes,
            "no_change_candidates": result.no_change_candidates
        }
        
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        )
    except Exception as error:
        print(f"[DRAFT ANALYZE] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Draft analysis failed."
        )


# ============================================================
# CONTRACT IMPROVEMENT ASSESSMENT - FEATURE 3 LAYER 1
# ============================================================

@app.post("/api/contracts/{contract_id}/improvements")
def generate_contract_improvements(
    contract_id: int,
    user=Depends(require_user)
):
    """
    Generate contract-level improvement areas from the
    existing saved contract analysis.

    This endpoint does NOT analyze the contract again.
    It consumes the clause/risk analysis already stored for
    the user's contract and converts it into:

        improvement areas
        why each area deserves review
        improvement strategies

    It does not rewrite or modify contract language.
    """

    user_id = int(user["id"])

    # --------------------------------------------------------
    # Verify contract belongs to the authenticated user.
    # --------------------------------------------------------

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:

        result = analyze_contract_for_improvements(
            contract_id=contract_id,
            contract_row=contract_row
        )

        return result

    except RuntimeError as error:

        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except Exception as error:

        print(
            f"[IMPROVEMENTS] Error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not generate contract improvement assessment."
        )


# ============================================================
# IMPROVEMENT PLAN / FOUNDER INTENT - FEATURE 3 LAYER 2
# ============================================================

@app.post("/api/contracts/{contract_id}/improvement-plan")
def create_improvement_plan(
    contract_id: int,
    payload: ImprovementPlanRequest,
    user=Depends(require_user)
):
    """
    Turn one selected attention area into a structured
    improvement plan.

    Layer 2 sits after the contract-level attention assessment
    and before exact clause drafting.

    It does not rewrite or modify the contract.
    """

    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:
        return build_improvement_plan(
            contract_id=contract_id,
            contract_row=contract_row,
            area_key=payload.area_key,
            strategy_ids=payload.strategy_ids,
            user_instruction=payload.user_instruction,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"[IMPROVEMENT PLAN] Error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not build the improvement plan."
        )


# ============================================================
# FOUNDER-DIRECTED CLAUSE DRAFTING - FEATURE 3 LAYER 3
# ============================================================

@app.post("/api/contracts/{contract_id}/improvement-plan/draft")
def draft_founder_change(
    contract_id: int,
    payload: FounderDraftRequest,
    user=Depends(require_user)
):
    """
    Generate a proposed clause from the founder's improvement request.

    This endpoint does not modify or apply the contract.
    It first resolves Layer 2 intent, then drafts and validates one
    founder-directed clause change.
    """

    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:

        plan_result = build_improvement_plan(
            contract_id=contract_id,
            contract_row=contract_row,
            area_key=payload.area_key,
            strategy_ids=payload.strategy_ids,
            user_instruction=payload.user_instruction,
        )

        result = draft_founder_requested_change(
            contract_id=contract_id,
            plan_result=plan_result,
        )

        change = result.get("change")
        validation = result.get("validation", {})

        if (
            result.get("success")
            and result.get("drafting_status") == "drafted"
            and isinstance(change, dict)
            and validation.get("passed") is True
            and change.get("validated") is True
        ):
            persisted_change = persist_change_proposal(
                contract_id=contract_id,
                user_id=user_id,
                change=change,
            )

            result["change"] = persisted_change

        return result

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except Exception as error:

        print(
            f"[FOUNDER DRAFT] Error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not draft the requested clause."
        )



# ============================================================
# CHANGE APPROVAL / EXACT APPLICATION - FEATURE 3 LAYER 4
# ============================================================

@app.get("/api/contracts/{contract_id}/draft-changes")
def list_contract_draft_changes(
    contract_id: int,
    user=Depends(require_user)
):
    """Return the exact persisted Change Objects for founder review."""
    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    return {
        "success": True,
        "contract_id": contract_id,
        "changes": get_draft_changes(
            contract_id=contract_id,
            user_id=user_id,
        ),
    }


@app.post("/api/contracts/{contract_id}/draft-changes/apply")
def apply_contract_approved_changes(
    contract_id: int,
    payload: DraftApplyRequest,
    user=Depends(require_user)
):
    """Apply exact approved Change Objects and create a new revision."""
    user_id = int(user["id"])

    if payload.contract_id != contract_id:
        raise HTTPException(
            status_code=400,
            detail="Contract ID in path and body must match."
        )

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:
        return apply_approved_changes_exact(
            contract_id=contract_id,
            user_id=user_id,
            approved_change_ids=payload.approved_changes,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"[LAYER 4 APPLY] Error: {error}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to apply approved changes."
        )


@app.post(
    "/api/contracts/{contract_id}/draft-changes/{change_id}/approve"
)
def approve_contract_change(
    contract_id: int,
    change_id: str,
    user=Depends(require_user)
):
    """Approve one exact persisted Change Object."""
    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:
        change = set_change_status(
            contract_id=contract_id,
            user_id=user_id,
            change_id=change_id,
            new_status="approved",
        )

        return {
            "success": True,
            "action": "approved",
            "change": change,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"[LAYER 4 APPROVE] Error: {error}"
        )
        raise HTTPException(
            status_code=500,
            detail="Could not approve the change."
        )


@app.post(
    "/api/contracts/{contract_id}/draft-changes/{change_id}/reject"
)
def reject_contract_change(
    contract_id: int,
    change_id: str,
    user=Depends(require_user)
):
    """Reject one exact persisted Change Object."""
    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:
        change = set_change_status(
            contract_id=contract_id,
            user_id=user_id,
            change_id=change_id,
            new_status="rejected",
        )

        return {
            "success": True,
            "action": "rejected",
            "change": change,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"[LAYER 4 REJECT] Error: {error}"
        )
        raise HTTPException(
            status_code=500,
            detail="Could not reject the change."
        )


@app.get("/api/contracts/{contract_id}/revisions")
def list_contract_revisions(
    contract_id: int,
    user=Depends(require_user)
):
    """List immutable contract revisions produced by Layer 4."""
    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    return {
        "success": True,
        "contract_id": contract_id,
        "revisions": get_contract_revisions(
            contract_id=contract_id,
            user_id=user_id,
        ),
    }


@app.get("/api/contracts/{contract_id}/revisions/{revision_id}")
def get_contract_revision_detail(
    contract_id: int,
    revision_id: int,
    user=Depends(require_user)
):
    """Return one immutable revised contract version."""
    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    revision = get_contract_revision(
        contract_id=contract_id,
        user_id=user_id,
        revision_id=revision_id,
    )

    if revision is None:
        raise HTTPException(
            status_code=404,
            detail="Revision not found."
        )

    return {
        "success": True,
        "revision": revision,
    }


@app.get("/api/contracts/{contract_id}/change-ledger")
def get_contract_change_ledger(
    contract_id: int,
    user=Depends(require_user)
):
    """Return the immutable history of applied clause changes."""
    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    return {
        "success": True,
        "contract_id": contract_id,
        "ledger": get_change_ledger(
            contract_id=contract_id,
            user_id=user_id,
        ),
    }


@app.post("/api/ai/draft/apply")
def draft_apply(
    payload: DraftApplyRequest,
    user=Depends(require_user)
):
    """
    Compatibility endpoint.

    Layer 4 applies exact persisted approved Change Objects.
    It never regenerates an LLM proposal and never modifies the
    original contract row.
    """
    user_id = int(user["id"])
    contract_id = payload.contract_id

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:
        return apply_approved_changes_exact(
            contract_id=contract_id,
            user_id=user_id,
            approved_change_ids=payload.approved_changes,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"[DRAFT APPLY] Error: {error}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to apply approved changes."
        )


# ============================================================
# CONTRACT MANAGEMENT ENDPOINTS
# ============================================================

@app.get("/api/contracts")
def list_contracts(
    limit: int = 50,
    user=Depends(require_user)
):
    """List the authenticated user's saved contract analyses for history and Watchtower."""
    user_id = int(user["id"])
    safe_limit = max(1, min(int(limit), 100))
    contracts = get_user_contracts(user_id, limit=safe_limit)
    history = []

    for row in contracts:
        contract_id = int(row["id"])
        detail = get_contract(contract_id, user_id)
        if detail is None:
            continue

        try:
            clauses = json.loads(detail["clauses_json"] or "[]")
            summary = json.loads(detail["summary_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            clauses = []
            summary = {}

        if not isinstance(clauses, list):
            clauses = []
        if not isinstance(summary, dict):
            summary = {}

        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        numeric_scores = []
        for clause in clauses:
            if not isinstance(clause, dict):
                continue
            level = str(clause.get("risk_level") or "LOW").upper()
            counts[level if level in counts else "LOW"] += 1
            try:
                numeric_scores.append(float(clause.get("risk_score", 0)))
            except (TypeError, ValueError):
                pass

        highest_risk = "HIGH" if counts["HIGH"] else ("MEDIUM" if counts["MEDIUM"] else "LOW")
        overall_score = summary.get("overall_score")
        if overall_score is None:
            overall_score = round(sum(numeric_scores) / len(numeric_scores)) if numeric_scores else 0

        history.append({
            "id": contract_id,
            "filename": detail["filename"] or f"Untitled contract {contract_id}",
            "created_at": detail["created_at"],
            "total_clauses": len(clauses),
            "overall_score": overall_score,
            "high_risk_count": summary.get("high_risk_count", counts["HIGH"]),
            "medium_risk_count": summary.get("medium_risk_count", counts["MEDIUM"]),
            "low_risk_count": summary.get("low_risk_count", counts["LOW"]),
            "attention_count": summary.get("attention_count", counts["HIGH"] + counts["MEDIUM"]),
            "highest_risk": highest_risk,
        })

    return {"contracts": history, "total": len(history)}


# ============================================================
# CONTRACT WATCHTOWER - PREVIEW
# ============================================================

@app.get("/api/contracts/{contract_id}/watchtower/preview")
def preview_watchtower(
    contract_id: int,
    user=Depends(require_user)
):
    """
    Analyze a contract and return the monitorable provisions
    detected by Watchtower.

    Preview-only endpoint: nothing is persisted and no monitoring
    is activated.
    """

    user_id = int(user["id"])

    contract_row = get_contract(
        contract_id,
        user_id
    )

    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    try:
        result = extract_monitorable_items(
            contract_id=contract_id,
            user_id=user_id,
        )

        return {
            "success": True,
            **result,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"[WATCHTOWER PREVIEW] Error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Watchtower extraction failed."
        )


@app.post("/api/contracts/{contract_id}/watchtower/activate")
def activate_contract_watchtower(
    contract_id: int,
    payload: WatchtowerActivationRequest,
    user=Depends(require_user)
):
    """Activate Watchtower for the selected monitorable provisions."""
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    try:
        return activate_watchtower(
            contract_id=contract_id,
            user_id=user_id,
            selected_items=payload.watch_items,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print(f"[WATCHTOWER ACTIVATE] Error: {error}")
        raise HTTPException(status_code=500, detail="Failed to activate Watchtower.")


@app.get("/api/contracts/{contract_id}/watchtower")
def get_contract_watchtower(
    contract_id: int,
    user=Depends(require_user)
):
    """Return Watchtower state and initialize it for already-saved contracts."""
    user_id = int(user["id"])

    # Never expose another user's contract.
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )

    result = get_watchtower(
        contract_id=contract_id,
        user_id=user_id
    )

    # Repair contracts uploaded before automatic Watchtower activation existed.
    if result is None:
        try:
            preview = extract_monitorable_items(
                contract_id=contract_id,
                user_id=user_id
            )
            items = (
                preview.get("items")
                or preview.get("monitorable_items")
                or []
            )

            if not items:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "No monitorable contractual provisions were detected. "
                        "Watchtower cannot be activated for this contract yet."
                    )
                )

            result = activate_watchtower(
                contract_id=contract_id,
                user_id=user_id,
                selected_items=items
            )

        except HTTPException:
            raise
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error)
            )
        except Exception as error:
            print(f"[WATCHTOWER INITIALIZATION] Contract {contract_id}: {error}")
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize Watchtower for this contract."
            )

    return {"success": True, **result}


@app.post("/api/contracts/{contract_id}/watchtower/events")
def create_watchtower_event(
    contract_id: int,
    payload: WatchtowerEventRequest,
    user=Depends(require_user)
):
    """Record one observed event and evaluate it against active watch items."""
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    try:
        return record_watch_event(
            contract_id=contract_id,
            user_id=user_id,
            event_type=payload.event_type,
            event_date=payload.event_date,
            description=payload.description,
            observed_value=payload.observed_value,
            observed_unit=payload.observed_unit,
            evidence=payload.evidence or {},
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print(f"[WATCHTOWER EVENT] Error: {error}")
        raise HTTPException(status_code=500, detail="Failed to record Watchtower event.")



@app.get("/api/contracts/{contract_id}/watchtower/alerts")
def list_watchtower_alerts(
    contract_id: int,
    status: Optional[str] = None,
    user=Depends(require_user),
):
    """Return Watchtower alerts, optionally filtered by status."""
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    if status is not None and status not in {"open", "closed"}:
        raise HTTPException(
            status_code=400,
            detail="Alert status must be 'open' or 'closed'.",
        )

    return {
        "success": True,
        "alerts": get_watch_alerts(
            contract_id=contract_id,
            user_id=user_id,
            status=status,
        ),
    }


@app.get("/api/contracts/{contract_id}/watchtower/evaluations")
def list_watchtower_evaluations(
    contract_id: int,
    user=Depends(require_user),
):
    """Return the persisted Watchtower evaluation/audit history."""
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    return {
        "success": True,
        "evaluations": get_watch_evaluations(
            contract_id=contract_id,
            user_id=user_id,
        ),
    }


@app.post("/api/contracts/{contract_id}/watchtower/decisions")
def create_watchtower_decision(
    contract_id: int,
    payload: WatchtowerDecisionRequest,
    user=Depends(require_user),
):
    """Persist the user's decision for a monitored Watchtower provision."""
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    try:
        return record_watch_decision(
            contract_id=contract_id,
            user_id=user_id,
            watch_item_id=payload.watch_item_id,
            decision=payload.decision,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print(f"[WATCHTOWER DECISION] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Failed to record Watchtower decision.",
        )


@app.get("/api/contracts/{contract_id}/watchtower/decisions")
def list_watchtower_decisions(
    contract_id: int,
    watch_item_id: Optional[int] = None,
    user=Depends(require_user),
):
    """Return Watchtower decision history for the contract."""
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    return {
        "success": True,
        "decisions": get_watch_decisions(
            contract_id=contract_id,
            user_id=user_id,
            watch_item_id=watch_item_id,
        ),
        "current": get_latest_watch_decisions(
            contract_id=contract_id,
            user_id=user_id,
        ),
    }


@app.post("/api/contracts/{contract_id}/watchtower/alerts/{alert_id}/close")
def close_contract_watchtower_alert(
    contract_id: int,
    alert_id: int,
    user=Depends(require_user),
):
    """Close an open Watchtower alert."""
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    try:
        return close_watch_alert(
            contract_id=contract_id,
            user_id=user_id,
            alert_id=alert_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print(f"[WATCHTOWER ALERT] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Failed to close Watchtower alert.",
        )


@app.get("/api/contracts/{contract_id}/watchtower/events")
def list_watchtower_events(
    contract_id: int,
    user=Depends(require_user)
):
    user_id = int(user["id"])
    if get_contract(contract_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return {"success": True, "events": get_watch_events(contract_id, user_id)}


@app.get("/api/contracts/{contract_id}")
def get_contract_detail(
    contract_id: int,
    user=Depends(require_user)
):
    """Get full contract analysis."""
    user_id = int(user["id"])
    contract_row = get_contract(contract_id, user_id)
    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )
    
    import json
    try:
        clauses = json.loads(contract_row["clauses_json"])
        summary = json.loads(contract_row["summary_json"]) if contract_row["summary_json"] else {}
    except Exception as exc:
        print(f"[CONTRACT] Failed to parse contract data: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load contract data."
        )
    
    return {
        "id": contract_row["id"],
        "filename": contract_row["filename"],
        "clauses": clauses,
        "summary": summary,
        "created_at": contract_row["created_at"]
    }


@app.get("/api/contracts/{contract_id}/report.pdf")
def download_contract_analysis_report(
    contract_id: int,
    user=Depends(require_user)
):
    """Build a downloadable PDF summary from the authenticated user's saved analysis."""
    user_id = int(user["id"])
    contract_row = get_contract(contract_id, user_id)
    if contract_row is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    try:
        clauses = json.loads(contract_row["clauses_json"] or "[]")
        summary = json.loads(contract_row["summary_json"] or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        print(f"[REPORT] Failed to parse saved analysis for contract {contract_id}: {exc}")
        raise HTTPException(status_code=500, detail="Saved analysis could not be read.")

    if not isinstance(clauses, list):
        clauses = []
    if not isinstance(summary, dict):
        summary = {}

    try:
        from io import BytesIO
        from xml.sax.saxutils import escape
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether
        )
    except ImportError as exc:
        print(f"[REPORT] ReportLab is required to generate PDF reports: {exc}")
        raise HTTPException(
            status_code=503,
            detail="PDF report support is not installed. Install the report dependency and restart ClauseGuard."
        )

    def safe_text(value, max_chars=None):
        if value is None:
            value = "Not provided"
        if isinstance(value, (list, tuple, set)):
            value = "; ".join(str(item) for item in value)
        text_value = str(value).replace("\r\n", "\n").replace("\r", "\n")
        text_value = text_value.translate(str.maketrans({
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-",
            "\u00a0": " ",
        }))
        text_value = "".join(ch if (ch in "\n\t" or ord(ch) >= 32) else " " for ch in text_value)
        text_value = text_value.encode("latin-1", "replace").decode("latin-1")
        if max_chars is not None and len(text_value) > max_chars:
            text_value = text_value[:max_chars].rstrip() + " ... [truncated in summary report]"
        return text_value

    def para(value, style):
        return Paragraph(escape(safe_text(value)).replace("\n", "<br/>"), style)

    levels = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    scores = []
    normalized_clauses = []
    for index, clause in enumerate(clauses):
        if not isinstance(clause, dict):
            continue
        level = str(clause.get("risk_level") or "LOW").upper()
        if level not in levels:
            level = "LOW"
        levels[level] += 1
        try:
            score = float(clause.get("risk_score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0
        scores.append(score)
        normalized_clauses.append((score, index, level, clause))

    overall_score = summary.get("overall_score")
    if overall_score is None:
        overall_score = round(sum(scores) / len(scores)) if scores else 0
    total_clauses = len(normalized_clauses)
    attention_count = summary.get("attention_count", levels["HIGH"] + levels["MEDIUM"])

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CGBrand", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=colors.HexColor("#6B5B36"),
        alignment=TA_LEFT, spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="CGTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=27, textColor=colors.HexColor("#171815"),
        alignment=TA_LEFT, spaceAfter=7
    ))
    styles.add(ParagraphStyle(
        name="CGSubtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#5C5E57"), spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name="CGSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=colors.HexColor("#24251F"),
        spaceBefore=12, spaceAfter=7, keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="CGClause", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=10, leading=14, textColor=colors.HexColor("#24251F"),
        spaceBefore=8, spaceAfter=3, keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="CGBody", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.7, leading=12.5, textColor=colors.HexColor("#30312D"), spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="CGSmall", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.8, leading=10.5, textColor=colors.HexColor("#62645C"), spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        name="CGKPI", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=13, leading=16, textColor=colors.HexColor("#24251F"), alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name="CGKPIlabel", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.2, leading=9, textColor=colors.HexColor("#64665E"), alignment=TA_CENTER
    ))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=19 * mm, leftMargin=19 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"ClauseGuard Analysis Summary - {safe_text(contract_row['filename'] or 'Contract')}",
        author="ClauseGuard"
    )

    story = [
        para("CLAUSEGUARD  /  CONTRACT INTELLIGENCE", styles["CGBrand"]),
        para("Contract Analysis Summary", styles["CGTitle"]),
        para("A saved summary of the clause-level analysis performed by ClauseGuard. This report is intended to support review and does not constitute legal advice.", styles["CGSubtitle"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#B7A16B"), spaceBefore=2, spaceAfter=12),
    ]

    filename = safe_text(contract_row["filename"] or f"Untitled contract {contract_id}")
    created_at = safe_text(contract_row["created_at"] or "Not recorded")
    meta_data = [
        [para("CONTRACT", styles["CGSmall"]), para("ANALYZED ON", styles["CGSmall"]), para("CLAUSEGUARD ID", styles["CGSmall"])],
        [para(filename, styles["CGBody"]), para(created_at, styles["CGBody"]), para(str(contract_id), styles["CGBody"])],
    ]
    meta_table = Table(meta_data, colWidths=[80*mm, 47*mm, 40*mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F4F1E9")),
        ("BOX", (0,0), (-1,-1), .5, colors.HexColor("#D7D2C5")),
        ("INNERGRID", (0,0), (-1,-1), .35, colors.HexColor("#E0DBCF")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story.extend([meta_table, Spacer(1, 10), para("Executive summary", styles["CGSection"])])

    kpi_data = [[
        para(str(overall_score), styles["CGKPI"]),
        para(str(total_clauses), styles["CGKPI"]),
        para(str(levels["HIGH"]), styles["CGKPI"]),
        para(str(levels["MEDIUM"]), styles["CGKPI"]),
        para(str(levels["LOW"]), styles["CGKPI"]),
    ], [
        para("MEAN RISK SCORE", styles["CGKPIlabel"]),
        para("CLAUSES REVIEWED", styles["CGKPIlabel"]),
        para("HIGH", styles["CGKPIlabel"]),
        para("MEDIUM", styles["CGKPIlabel"]),
        para("LOW", styles["CGKPIlabel"]),
    ]]
    kpi_table = Table(kpi_data, colWidths=[35*mm, 35*mm, 31*mm, 31*mm, 31*mm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#FBFAF6")),
        ("BOX", (0,0), (-1,-1), .6, colors.HexColor("#D7D2C5")),
        ("INNERGRID", (0,0), (-1,-1), .35, colors.HexColor("#E4E0D6")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 9), ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.extend([kpi_table, Spacer(1, 8), para(
        f"{attention_count} clause(s) are marked HIGH or MEDIUM and may warrant closer human review. The score is a summary of the application's current rule-based signals, not a probability that the contract is legally unsafe.",
        styles["CGBody"]
    )])

    story.append(para("Risk distribution", styles["CGSection"]))
    risk_rows = [
        [para("Risk level", styles["CGSmall"]), para("Number of clauses", styles["CGSmall"]), para("Interpretation", styles["CGSmall"])],
        [para("High", styles["CGBody"]), para(str(levels["HIGH"]), styles["CGBody"]), para("Strong signals for priority review", styles["CGBody"])],
        [para("Medium", styles["CGBody"]), para(str(levels["MEDIUM"]), styles["CGBody"]), para("Potential concern requiring context", styles["CGBody"])],
        [para("Low", styles["CGBody"]), para(str(levels["LOW"]), styles["CGBody"]), para("Fewer signals under the current rules", styles["CGBody"])],
    ]
    risk_table = Table(risk_rows, colWidths=[35*mm, 42*mm, 86*mm], repeatRows=1)
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EEEAE0")),
        ("BOX", (0,0), (-1,-1), .5, colors.HexColor("#D7D2C5")),
        ("INNERGRID", (0,0), (-1,-1), .35, colors.HexColor("#E0DBCF")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(risk_table)

    flagged = [item for item in normalized_clauses if item[2] in ("HIGH", "MEDIUM")]
    if not flagged:
        flagged = sorted(normalized_clauses, key=lambda item: item[0], reverse=True)[:8]
        story.append(para("No HIGH or MEDIUM clauses were recorded. The following section lists the highest-scoring available clauses for reference.", styles["CGSmall"]))
    else:
        flagged.sort(key=lambda item: item[0], reverse=True)

    story.append(para("Priority findings", styles["CGSection"]))
    if not flagged:
        story.append(para("No clause-level findings were saved in this analysis.", styles["CGBody"]))
    else:
        max_findings = 30
        for score, index, level, clause in flagged[:max_findings]:
            clause_id = safe_text(clause.get("clause_id", index + 1))
            clause_type = safe_text(clause.get("clause_type") or clause.get("title") or "Unclassified clause")
            title = f"Clause {clause_id} - {clause_type}"
            story.append(para(title, styles["CGClause"]))
            story.append(para(f"Risk level: {level}    |    Risk score: {score:g}/100", styles["CGSmall"]))
            clause_text = clause.get("text") or clause.get("clause_text") or clause.get("original_text") or "Source wording was not stored for this clause."
            story.append(para("Original wording", styles["CGSmall"]))
            story.append(para(safe_text(clause_text, 1800), styles["CGBody"]))
            flags = clause.get("risk_flags") or clause.get("flags") or []
            reasons = clause.get("risk_reasons") or clause.get("reasons") or []
            if flags:
                story.append(para("Detected signals: " + safe_text(flags, 650), styles["CGBody"]))
            if reasons:
                story.append(para("Why it was flagged: " + safe_text(reasons, 1100), styles["CGBody"]))
            story.append(Spacer(1, 3))
        if len(flagged) > max_findings:
            story.append(para(f"This summary report includes the top {max_findings} priority findings. The application contains the full saved analysis for this contract.", styles["CGSmall"]))

    story.extend([
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=.5, color=colors.HexColor("#D7D2C5"), spaceBefore=4, spaceAfter=8),
        para("How to read this report", styles["CGSection"]),
        para("ClauseGuard uses document parsing, clause classification and rule-based risk signals to organize provisions that may deserve attention. The report reflects the analysis saved by the application at the time shown above. It may miss risks, identify false positives, or lack jurisdiction-specific context. Verify important findings against the complete agreement and consult a qualified legal professional for legal advice.", styles["CGBody"]),
        para("Generated by ClauseGuard from saved analysis data. This report does not modify the original agreement.", styles["CGSmall"]),
    ])

    def draw_page_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7D2C5"))
        canvas.setLineWidth(.5)
        canvas.line(19*mm, 13*mm, A4[0] - 19*mm, 13*mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#77786F"))
        canvas.drawString(19*mm, 8.5*mm, "ClauseGuard | Contract analysis summary")
        canvas.drawRightString(A4[0] - 19*mm, 8.5*mm, f"Page {document.page}")
        canvas.restoreState()

    try:
        doc.build(story, onFirstPage=draw_page_footer, onLaterPages=draw_page_footer)
    except Exception as exc:
        print(f"[REPORT] PDF generation failed for contract {contract_id}: {exc}")
        raise HTTPException(status_code=500, detail="Could not generate the contract summary PDF.")

    safe_basename = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(contract_row["filename"] or f"contract_{contract_id}").stem).strip("._")
    if not safe_basename:
        safe_basename = f"contract_{contract_id}"
    download_name = f"{safe_basename[:70]}_ClauseGuard_Report.pdf"
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.get("/api/contracts/{contract_id}/chat")
def get_contract_chat_history(
    contract_id: int,
    user=Depends(require_user)
):
    """Get chat history for a contract."""
    user_id = int(user["id"])
    
    # Verify contract belongs to user
    contract_row = get_contract(contract_id, user_id)
    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )
    
    history_rows = get_chat_history(contract_id, user_id, limit=50)
    messages = []
    for row in history_rows:
        messages.append({
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "answer_type": row["answer_type"],
            "grounded": bool(row["grounded"]),
            "sources": json.loads(row["sources_json"]) if row["sources_json"] else [],
            "follow_up_suggestions": json.loads(row["follow_up_suggestions_json"]) if row["follow_up_suggestions_json"] else [],
            "created_at": row["created_at"]
        })
    
    return {
        "messages": messages
    }


@app.delete("/api/contracts/{contract_id}/chat")
def clear_contract_chat_history(
    contract_id: int,
    user=Depends(require_user)
):
    """Clear chat history for a contract."""
    user_id = int(user["id"])
    
    # Verify contract belongs to user
    contract_row = get_contract(contract_id, user_id)
    if contract_row is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found."
        )
    
    delete_chat_history(contract_id, user_id)
    return {"message": "Chat history cleared."}

# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status":
            "ok",

        "service":
            "ClauseGuard"
    }


# ============================================================
# TEXT ANALYSIS
# ============================================================

@app.post("/analyze")
def analyze(
    payload: ContractRequest,
    user=Depends(
        require_user
    )
):

    text = payload.text.strip()


    if not text:

        raise HTTPException(
            status_code=400,
            detail=(
                "Contract text cannot be empty."
            )
        )


    clauses = analyze_document(
        text
    )

    summary = build_summary(clauses)
    user_id = int(user["id"])
    
    # Save contract to database
    contract_id = save_contract(
        user_id=user_id,
        filename=None,
        original_text=text,
        clauses=clauses,
        summary=summary
    )

    return {
        "message":
            "Contract analyzed successfully.",

        "contract_id":
            contract_id,

        "total_clauses":
            len(clauses),

        "clauses":
            clauses,

        "summary":
            summary,

        "user": {
            "id":
                user_id,

            "name":
                user["name"]
        }
    }


# ============================================================
# FILE ANALYSIS
# ============================================================

@app.post("/analyze-file")
async def analyze_file(
    file: UploadFile = File(...),
    user=Depends(
        require_user
    )
):

    # --------------------------------------------------------
    # VALIDATE FILE
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )


    extension = Path(
        file.filename
    ).suffix.lower()


    if extension not in {
        ".pdf",
        ".docx"
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only PDF and DOCX files "
                "are supported."
            )
        )


    temp_path = None


    try:

        # ----------------------------------------------------
        # SAVE TEMPORARY FILE
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension
        ) as temp_file:

            temp_path = Path(
                temp_file.name
            )


            shutil.copyfileobj(
                file.file,
                temp_file
            )


        # ----------------------------------------------------
        # DETERMINE FILE TYPE
        # ----------------------------------------------------

        file_type = extension.lstrip(
            "."
        ).lower()


        # ----------------------------------------------------
        # PARSE DOCUMENT
        # ----------------------------------------------------

        parsed_document = parse_document(
            str(temp_path),
            file_type
        )


        # ----------------------------------------------------
        # CONVERT PAGE STRUCTURE INTO TEXT
        # ----------------------------------------------------

        extracted_text = (
            normalize_extracted_text(
                parsed_document
            )
        )


        # ----------------------------------------------------
        # CHECK EXTRACTION
        # ----------------------------------------------------

        if not extracted_text:

            raise HTTPException(
                status_code=422,
                detail=(
                    "No readable text could be "
                    "extracted from this document."
                )
            )


        # ----------------------------------------------------
        # ANALYZE DOCUMENT
        # ----------------------------------------------------

        clauses = analyze_document(
            extracted_text
        )

        summary = build_summary(clauses)
        user_id = int(user["id"])

        # Save contract to database
        contract_id = save_contract(
            user_id=user_id,
            filename=file.filename,
            original_text=extracted_text,
            clauses=clauses,
            summary=summary
        )

        # ----------------------------------------------------
        # AUTO-ACTIVATE WATCHTOWER FOR NEW CONTRACTS
        # ----------------------------------------------------
        # Watchtower is supplemental. A monitor extraction failure must
        # never turn a successful contract analysis into a failed upload.
        try:
            watchtower_preview = extract_monitorable_items(
                contract_id=contract_id,
                user_id=user_id
            )
            watchtower_items = (
                watchtower_preview.get("items")
                or watchtower_preview.get("monitorable_items")
                or []
            )

            if watchtower_items:
                activate_watchtower(
                    contract_id=contract_id,
                    user_id=user_id,
                    selected_items=watchtower_items
                )
            else:
                print(
                    f"[WATCHTOWER AUTO-ACTIVATION] No monitorable provisions "
                    f"detected for contract {contract_id}."
                )

        except Exception as watchtower_error:
            print(
                f"[WATCHTOWER AUTO-ACTIVATION] Contract {contract_id}: "
                f"{watchtower_error}"
            )

        # ----------------------------------------------------
        # RETURN RESULTS
        # ----------------------------------------------------

        return {
            "message":
                "Contract analyzed successfully.",

            "contract_id":
                contract_id,

            "filename":
                file.filename,

            "total_clauses":
                len(clauses),

            "clauses":
                clauses,

            "summary":
                summary,

            "user": {
                "id":
                    user_id,

                "name":
                    user["name"]
            }
        }


    finally:

        # ----------------------------------------------------
        # CLEAN TEMPORARY FILE
        # ----------------------------------------------------

        if (
            temp_path is not None
            and temp_path.exists()
        ):

            try:

                temp_path.unlink()

            except OSError:

                pass