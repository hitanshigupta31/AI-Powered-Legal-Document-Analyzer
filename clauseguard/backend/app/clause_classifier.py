# ============================================================
# CLAUSEGUARD - CLAUSE CLASSIFIER
# ============================================================
#
# Current implementation:
# Rule-based baseline classifier.
#
# The purpose of this file is to identify the primary type
# of a legal clause before the risk engine analyzes it.
#
# This is intentionally a baseline implementation.
# A semantic / ML classifier will be added later.
# ============================================================


def classify_clause(text: str) -> str:
    """
    Classify a legal clause into its primary clause category.

    Parameters
    ----------
    text : str
        The complete text of a clause.

    Returns
    -------
    str
        The detected clause category.
    """

    text_lower = text.lower().strip()


    # ========================================================
    # INTELLECTUAL PROPERTY
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "intellectual property",
            "intellectual-property",
            "work product",
            "work-product",
            "assigns all right",
            "all right, title and interest",
            "hereby assigns",
            "irrevocably assigns",
            "inventions",
            "source code",
            "copyright",
            "patent rights",
            "ownership of the deliverables",
        ]
    ):
        return "Intellectual Property"


    # ========================================================
    # INDEMNIFICATION
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "indemnif",
            "hold harmless",
            "defend and indemnify",
            "defend, indemnify",
            "indemnify and defend",
        ]
    ):
        return "Indemnification"


    # ========================================================
    # LIMITATION OF LIABILITY
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "limitation of liability",
            "limitation on liability",
            "liability shall not exceed",
            "aggregate liability",
            "maximum liability",
            "unlimited liability",
            "liability cap",
            "cap on liability",
            "liable for",
            "liability",
        ]
    ):
        return "Limitation of Liability"


    # ========================================================
    # RESTRICTIVE COVENANTS
    # ========================================================
    #
    # IMPORTANT:
    # This is checked BEFORE Auto-Renewal.
    #
    # A restrictive-covenant clause may contain words such as
    # "renewal term" simply because the restriction remains
    # effective during renewal periods.
    #
    # That does NOT mean the clause itself is an automatic
    # renewal clause.
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "non-compete",
            "non compete",
            "noncompetition",
            "non-competition",
            "non-solicitation",
            "non solicitation",
            "nonsolicitation",
            "restrictive covenant",
            "restrictive covenants",
            "competing business",
            "compete with",
            "competes with",
            "solicit customers",
            "solicit clients",
            "solicit employees",
            "solicit contractors",
            "take away company customers",
            "take away customers",
        ]
    ):
        return "Restrictive Covenant"


    # ========================================================
    # AUTO-RENEWAL
    # ========================================================
    #
    # IMPORTANT:
    # We deliberately require actual automatic-renewal
    # language.
    #
    # "renewal term" by itself is NOT enough.
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "automatically renew",
            "automatic renewal",
            "shall renew automatically",
            "will renew automatically",
            "renewed automatically",
            "automatically extended",
            "automatically extend",
            "shall automatically extend",
            "will automatically extend",
        ]
    ):
        return "Auto-Renewal"


    # ========================================================
    # TERMINATION
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "termination",
            "terminate this agreement",
            "terminate the agreement",
            "terminate employment",
            "termination of employment",
            "termination for cause",
            "termination without cause",
            "terminate for cause",
            "terminate without cause",
            "terminated by either party",
            "termination date",
        ]
    ):
        return "Termination"


    # ========================================================
    # CONFIDENTIALITY
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "confidential information",
            "confidentiality",
            "confidential information",
            "trade secret",
            "trade secrets",
            "non-public information",
            "nonpublic information",
            "proprietary information",
            "proprietary information",
            "nondisclosure",
            "non-disclosure",
        ]
    ):
        return "Confidentiality"


    # ========================================================
    # PAYMENT / COMPENSATION
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "payment",
            "payments",
            "payment terms",
            "fee",
            "fees",
            "invoice",
            "invoices",
            "compensation",
            "salary",
            "base salary",
            "bonus",
            "annual bonus",
            "reimbursement",
            "reimburse",
            "amount payable",
        ]
    ):
        return "Payment"


    # ========================================================
    # DISPUTE RESOLUTION
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "arbitration",
            "binding arbitration",
            "mandatory arbitration",
            "dispute resolution",
            "jury trial",
            "trial by jury",
            "waive a jury",
            "waiver of jury",
        ]
    ):
        return "Dispute Resolution"


    # ========================================================
    # GOVERNING LAW
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "governing law",
            "laws of the state",
            "laws of the republic",
            "jurisdiction",
            "exclusive jurisdiction",
            "venue",
            "exclusive venue",
            "choice of law",
        ]
    ):
        return "Governing Law"


    # ========================================================
    # ASSIGNMENT
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "assignment",
            "assign this agreement",
            "assign its rights",
            "assign its obligations",
            "successors and assigns",
        ]
    ):
        return "Assignment"


    # ========================================================
    # WARRANTIES
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "warranties",
            "warranty",
            "represents and warrants",
            "representation and warranty",
            "representations and warranties",
            "as is and as available",
        ]
    ):
        return "Warranties"


    # ========================================================
    # SERVICES / DUTIES
    # ========================================================

    if any(
        phrase in text_lower
        for phrase in [
            "services",
            "scope of services",
            "duties",
            "responsibilities",
            "obligations",
            "shall provide",
            "shall perform",
            "engagement",
        ]
    ):
        return "Services"


    # ========================================================
    # GENERAL / MISCELLANEOUS
    # ========================================================

    return "Other"