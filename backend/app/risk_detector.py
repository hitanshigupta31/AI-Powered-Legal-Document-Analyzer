import re


def contains_any(
    text: str,
    patterns: list[str]
) -> bool:

    return any(
        pattern in text
        for pattern in patterns
    )


def contains_month_duration(text: str) -> bool:
    """
    Detect month-based duration patterns like:
    - 18 months, eighteen months
    - 18 (18) months, eighteen (18) months
    - 6 month, 12 month, etc.
    """
    # Pattern: number or word followed by "month"
    month_pattern = r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|\d+)\s*(?:\(\d+\))?\s*months?\b'
    return bool(re.search(month_pattern, text, re.IGNORECASE))


def add_signal(
    score: int,
    flags: list,
    reasons: list,
    points: int,
    flag: str,
    reason: str
):
    """
    Add one risk signal to the clause.
    """

    score += points

    flags.append(flag)

    reasons.append(reason)

    return score


def detect_risk(
    clause_type: str,
    text: str
):
    """
    Deterministic baseline risk engine.

    This is NOT a legal judgment.
    It detects contractual patterns that may
    deserve human review.
    """

    text_lower = text.lower()

    score = 0

    flags = []

    reasons = []


    # =====================================================
    # TERMINATION
    # =====================================================

    if clause_type == "Termination":

        if contains_any(
            text_lower,
            [
                "without notice",
                "without prior notice",
                "immediately and without notice",
                "immediately",
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                40,
                "Termination without meaningful notice",
                "The provision may allow termination with little or no advance notice."
            )


        if contains_any(
            text_lower,
            [
                "at any time",
                "for any reason",
                "for no reason",
                "without cause",
                "sole discretion"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                25,
                "Broad termination right",
                "The provision gives a party broad discretion to terminate the agreement."
            )


        if "either party" not in text_lower:

            score = add_signal(
                score,
                flags,
                reasons,
                10,
                "Potentially one-sided termination",
                "The termination provision may give one party broader rights than the other."
            )


    # =====================================================
    # INDEMNIFICATION
    # =====================================================

    elif clause_type == "Indemnification":

        if contains_any(
            text_lower,
            [
                "any and all claims",
                "any and all",
                "all claims",
                "any claims",
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                35,
                "Broad indemnification scope",
                "The indemnification language appears broad and may cover a wide range of claims."
            )


        if contains_any(
            text_lower,
            [
                "indemnify, defend, and hold harmless",
                "indemnify and hold harmless",
                "hold harmless"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                20,
                "Defense and indemnity obligation",
                "The obligation may require the party to defend and compensate the other party for covered claims."
            )


        if contains_any(
            text_lower,
            [
                "unlimited",
                "not subject to any monetary cap",
                "without limitation",
                "no monetary cap"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                35,
                "Potentially uncapped liability",
                "The provision appears not to impose a clear monetary limit on the obligation."
            )


        if contains_any(
            text_lower,
            [
                "attorneys' fees",
                "attorney's fees",
                "legal fees"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                10,
                "Legal-fee exposure",
                "The provision may extend financial exposure to legal or attorney fees."
            )


    # =====================================================
    # AUTO RENEWAL
    # =====================================================

    elif clause_type == "Auto-Renewal":

        if contains_any(
            text_lower,
            [
                "automatically renew",
                "automatic renewal",
                "successive",
                "renewal term"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                35,
                "Automatic renewal",
                "The agreement may continue automatically unless a party takes action to stop renewal."
            )


        if contains_any(
            text_lower,
            [
                "90 days",
                "ninety days",
                "60 days",
                "sixty days",
                "120 days",
                "one hundred twenty days"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                20,
                "Extended non-renewal notice",
                "A relatively long notice window may make it easier to miss the deadline to prevent renewal."
            )


        if contains_any(
            text_lower,
            [
                "remaining fees",
                "fees through the end",
                "full remaining term"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                25,
                "Continuing fee obligation",
                "The provision may require payment for the remaining contractual term even after early termination."
            )


    # =====================================================
    # LIABILITY
    # =====================================================

    elif clause_type == "Limitation of Liability":

        if contains_any(
            text_lower,
            [
                "unlimited liability",
                "unlimited",
                "not subject to any monetary cap",
                "no monetary cap"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                50,
                "Potentially unlimited liability",
                "The provision appears to leave liability without a clearly defined monetary ceiling."
            )


        if contains_any(
            text_lower,
            [
                "aggregate liability",
                "liability shall not exceed",
                "maximum liability"
            ]
        ):

            # A liability cap itself is not necessarily a
            # negative issue, so only a small baseline score
            # is added here.
            score = add_signal(
                score,
                flags,
                reasons,
                10,
                "Liability allocation provision",
                "The agreement contains a specific contractual allocation or cap on liability."
            )


    # =====================================================
    # IP / OWNERSHIP
    # =====================================================

    elif clause_type == "Intellectual Property":

        if contains_any(
            text_lower,
            [
                "assigns all right, title and interest",
                "all right, title and interest",
                "hereby assigns",
                "irrevocably assigns"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                45,
                "Broad intellectual-property assignment",
                "The provision transfers broad intellectual-property rights to the other party."
            )


        if contains_any(
            text_lower,
            [
                "pre-existing",
                "background intellectual property",
                "prior inventions"
            ]
        ) and contains_any(
            text_lower,
            [
                "perpetual",
                "irrevocable",
                "worldwide",
                "royalty-free"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                30,
                "Broad rights over pre-existing materials",
                "Pre-existing materials may be subject to broad ongoing rights or licenses."
            )


    # =====================================================
    # CONFIDENTIALITY
    # =====================================================

    elif clause_type == "Confidentiality":

        if contains_any(
            text_lower,
            [
                "perpetual",
                "at all times",
                "survive termination",
                "indefinitely"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                20,
                "Long-lasting confidentiality obligation",
                "The confidentiality obligation may continue for an extended or indefinite period."
            )


        if contains_any(
            text_lower,
            [
                "trade secrets",
                "all confidential information",
                "non-public information"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                10,
                "Broad confidential-information scope",
                "The provision covers a broad range of information."
            )


    # =====================================================
    # NON-COMPETE / RESTRICTIVE COVENANTS
    # =====================================================

    elif clause_type == "Restrictive Covenant":

        if contains_any(
            text_lower,
            [
                "non-compete",
                "non compete",
                "noncompetition",
                "competing business"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                40,
                "Non-compete restriction",
                "The clause restricts participation in potentially competing activities."
            )


        if contains_any(
            text_lower,
            [
                "five years",
                "3 years",
                "three years",
                "two years",
                "one year"
            ]
        ) or contains_month_duration(text_lower):

            score = add_signal(
                score,
                flags,
                reasons,
                20,
                "Time-limited post-termination restriction",
                "The restriction may continue after the agreement ends."
            )


    # =====================================================
    # PAYMENT
    # =====================================================

    elif clause_type == "Payment":

        if contains_any(
            text_lower,
            [
                "net 60",
                "net sixty",
                "net 90",
                "ninety days",
                "60 days"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                20,
                "Extended payment period",
                "The payment provision may create a relatively long period before invoices are paid."
            )


        if contains_any(
            text_lower,
            [
                "sole discretion",
                "may withhold",
                "may deduct"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                20,
                "One-sided payment discretion",
                "The provision gives one party discretion to withhold, deduct, or determine payments."
            )


    # =====================================================
    # ARBITRATION
    # =====================================================

    elif clause_type == "Dispute Resolution":

        if contains_any(
            text_lower,
            [
                "binding arbitration",
                "mandatory arbitration",
                "waive a trial by jury",
                "waive trial by jury"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                25,
                "Mandatory dispute-resolution mechanism",
                "Disputes may be required to proceed through arbitration or involve a jury-trial waiver."
            )


    # =====================================================
    # DOCUMENT-WIDE FALLBACK
    # =====================================================

    else:

        # Even if the classifier does not recognize the
        # clause type, scan for particularly strong signals.

        if contains_any(
            text_lower,
            [
                "unlimited liability",
                "not subject to any monetary cap",
                "irrevocably assigns",
                "non-compete",
                "automatically renew",
                "without notice",
                "binding arbitration"
            ]
        ):

            score = add_signal(
                score,
                flags,
                reasons,
                30,
                "Potentially significant contractual restriction",
                "The clause contains language that may warrant closer review."
            )


    # =====================================================
    # FINAL RISK LEVEL
    # =====================================================

    score = min(
        score,
        100
    )


    if score >= 70:

        risk_level = "HIGH"

    elif score >= 35:

        risk_level = "MEDIUM"

    else:

        risk_level = "LOW"


    return {

        "risk_level":
            risk_level,

        "risk_score":
            score,

        "risk_flags":
            flags,

        "risk_reasons":
            reasons
    }