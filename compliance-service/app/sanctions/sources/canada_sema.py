"""Canada consolidated autonomous sanctions (SEMA) source.

Global Affairs Canada publishes the "Consolidated Canadian Autonomous
Sanctions List" as one XML file (root ``data-set``, one flat ``<record>`` per
listed person / entity / vessel). Structure verified against a real download:

  * element names are bilingual ("LastName-NomDeFamille", ...); only the part
    before the first "-" (the English name) is used here;
  * persons carry LastName + GivenName, entities and vessels carry
    EntityOrShip (vessels additionally ShipIMONumber / TitleOrShipType);
  * ``Aliases-Alias`` is ONE comma-separated string, sometimes with
    "Belarusian:" / "Russian:" script labels;
  * the item number is only unique within (country, schedule), so the stable
    id is built from all three;
  * data quirk: for some persons the ShipIMONumber element holds a non-Latin
    alias instead of a number -- non-numeric values are treated as aliases.

The related Justice for Victims of Corrupt Foreign Officials Act list has no
separate machine-readable file linked from the Global Affairs Canada site
(only the SEMA XML is), so it is not a separate source here.
"""

import re

import requests
from defusedxml import ElementTree as etree  # untrusted XML: no entity expansion

from app.sanctions.sources.base import NormalizedRecord, SanctionsSource

DOWNLOAD_URL = (
    "https://www.international.gc.ca/world-monde/assets/office_docs/"
    "international_relations-relations_internationales/sanctions/sema-lmes.xml"
)

_MAX = 256
_LANG_PREFIX = re.compile(
    r"^\s*(?:belarusian|russian|ukrainian|arabic|persian|farsi|chinese|burmese|"
    r"korean|cyrillic|original script)\s*:\s*",
    re.I,
)
_LEGAL_SUFFIXES = {
    "ltd", "limited", "llc", "inc", "co", "corp", "corporation", "jsc", "ojsc",
    "pjsc", "cjsc", "llp", "lp", "plc", "gmbh", "ag", "sa", "bv", "nv", "ooo",
    "ao", "oao", "zao", "pao", "fze", "fzc", "fzco", "pte", "pvt", "sdn bhd",
}


def _text(record) -> dict:
    out = {}
    for child in record:
        key = child.tag.split("-")[0]
        value = (child.text or "").replace("\xa0", " ").strip()
        if value and key not in out:
            out[key] = value
    return out


def _clip(value):
    return value[:_MAX] if value else None


def _split_aliases(raw: str, is_entity: bool) -> list:
    parts = [p.strip() for p in re.split(r"[;\n]|,", raw)]
    merged = []
    for part in parts:
        if not part:
            continue
        if is_entity and merged and part.lower().strip(". ") in _LEGAL_SUFFIXES:
            merged[-1] = f"{merged[-1]}, {part}"
        else:
            merged.append(part)
    return [m for m in (_LANG_PREFIX.sub("", p).strip() for p in merged) if m]


class CanadaSEMASource(SanctionsSource):
    name = "CA_SEMA"
    source_url = DOWNLOAD_URL

    def fetch(self) -> bytes:
        response = requests.get(
            self.source_url,
            timeout=180,
            headers={"User-Agent": "Mozilla/5.0 (AML18 sanctions fetch)"},
        )
        response.raise_for_status()
        return response.content

    def parse(self, raw: bytes):
        root = etree.fromstring(raw)
        for record in root.iter("record"):
            parsed = self._parse_record(record)
            if parsed is not None:
                yield parsed

    def _parse_record(self, record):
        d = _text(record)
        entity_field = d.get("EntityOrShip")
        is_entity = bool(entity_field)

        if is_entity:
            primary = entity_field
        else:
            primary = " ".join(p for p in (d.get("GivenName"), d.get("LastName")) if p)
        primary = (primary or "").strip()
        if not primary:
            return None

        imo_raw = d.get("ShipIMONumber", "")
        imo = imo_raw if imo_raw.isdigit() else None
        is_ship = bool(imo) or (is_entity and bool(d.get("TitleOrShipType")))

        aliases = _split_aliases(d.get("Aliases", ""), is_entity)
        if imo_raw and not imo:  # quirk: alias text stored in the IMO element
            aliases.append(imo_raw)
        seen = {primary.lower()}
        unique = []
        for alias in aliases:
            alias = alias[:_MAX]
            if alias.lower() not in seen:
                seen.add(alias.lower())
                unique.append(alias)

        country = d.get("Country", "")
        country_en = country.split(" / ")[0].strip()
        schedule = d.get("Schedule", "")
        item = d.get("Item", "")
        entity_id = "|".join([country_en, schedule, item])

        program = f"SEMA - {country_en}" if country_en else "SEMA"
        if schedule:
            program += f" (Schedule {schedule})"

        dob_raw = d.get("DateOfBirthOrShipBuildDate")
        return NormalizedRecord(
            source=self.name,
            source_entity_id=entity_id,
            entity_type="legal_entity" if is_entity else "person",
            primary_name=primary[:_MAX],
            aliases=unique,
            date_of_birth=None if is_entity else _clip(dob_raw),
            national_ids=[{"type": "IMO Number", "value": imo}] if imo else [],
            programs=[program],
            raw_record={
                "country": country,
                "schedule": schedule,
                "item": item,
                "date_of_listing": d.get("DateOfListing"),
                "ship_type": d.get("TitleOrShipType") if is_ship else None,
                "build_date": dob_raw if is_entity else None,
            },
        )
