from datetime import datetime, timezone
from uuid import uuid4

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class WalletOwnershipChallenge(db.Model):
    """A server-issued, single-use nonce a wallet must sign to prove control
    of its private key. Never accept a client-supplied message to sign --
    that would let a signature obtained for an unrelated purpose (e.g. a
    phishing prompt) be replayed here as "proof of ownership"."""

    __tablename__ = "wallet_ownership_challenges"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), nullable=False, unique=True, default=lambda: uuid4().hex)
    network = db.Column(db.String(16), nullable=False)
    address = db.Column(db.String(128), nullable=False, index=True)
    nonce = db.Column(db.String(64), nullable=False, default=lambda: uuid4().hex)
    message = db.Column(db.Text, nullable=False)
    consumed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)


class WalletOwnershipVerification(db.Model):
    """One row per self-hosted-wallet ownership check, required by the EBA
    Travel Rule guidelines / BaFin GwG Sec. 15a for self-hosted-wallet
    transfers at or above the configured EUR threshold. Deliberately
    isolated from screening_decisions: this is a distinct control
    (ownership/control of an address), not a sanctions match."""

    __tablename__ = "wallet_ownership_verifications"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), nullable=False, unique=True, default=lambda: uuid4().hex)
    transaction_id = db.Column(db.String(36), nullable=True, index=True)  # Envoy transfer this check relates to, if any
    network = db.Column(db.String(16), nullable=False)
    address = db.Column(db.String(128), nullable=False, index=True)
    method = db.Column(db.String(24), nullable=False)  # signed_message | test_transfer
    transfer_amount_eur = db.Column(db.Float, nullable=True)
    threshold_eur = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")  # pending | verified | failed
    verified = db.Column(db.Boolean, nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    evidence = db.Column(db.JSON, nullable=True)  # signed_message: recovered_address; test_transfer: tx_hash/confirmations
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
