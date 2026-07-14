"""OFAC SDN.XML source: fetch from the Treasury Sanctions List Service,
parse the legacy/classic SDN schema (sdnEntry/akaList/idList/programList/
addressList/dateOfBirthList/placeOfBirthList/nationalityList).

Deliberately targets the classic SDN.XML schema rather than the newer
"Advanced" schema (SDN_ADVANCED.XML): the Advanced schema uses a much more
elaborate generic sanctions-data model (DistinctParty/Feature/Identity)
shared across many list types, while classic SDN.XML is simpler, has been
stable for years, and is still officially published. OFAC changed the XML
namespace in 2024 (tempuri.org -> sanctionslistservice.ofac.treas.gov) --
parsing is namespace-agnostic (tag names are matched by local name only) so
a future namespace change doesn't silently break ingestion.
"""

import xml.etree.ElementTree as ET

import requests

from app.sanctions.sources.base import NormalizedRecord, SanctionsSource

DOWNLOAD_URL = "https://sanctionslistservice.ofac.treas.gov/api/download/sdn.xml"

_ENTITY_TYPE_MAP = {
    "individual": "person",
    "entity": "legal_entity",
    "vessel": "legal_entity",
    "aircraft": "legal_entity",
}

_LEI_ID_TYPES = {"legal entity identifier (lei)", "lei"}


def _local(tag: str) -> str:
    """Strips a namespace prefix ('{uri}tag' -> 'tag') so parsing doesn't
    depend on matching OFAC's exact namespace URI, which has changed before."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _child_text(elem, name: str) -> str | None:
    for child in elem:
        if _local(child.tag) == name:
            return (child.text or "").strip() or None
    return None


def _children(elem, name: str):
    return [c for c in elem if _local(c.tag) == name]


def _full_name(last_name: str | None, first_name: str | None) -> str:
    parts = [p for p in (first_name, last_name) if p]
    return " ".join(parts)


class OFACSDNSource(SanctionsSource):
    name = "OFAC_SDN"
    source_url = DOWNLOAD_URL

    def fetch(self) -> bytes:
        response = requests.get(self.source_url, timeout=60)
        response.raise_for_status()
        return response.content

    def parse(self, raw: bytes):
        root = ET.fromstring(raw)

        for entry in root:
            if _local(entry.tag) != "sdnEntry":
                continue
            yield self._parse_entry(entry)

    def _parse_entry(self, entry) -> NormalizedRecord:
        uid = _child_text(entry, "uid") or ""
        last_name = _child_text(entry, "lastName")
        first_name = _child_text(entry, "firstName")
        sdn_type = (_child_text(entry, "sdnType") or "").lower()
        entity_type = _ENTITY_TYPE_MAP.get(sdn_type, "legal_entity")

        aliases = []
        for aka_list in _children(entry, "akaList"):
            for aka in _children(aka_list, "aka"):
                alias_name = _full_name(
                    _child_text(aka, "lastName"), _child_text(aka, "firstName")
                )
                if alias_name:
                    aliases.append(alias_name)

        programs = []
        for program_list in _children(entry, "programList"):
            for program in _children(program_list, "program"):
                if program.text and program.text.strip():
                    programs.append(program.text.strip())

        date_of_birth = None
        for dob_list in _children(entry, "dateOfBirthList"):
            for item in _children(dob_list, "dateOfBirthItem"):
                date_of_birth = _child_text(item, "dateOfBirth") or date_of_birth

        place_of_birth = None
        for pob_list in _children(entry, "placeOfBirthList"):
            for item in _children(pob_list, "placeOfBirthItem"):
                place_of_birth = _child_text(item, "placeOfBirth") or place_of_birth

        nationality = None
        for nat_list in _children(entry, "nationalityList"):
            for item in _children(nat_list, "nationality"):
                nationality = _child_text(item, "country") or nationality
        if nationality is None:
            for cit_list in _children(entry, "citizenshipList"):
                for item in _children(cit_list, "citizenship"):
                    nationality = _child_text(item, "country") or nationality

        national_ids = []
        lei = None
        for id_list in _children(entry, "idList"):
            for id_item in _children(id_list, "id"):
                id_type = _child_text(id_item, "idType")
                id_number = _child_text(id_item, "idNumber")
                if not id_number:
                    continue
                national_ids.append({"type": id_type, "value": id_number})
                if id_type and id_type.strip().lower() in _LEI_ID_TYPES:
                    lei = id_number

        addresses = []
        for address_list in _children(entry, "addressList"):
            for address in _children(address_list, "address"):
                addresses.append({
                    "city": _child_text(address, "city"),
                    "country": _child_text(address, "country"),
                })

        country_of_residence = addresses[0]["country"] if addresses else None

        return NormalizedRecord(
            source=self.name,
            source_entity_id=uid,
            entity_type=entity_type,
            primary_name=_full_name(last_name, first_name),
            aliases=aliases,
            date_of_birth=date_of_birth,
            place_of_birth=place_of_birth,
            nationality=nationality,
            country_of_residence=country_of_residence,
            national_ids=national_ids,
            addresses=addresses,
            programs=programs,
            lei=lei,
            raw_record={
                "uid": uid,
                "lastName": last_name,
                "firstName": first_name,
                "sdnType": sdn_type,
            },
        )
