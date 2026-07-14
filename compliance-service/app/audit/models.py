from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class AuditLog(db.Model):
    """General-purpose append-only log for operator actions (overrides,
    manual sanctions list reloads, etc). Screening-decision-specific
    reasoning lives in ScreeningMatch, not here."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    actor = db.Column(db.String(128), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    target_type = db.Column(db.String(64), nullable=True)
    target_id = db.Column(db.String(64), nullable=True)
    detail = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
