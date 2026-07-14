"""Sanctions ingestion pipeline: fetch -> hash -> stage -> swap-in.

Deliberately a full reload-and-swap per source, not incremental diffing:
at tens-of-thousands-of-rows scale (OFAC + EU combined) this is fast and
far simpler to reason about, and ListSnapshot is the audit-of-record for
each refresh. Revisit only if reload time becomes an actual problem.
"""

import hashlib
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.sanctions.models import EntityNameIndex, ListSnapshot, SanctionedEntity
from app.sanctions.normalize import name_variants
from app.sanctions.sources.eu_fsf import EUFSFSource
from app.sanctions.sources.ofac_sdn import OFACSDNSource

logger = logging.getLogger(__name__)

REGISTERED_SOURCES = [OFACSDNSource, EUFSFSource]


def ingest_source(source) -> ListSnapshot:
    raw = source.fetch()
    content_hash = hashlib.sha256(raw).hexdigest()

    existing_active = ListSnapshot.query.filter_by(
        source=source.name, content_hash=content_hash, status="active"
    ).first()
    if existing_active:
        logger.info("sanctions source %s unchanged (hash match), skipping reload", source.name)
        return existing_active

    snapshot = ListSnapshot(
        source=source.name,
        source_url=source.source_url,
        content_hash=content_hash,
        status="staged",
    )
    db.session.add(snapshot)
    db.session.flush()

    record_count = 0
    try:
        for record in source.parse(raw):
            entity = SanctionedEntity(
                list_snapshot_id=snapshot.id,
                source=record.source,
                source_entity_id=record.source_entity_id,
                entity_type=record.entity_type,
                primary_name=record.primary_name,
                date_of_birth=record.date_of_birth,
                place_of_birth=record.place_of_birth,
                nationality=record.nationality,
                country_of_residence=record.country_of_residence,
                national_ids=record.national_ids,
                addresses=record.addresses,
                programs=record.programs,
                lei=record.lei,
                raw_record=record.raw_record,
            )
            db.session.add(entity)
            db.session.flush()

            for variant in name_variants(record):
                db.session.add(EntityNameIndex(
                    entity_id=entity.id,
                    name_text=variant["name_text"],
                    name_normalized=variant["name_text"].lower(),
                    phonetic_key=variant["phonetic_key"],
                    name_type=variant["name_type"],
                ))

            record_count += 1
    except Exception as exc:
        db.session.rollback()
        snapshot = ListSnapshot(
            source=source.name,
            source_url=source.source_url,
            content_hash=content_hash,
            status="failed",
            error_detail=str(exc),
        )
        db.session.add(snapshot)
        db.session.commit()
        logger.error("sanctions ingestion failed for %s: %s", source.name, exc)
        raise

    snapshot.record_count = record_count

    previous = ListSnapshot.query.filter_by(source=source.name, status="active").all()
    for prev in previous:
        prev.status = "superseded"
        for entity in prev.entities:
            entity.is_active = False

    snapshot.status = "active"
    snapshot.activated_at = datetime.now(timezone.utc)

    db.session.commit()
    logger.info("ingested %d records for %s (snapshot %d)", record_count, source.name, snapshot.id)
    return snapshot


def ingest_all() -> list:
    return [ingest_source(source_cls()) for source_cls in REGISTERED_SOURCES]
