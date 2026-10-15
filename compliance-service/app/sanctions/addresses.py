"""Cryptocurrency-address handling for sanctions lists: normalization,
extraction of listed addresses from source records, and exact-match lookup.

Matching is exact on purpose. A sanctioned address is a hard identifier --
there is no meaningful "fuzzy" match for an address -- so any hit is
reported as such and always goes to a human in the agent."""

import re

from app.extensions import db
from app.sanctions.models import ListSnapshot, SanctionedAddress, SanctionedEntity

_OFAC_ID = re.compile(r"^\s*digital currency address\s*-\s*([A-Za-z0-9._]+)\s*$", re.I)
_EVM = re.compile(r"^0x[0-9a-fA-F]{40}$")


def normalize_address(address: str) -> str:
    """EVM addresses are case-insensitive (checksum casing is cosmetic), so
    they are lowercased; every other chain's encoding is case-sensitive and
    is only whitespace-trimmed."""
    value = (address or "").strip()
    return value.lower() if _EVM.match(value) else value


def addresses_from_national_ids(national_ids: list | None) -> list[dict]:
    """OFAC lists crypto addresses as ids typed "Digital Currency Address - XBT"."""
    found = []
    for item in national_ids or []:
        m = _OFAC_ID.match(item.get("type") or "")
        if m and item.get("value"):
            found.append({"currency": m.group(1).upper(), "address": item["value"].strip()})
    return found


def match_address(address: str) -> list[dict]:
    """Exact match against addresses of ACTIVE entities in ACTIVE snapshots."""
    normalized = normalize_address(address)
    if not normalized:
        return []
    rows = (
        db.session.query(SanctionedAddress, SanctionedEntity)
        .join(SanctionedEntity, SanctionedAddress.entity_id == SanctionedEntity.id)
        .join(ListSnapshot, SanctionedEntity.list_snapshot_id == ListSnapshot.id)
        .filter(
            SanctionedAddress.address_normalized == normalized,
            SanctionedEntity.is_active.is_(True),
            ListSnapshot.status == "active",
        )
        .all()
    )
    return [
        {
            "entity_id": entity.id,
            "sanctioned_name": entity.primary_name,
            "source": entity.source,
            "source_entity_id": entity.source_entity_id,
            "currency": addr.currency,
            "address": addr.address,
            "programs": entity.programs or [],
        }
        for addr, entity in rows
    ]
