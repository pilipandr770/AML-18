from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class UsageEvent(db.Model):
    """One row per billable API call. Append-only, like AuditLog/ListSnapshot
    elsewhere in this codebase -- quota checks and any future usage-based
    billing both read this by range rather than a mutable counter, and it
    doubles as an audit trail of what a project was actually charged for.
    Only written to when BILLING_ENABLED is true (see app/billing/metering.py);
    a self-hosted deployment never populates this table."""

    __tablename__ = "billing_usage_events"

    id = db.Column(db.Integer, primary_key=True)
    developer_project_id = db.Column(db.Integer, db.ForeignKey("developer_projects.id"), nullable=False, index=True)
    module = db.Column(db.String(32), nullable=False)
    endpoint = db.Column(db.String(64), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True)

    __table_args__ = (
        db.Index("ix_billing_usage_events_project_occurred", "developer_project_id", "occurred_at"),
    )
