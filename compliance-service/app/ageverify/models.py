from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class AgeVerification(db.Model):
    """Deliberately isolated from every Travel Rule table above: no foreign
    key into screening_decisions or sanctioned_entities. DSA Article 28 age
    checks and TFR Travel Rule identity checks are two distinct regulatory
    regimes and must never be joinable in one record."""

    __tablename__ = "age_verifications"

    id = db.Column(db.Integer, primary_key=True)
    subject_reference = db.Column(db.String(128), nullable=False, index=True)  # opaque platform-side user ref
    adapter = db.Column(db.String(32), nullable=False)  # "mock" | "zyphe" | "eu_oid4vp" (future)
    verified = db.Column(db.Boolean, nullable=False)
    method = db.Column(db.String(32), nullable=True)
    proof_token_hash = db.Column(db.String(128), nullable=True)  # never store the raw proof/token
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
