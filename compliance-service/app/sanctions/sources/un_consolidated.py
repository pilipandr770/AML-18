"""UN Security Council Consolidated List source.

Structure verified against the real file: CONSOLIDATED_LIST/INDIVIDUALS/
INDIVIDUAL and CONSOLIDATED_LIST/ENTITIES/ENTITY. Names are split into
FIRST_NAME..FOURTH_NAME (for entities FIRST_NAME holds the whole name);
aliases are INDIVIDUAL_ALIAS/ENTITY_ALIAS with a QUALITY (Good/Low/a.k.a./
f.k.a.) -- all non-empty alias names are kept. Empty placeholder elements
(e.g. <ALIAS_NAME/>) are common and ignored. The list has no LEI and no
structured crypto addresses.
"""

import requests
from defusedxml import ElementTree as ET  # untrusted XML from the internet

from app.sanctions.sources.base import NormalizedRecord, SanctionsSource

DOWNLOAD_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"

_MAX = 256


def _text(elem, name: str) -> str | None:
    child = elem.find(name)
    if child is None:
        return None
    return " ".join((child.text or "").split()) or None


def _values(elem, name: str) -> list[str]:
    """Texts of <name><VALUE>..</VALUE>...</name> wrappers (NATIONALITY etc.)."""
    out = []
    for wrapper in elem.findall(name):
        for v in wrapper.findall("VALUE"):
            t = " ".join((v.text or "").split())
            if t:
                out.append(t)
    return out


def _join(*parts) -> str:
    return ", ".join(p for p in parts if p)


def _dob(item) -> str | None:
    exact = _text(item, "DATE")
    if exact:
        return exact
    year = _text(item, "YEAR")
    if year:
        return year
    frm, to = _text(item, "FROM_YEAR"), _text(item, "TO_YEAR")
    if frm and to:
        return f"{frm} to {to}"
    return frm or to


class UNConsolidatedSource(SanctionsSource):
    name = "UN_CONSOLIDATED"
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
        root = ET.fromstring(raw)
        for tag, etype in (("INDIVIDUALS/INDIVIDUAL", "person"), ("ENTITIES/ENTITY", "legal_entity")):
            for entry in root.findall(tag):
                record = self._parse_entry(entry, etype)
                if record is not None:
                    yield record

    def _parse_entry(self, entry, entity_type: str):
        prefix = "INDIVIDUAL" if entity_type == "person" else "ENTITY"
        data_id = _text(entry, "DATAID")
        name_parts = (_text(entry, n) for n in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME"))
        name = " ".join(p for p in name_parts if p)[:_MAX]
        if not data_id or not name:
            return None

        aliases = []
        for alias in entry.findall(f"{prefix}_ALIAS"):
            alias_name = _text(alias, "ALIAS_NAME")
            if alias_name and alias_name != name and alias_name not in aliases:
                aliases.append(alias_name)
        original = _text(entry, "NAME_ORIGINAL_SCRIPT")
        if original and original not in aliases:
            aliases.append(original)

        # Several DOBs / nationalities can be listed; the first usable one is kept.
        date_of_birth = None
        for item in entry.findall(f"{prefix}_DATE_OF_BIRTH"):
            date_of_birth = _dob(item)
            if date_of_birth:
                break

        place_of_birth = None
        for item in entry.findall(f"{prefix}_PLACE_OF_BIRTH"):
            place_of_birth = _join(
                _text(item, "CITY"), _text(item, "STATE_PROVINCE"), _text(item, "COUNTRY")
            ) or None
            if place_of_birth:
                break

        nationalities = _values(entry, "NATIONALITY")
        nationality = nationalities[0][:_MAX] if nationalities else None

        national_ids = []
        for doc in entry.findall(f"{prefix}_DOCUMENT"):
            number = _text(doc, "NUMBER")
            if number:
                national_ids.append({"type": _text(doc, "TYPE_OF_DOCUMENT"), "value": number})

        addresses = []
        for addr in entry.findall(f"{prefix}_ADDRESS"):
            city, country = _text(addr, "CITY"), _text(addr, "COUNTRY")
            if city or country:
                addresses.append({"city": city, "country": country})
        residence = next((a["country"] for a in addresses if a["country"]), None)

        list_type = _text(entry, "UN_LIST_TYPE")
        programs = [list_type] if list_type else []

        return NormalizedRecord(
            source=self.name,
            source_entity_id=data_id,
            entity_type=entity_type,
            primary_name=name,
            aliases=aliases,
            date_of_birth=date_of_birth,
            place_of_birth=place_of_birth[:_MAX] if place_of_birth else None,
            nationality=nationality,
            country_of_residence=residence[:_MAX] if residence else None,
            national_ids=national_ids,
            addresses=addresses,
            programs=programs,
            raw_record={
                "dataid": data_id,
                "reference_number": _text(entry, "REFERENCE_NUMBER"),
                "un_list_type": list_type,
                "listed_on": _text(entry, "LISTED_ON"),
            },
        )
