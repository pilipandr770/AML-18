from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class ListSnapshot(db.Model):
    """Audit-of-record for each sanctions list refresh. Every SanctionedEntity
    row points back to the snapshot it was loaded from, so a screening
    decision can always cite exactly which list version produced a hit."""

    __tablename__ = "list_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(32), nullable=False)  # "OFAC_SDN" | "EU_FSF" | "UN_CONSOLIDATED"
    source_url = db.Column(db.String(512), nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    content_hash = db.Column(db.String(64), nullable=False)  # sha256 hex of the raw fetched file
    record_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="staged")  # staged | active | failed
    error_detail = db.Column(db.Text, nullable=True)
    activated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    entities = db.relationship("SanctionedEntity", back_populates="list_snapshot")


class SanctionedEntity(db.Model):
    __tablename__ = "sanctioned_entities"

    id = db.Column(db.Integer, primary_key=True)
    list_snapshot_id = db.Column(db.Integer, db.ForeignKey("list_snapshots.id"), nullable=False)
    source = db.Column(db.String(32), nullable=False)
    source_entity_id = db.Column(db.String(128), nullable=False)  # the source's own record ID
    entity_type = db.Column(db.String(16), nullable=False)  # "person" | "legal_entity"
    primary_name = db.Column(db.String(256), nullable=False)
    date_of_birth = db.Column(db.String(32), nullable=True)  # kept as string: sources give partial/fuzzy DOBs
    place_of_birth = db.Column(db.String(256), nullable=True)
    nationality = db.Column(db.String(4), nullable=True)  # ISO 3166-1 alpha-2 where known
    country_of_residence = db.Column(db.String(4), nullable=True)
    national_ids = db.Column(db.JSON, nullable=True)  # [{type, value}]
    addresses = db.Column(db.JSON, nullable=True)
    programs = db.Column(db.JSON, nullable=True)  # sanctions program tags, e.g. ["SDGT"]
    lei = db.Column(db.String(32), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    first_seen_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    raw_record = db.Column(db.JSON, nullable=True)  # the untouched source record, for audit

    list_snapshot = db.relationship("ListSnapshot", back_populates="entities")
    names = db.relationship("EntityNameIndex", back_populates="entity", cascade="all, delete-orphan")


class EntityNameIndex(db.Model):
    """The actual searchable table. SQLite can't index JSON columns, so every
    name variant (primary name + akas + transliterations) gets its own row
    here with a precomputed phonetic key for fast blocking at query time."""

    __tablename__ = "entity_name_index"

    id = db.Column(db.Integer, primary_key=True)
    entity_id = db.Column(db.Integer, db.ForeignKey("sanctioned_entities.id"), nullable=False)
    name_text = db.Column(db.String(256), nullable=False)
    name_normalized = db.Column(db.String(256), nullable=False, index=True)
    phonetic_key = db.Column(db.String(64), nullable=False, index=True)
    name_type = db.Column(db.String(16), nullable=False, default="primary")  # primary | aka | transliteration

    entity = db.relationship("SanctionedEntity", back_populates="names")
