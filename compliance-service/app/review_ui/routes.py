from flask import Blueprint, jsonify

review_bp = Blueprint("review_ui", __name__, url_prefix="/review")


@review_bp.get("/health")
def health():
    # Placeholder until Phase 1 adds the real explainability/override UI
    # (list screening_decisions, show screening_matches, allow override).
    return jsonify({"status": "ok"})
