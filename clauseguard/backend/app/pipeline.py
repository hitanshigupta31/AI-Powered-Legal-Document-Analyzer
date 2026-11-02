from app.clause_segmenter import segment_clauses
from app.clause_classifier import classify_clause
from app.risk_detector import detect_risk


def analyze_document(text: str):
    segmented = segment_clauses(text)

    results = []

    for clause in segmented:
        clause_type = classify_clause(clause["text"])
        risk = detect_risk(clause_type, clause["text"])

        results.append({
            "clause_id": clause["clause_id"],
            "title": clause["title"],
            "text": clause["text"],
            "clause_type": clause_type,
            "risk_level": risk["risk_level"],
            "risk_score": risk["risk_score"],
            "risk_flags": risk["risk_flags"],
            "risk_reasons": risk["risk_reasons"],
        })

    return results