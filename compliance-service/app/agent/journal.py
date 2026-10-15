"""Append-only, hash-chained journal of everything the agent and the owner do.

Each entry's hash covers its own content plus the previous entry's hash,
per project. Editing or deleting any earlier row changes its hash and
breaks every later link, which verify_chain() reports. The ORM layer also
refuses UPDATE/DELETE on journal rows, so tampering has to bypass the
application (and is then detectable).
"""

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.agent.models import AgentAuditEntry
from app.extensions import db

GENESIS_HASH = "0" * 64


class JournalTamperError(Exception):
    pass


def _ts(dt: datetime) -> str:
    if dt.tzinfo is None:  # sqlite drops tzinfo; values are always written in UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_hash(project_id, seq, occurred_at, actor, event_type, case_public_id, payload, prev_hash) -> str:
    body = _canonical({
        "project": project_id, "seq": seq, "at": _ts(occurred_at), "actor": actor,
        "event": event_type, "case": case_public_id, "payload": payload, "prev": prev_hash,
    })
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def append(project_id: int, actor: str, event_type: str, payload: dict, case_public_id: str | None = None) -> AgentAuditEntry:
    """Appends one entry and commits. payload must be JSON-native (convert
    Decimal/datetime to str first) so the stored value hashes identically
    when read back."""
    for _attempt in range(3):
        last = (
            AgentAuditEntry.query.filter_by(developer_project_id=project_id)
            .order_by(AgentAuditEntry.seq.desc())
            .with_for_update()
            .first()
        )
        seq = 1 if last is None else last.seq + 1
        prev_hash = GENESIS_HASH if last is None else last.entry_hash
        now = datetime.now(timezone.utc)
        entry = AgentAuditEntry(
            developer_project_id=project_id, seq=seq, occurred_at=now, actor=actor,
            event_type=event_type, case_public_id=case_public_id, payload=payload,
            prev_hash=prev_hash,
            entry_hash=compute_hash(project_id, seq, now, actor, event_type, case_public_id, payload, prev_hash),
        )
        db.session.add(entry)
        try:
            db.session.commit()
            return entry
        except IntegrityError:  # concurrent writer took this seq; retry on the new tail
            db.session.rollback()
    raise RuntimeError("could not append journal entry after retries")


def verify_chain(project_id: int) -> tuple[bool, int | None]:
    """Returns (True, None) if intact, else (False, seq_of_first_bad_entry)."""
    prev_hash = GENESIS_HASH
    expected_seq = 1
    rows = AgentAuditEntry.query.filter_by(developer_project_id=project_id).order_by(AgentAuditEntry.seq).all()
    for row in rows:
        recomputed = compute_hash(
            project_id, row.seq, row.occurred_at, row.actor, row.event_type,
            row.case_public_id, row.payload, row.prev_hash,
        )
        if row.seq != expected_seq or row.prev_hash != prev_hash or row.entry_hash != recomputed:
            return False, row.seq
        prev_hash = row.entry_hash
        expected_seq += 1
    return True, None


@event.listens_for(AgentAuditEntry, "before_update")
def _forbid_update(mapper, connection, target):
    raise JournalTamperError("agent journal entries are append-only")


@event.listens_for(AgentAuditEntry, "before_delete")
def _forbid_delete(mapper, connection, target):
    raise JournalTamperError("agent journal entries are append-only")
