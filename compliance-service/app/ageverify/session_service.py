from datetime import datetime, timezone

from app.ageverify.adapters import AdapterError, AdapterNotConfiguredError, get_adapter
from app.ageverify.models import AgeVerification, AgeVerificationSession
from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


def create_session(
    subject_reference: str, adapter_name: str, min_age: int, config, developer_project_id: int
) -> AgeVerificationSession:
    adapter = get_adapter(adapter_name, config=config)
    if not adapter.supports_sessions:
        raise AdapterError(f"adapter {adapter_name} does not support interactive sessions")

    started = adapter.start_session(min_age=min_age)
    row = AgeVerificationSession(
        developer_project_id=developer_project_id,
        subject_reference=subject_reference,
        adapter=adapter_name,
        min_age=min_age,
        status="pending",
        external_transaction_id=started.transaction_id,
        request_value=started.request_value,
    )
    db.session.add(row)
    db.session.commit()
    return row


def refresh_session(public_id: str, config, developer_project_id: int | None = None) -> AgeVerificationSession | None:
    query = AgeVerificationSession.query.filter_by(public_id=public_id)
    if developer_project_id is not None:
        query = query.filter_by(developer_project_id=developer_project_id)
    row = query.first()
    if row is None:
        return None

    if row.status != "pending":
        return row

    adapter = get_adapter(row.adapter, config=config)
    try:
        result = adapter.get_session_result(transaction_id=row.external_transaction_id, min_age=row.min_age)
    except AdapterNotConfiguredError:
        raise
    except AdapterError as exc:
        row.status = "failed"
        row.last_error = str(exc)
        row.completed_at = _utcnow()
        db.session.commit()
        return row

    if result.status == "pending":
        return row

    if result.status != "complete" or result.verified is None:
        row.status = "failed"
        row.last_error = result.error or "unknown age verification session state"
        row.completed_at = _utcnow()
        db.session.commit()
        return row

    verification = AgeVerification(
        developer_project_id=row.developer_project_id,
        subject_reference=row.subject_reference,
        adapter=row.adapter,
        verified=result.verified,
        method=result.method,
        proof_token_hash=result.proof_token_hash,
        verified_at=_utcnow() if result.verified else None,
    )
    db.session.add(verification)
    db.session.flush()

    row.verification_id = verification.id
    row.status = "verified" if result.verified else "rejected"
    row.completed_at = _utcnow()
    db.session.commit()
    return row