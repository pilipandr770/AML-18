from app.ageverify.adapters import get_adapter, hash_proof_token
from app.ageverify.models import AgeVerification
from app.extensions import db


def verify_and_persist(subject_reference: str, proof_token: str, adapter_name: str, min_age: int, config) -> AgeVerification:
    adapter = get_adapter(adapter_name, config=config)
    result = adapter.verify(proof_token=proof_token, min_age=min_age)

    row = AgeVerification(
        subject_reference=subject_reference,
        adapter=adapter_name,
        verified=result.verified,
        method=result.method,
        proof_token_hash=hash_proof_token(proof_token),
        verified_at=result.verified_at,
        expires_at=result.expires_at,
    )
    db.session.add(row)
    db.session.commit()
    return row