# ============================================================
# CLAUSEGUARD - AI TEST
# ============================================================

from app.ai_service import generate_clause_insight


test_clause = {

    "clause_id": 8,

    "clause_type":
        "Indemnification",

    "risk_level":
        "HIGH",

    "risk_score":
        80,

    "risk_flags": [
        "Broad indemnification",
        "Potentially uncapped exposure"
    ],

    "risk_reasons": [
        "The clause contains broad indemnification language."
    ],

    "text": """
Vendor shall indemnify, defend and hold harmless
Company from and against any and all claims,
losses, damages, liabilities, costs and expenses
arising out of the Vendor's services.
"""
}


print()
print("=" * 70)
print("CLAUSEGUARD AI TEST")
print("=" * 70)
print()

try:

    result = generate_clause_insight(
        test_clause
    )

    print(result)

except Exception as error:

    print(
        "AI TEST FAILED:"
    )

    print(error)

print()
print("=" * 70)