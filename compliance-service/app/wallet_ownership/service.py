from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.extensions import db
from app.wallet_ownership.adapters import (
    AdapterError,
    AdapterNotConfiguredError,
    EVMTestTransferAdapter,
    build_challenge_message,
    recover_signer_address,
)
from app.wallet_ownership.models import WalletOwnershipChallenge, WalletOwnershipVerification


def _utcnow():
    return datetime.now(timezone.utc)


def get_test_transfer_adapter(config) -> EVMTestTransferAdapter:
    return EVMTestTransferAdapter(
        rpc_url=config.get("WALLET_OWNERSHIP_EVM_RPC_URL", ""),
        sender_private_key=config.get("WALLET_OWNERSHIP_EVM_SENDER_PRIVATE_KEY", ""),
        chain_id=int(config.get("WALLET_OWNERSHIP_EVM_CHAIN_ID", 1)),
        amount_wei=int(config.get("WALLET_OWNERSHIP_TEST_TRANSFER_AMOUNT_WEI", 1_000_000_000_000)),
        min_confirmations=int(config.get("WALLET_OWNERSHIP_TEST_TRANSFER_MIN_CONFIRMATIONS", 1)),
        timeout_seconds=float(config.get("WALLET_OWNERSHIP_EVM_RPC_TIMEOUT_SECONDS", 10)),
    )


def is_verification_required(transfer_amount_eur, threshold_eur) -> bool:
    return transfer_amount_eur is not None and transfer_amount_eur >= threshold_eur


def create_challenge(network: str, address: str, ttl_seconds: int) -> WalletOwnershipChallenge:
    nonce = uuid4().hex
    issued_at = _utcnow()
    message = build_challenge_message(
        network=network, address=address, nonce=nonce, issued_at=issued_at.isoformat()
    )
    row = WalletOwnershipChallenge(
        network=network,
        address=address,
        nonce=nonce,
        message=message,
        expires_at=issued_at + timedelta(seconds=ttl_seconds),
    )
    db.session.add(row)
    db.session.commit()
    return row


def verify_signed_message(
    challenge_public_id: str,
    signature: str,
    transfer_amount_eur,
    transaction_id,
    threshold_eur: float,
) -> WalletOwnershipVerification:
    challenge = WalletOwnershipChallenge.query.filter_by(public_id=challenge_public_id).first()
    if challenge is None:
        raise AdapterError("unknown challenge")
    if challenge.consumed:
        raise AdapterError("challenge already used")

    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        # SQLite drops tzinfo on round-trip even for DateTime(timezone=True)
        # columns; the value was always written in UTC (see _utcnow()).
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < _utcnow():
        raise AdapterError("challenge expired")

    recovered = recover_signer_address(challenge.message, signature)
    challenge.consumed = True

    verified = recovered.lower() == challenge.address.lower()

    row = WalletOwnershipVerification(
        transaction_id=transaction_id,
        network=challenge.network,
        address=challenge.address,
        method="signed_message",
        transfer_amount_eur=transfer_amount_eur,
        threshold_eur=threshold_eur,
        status="verified" if verified else "failed",
        verified=verified,
        verified_at=_utcnow() if verified else None,
        evidence={"recovered_address": recovered},
    )
    db.session.add(row)
    db.session.commit()
    return row


def start_test_transfer(
    network: str,
    address: str,
    transfer_amount_eur,
    transaction_id,
    threshold_eur: float,
    config,
) -> WalletOwnershipVerification:
    adapter = get_test_transfer_adapter(config)

    row = WalletOwnershipVerification(
        transaction_id=transaction_id,
        network=network,
        address=address,
        method="test_transfer",
        transfer_amount_eur=transfer_amount_eur,
        threshold_eur=threshold_eur,
        status="pending",
    )

    try:
        result = adapter.start_transfer(address)
    except AdapterNotConfiguredError:
        raise
    except AdapterError as exc:
        row.status = "failed"
        row.last_error = str(exc)
        db.session.add(row)
        db.session.commit()
        return row

    row.evidence = {"tx_hash": result.tx_hash}
    db.session.add(row)
    db.session.commit()
    return row


def refresh_test_transfer(public_id: str, config) -> WalletOwnershipVerification | None:
    row = WalletOwnershipVerification.query.filter_by(public_id=public_id).first()
    if row is None:
        return None
    if row.method != "test_transfer" or row.status != "pending":
        return row

    tx_hash = (row.evidence or {}).get("tx_hash")
    if not tx_hash:
        return row

    adapter = get_test_transfer_adapter(config)
    try:
        result = adapter.get_transfer_status(tx_hash)
    except AdapterNotConfiguredError:
        raise
    except AdapterError as exc:
        row.status = "failed"
        row.last_error = str(exc)
        db.session.commit()
        return row

    if result.status == "pending":
        return row

    row.evidence = {**(row.evidence or {}), "confirmations": result.confirmations}
    if result.status == "confirmed":
        row.status = "verified"
        row.verified = True
        row.verified_at = _utcnow()
    else:
        row.status = "failed"
        row.verified = False
    db.session.commit()
    return row
