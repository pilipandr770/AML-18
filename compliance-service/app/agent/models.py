"""Persistence for the AI compliance agent. Everything here is keyed by
developer_project_id (the tenant boundary) and deliberately separate from
the Travel Rule tables (screening_decisions/screening_matches), wallet-
ownership and age-verification data -- those regimes must never be joinable
in one record. Only used when AGENT_ENABLED=true."""

from datetime import datetime, timezone
from uuid import uuid4

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


MODE_MONITOR = "monitor"
MODE_OPERATE = "operate"

CLASS_CLEAR = "clear"
CLASS_NEEDS_REVIEW = "needs_review"
CLASS_RECOMMEND_BLOCK = "recommend_block"


class AgentSettings(db.Model):
    """One row per project. mode/policy are changed only through the
    authenticated owner routes, never by the agent itself."""

    __tablename__ = "agent_settings"

    id = db.Column(db.Integer, primary_key=True)
    developer_project_id = db.Column(
        db.Integer, db.ForeignKey("developer_projects.id"), nullable=False, unique=True
    )
    mode = db.Column(db.String(16), nullable=False, default=MODE_MONITOR)
    policy = db.Column(db.JSON, nullable=False, default=dict)  # validated by app.agent.policy.Policy
    policy_version = db.Column(db.Integer, nullable=False, default=1)
    # Instant stop: while true the agent can only record recommendations,
    # whatever the mode. Cleared only by the authenticated owner.
    kill_switch = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class OwnerAccount(db.Model):
    """Human owner of a project's agent: the only identity allowed to change
    mode or policy. Password + TOTP second factor."""

    __tablename__ = "agent_owner_accounts"

    id = db.Column(db.Integer, primary_key=True)
    developer_project_id = db.Column(db.Integer, db.ForeignKey("developer_projects.id"), nullable=False, index=True)
    email = db.Column(db.String(256), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)


class ModeConsent(db.Model):
    """Who agreed, when, to which operations, before OPERATE mode was enabled."""

    __tablename__ = "agent_mode_consents"

    id = db.Column(db.Integer, primary_key=True)
    developer_project_id = db.Column(db.Integer, db.ForeignKey("developer_projects.id"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("agent_owner_accounts.id"), nullable=False)
    operations = db.Column(db.JSON, nullable=False)  # list of operation names consented to
    granted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)


class AgentCase(db.Model):
    """One inbound transfer the agent examined."""

    __tablename__ = "agent_cases"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), nullable=False, unique=True, default=lambda: uuid4().hex)
    developer_project_id = db.Column(db.Integer, db.ForeignKey("developer_projects.id"), nullable=False, index=True)
    external_ref = db.Column(db.String(128), nullable=True)  # client's own transfer id
    chain = db.Column(db.String(32), nullable=False)
    asset = db.Column(db.String(16), nullable=False)
    amount = db.Column(db.Numeric(38, 18), nullable=False)
    tx_hash = db.Column(db.String(128), nullable=True, index=True)
    deposit_address = db.Column(db.String(128), nullable=False)
    counterparty_name = db.Column(db.String(256), nullable=True)  # untrusted external data
    counterparty_country = db.Column(db.String(8), nullable=True)
    memo = db.Column(db.Text, nullable=True)  # untrusted external data
    funds_check = db.Column(db.JSON, nullable=True)  # verify_incoming_funds result
    deterministic_decision = db.Column(db.String(16), nullable=True)  # accepted|review|rejected (floor; LLM can only raise)
    classification = db.Column(db.String(24), nullable=True)  # clear|needs_review|recommend_block
    explanation = db.Column(db.Text, nullable=True)
    evidence = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(24), nullable=False, default="open")  # open|auto_cleared|awaiting_human|resolved
    resolution = db.Column(db.String(24), nullable=True)
    resolved_by = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)


class AgentAuditEntry(db.Model):
    """Append-only, hash-chained log. entry_hash covers the entry's content
    plus prev_hash, so editing or deleting any earlier row breaks every
    later hash (see app.agent.journal.verify_chain)."""

    __tablename__ = "agent_audit_entries"

    id = db.Column(db.Integer, primary_key=True)
    developer_project_id = db.Column(db.Integer, db.ForeignKey("developer_projects.id"), nullable=False, index=True)
    seq = db.Column(db.Integer, nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    actor = db.Column(db.String(64), nullable=False)  # agent | policy_engine | owner:<email> | system
    event_type = db.Column(db.String(48), nullable=False)
    case_public_id = db.Column(db.String(32), nullable=True, index=True)
    payload = db.Column(db.JSON, nullable=False)
    prev_hash = db.Column(db.String(64), nullable=False)
    entry_hash = db.Column(db.String(64), nullable=False, unique=True)

    __table_args__ = (db.UniqueConstraint("developer_project_id", "seq", name="uq_agent_audit_project_seq"),)
