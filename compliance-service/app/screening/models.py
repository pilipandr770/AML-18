from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class ScreeningDecision(db.Model):
    """One row per webhook call: the aggregate decision sent back to Envoy,
    plus everything needed to reconstruct why, for a BaFin-style audit."""

    __tablename__ = "screening_decisions"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(36), nullable=False, index=True)  # Envoy's uuid
    counterparty_name = db.Column(db.String(256), nullable=True)
    counterparty_lei = db.Column(db.String(32), nullable=True)
    list_snapshot_id = db.Column(db.Integer, db.ForeignKey("list_snapshots.id"), nullable=True)
    decision = db.Column(db.String(16), nullable=False)  # accepted | review | rejected
    transfer_action_sent = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    human_override = db.Column(db.Boolean, nullable=False, default=False)
    human_override_by = db.Column(db.String(128), nullable=True)
    human_override_decision = db.Column(db.String(16), nullable=True)
    human_override_reason = db.Column(db.Text, nullable=True)
    human_override_at = db.Column(db.DateTime(timezone=True), nullable=True)

    webhook_request_raw = db.Column(db.JSON, nullable=True)  # the full incoming payload, for audit replay

    matches = db.relationship("ScreeningMatch", back_populates="decision", cascade="all, delete-orphan")


class ScreeningMatch(db.Model):
    """Per-party, per-candidate detail. This table is the actual
    explainability backbone — the review UI and any audit render from here,
    not from a bare score on ScreeningDecision."""

    __tablename__ = "screening_matches"

    id = db.Column(db.Integer, primary_key=True)
    screening_decision_id = db.Column(db.Integer, db.ForeignKey("screening_decisions.id"), nullable=False)
    party_role = db.Column(db.String(24), nullable=False)  # originator | beneficiary | originator_vasp | beneficiary_vasp
    sanctioned_entity_id = db.Column(db.Integer, db.ForeignKey("sanctioned_entities.id"), nullable=True)
    matched_name_variant = db.Column(db.String(256), nullable=True)
    name_score = db.Column(db.Float, nullable=False)
    corroborating_fields_matched = db.Column(db.JSON, nullable=True)  # {"dob": "...", "nationality": "..."}
    rule_branch = db.Column(db.String(64), nullable=False)  # ties to a row in the decision-band table
    composite_score = db.Column(db.Float, nullable=False)
    rank = db.Column(db.Integer, nullable=False, default=1)  # 1 = best candidate considered for this party

    decision = db.relationship("ScreeningDecision", back_populates="matches")
    sanctioned_entity = db.relationship("SanctionedEntity")
