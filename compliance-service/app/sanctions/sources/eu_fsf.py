"""EU Financial Sanctions Files (FSF) source: fetch the EU Consolidated
Financial Sanctions List XML, parse it into the common normalized schema.

Field names verified against OpenSanctions' actual production crawler
(github.com/opensanctions/opensanctions, zavod/zavod/shed/fsf.py and
datasets/eu/fsf/crawler.py) rather than guessed -- a live fetch from
webgate.ec.europa.eu was not reachable to inspect a real file directly from
this dev environment. Unlike OFAC's SDN.XML (data mostly in child-element
text), the EU FSF schema carries most fields as XML ATTRIBUTES on container
elements (nameAlias, birthdate, citizenship, identification, address,
regulation) -- this is a real structural difference, not an inconsistency.

Two things remain unverified against a real downloaded file and should be
checked before relying on this in production:
  1. Exact subjectType/@code values -- "P"/"E" assumed for person/entity.
  2. Which nameAlias entry counts as the "primary" name vs an aka -- this
     implementation takes the first nameAlias as primary and treats the
     rest as aliases, which is a reasonable default but not confirmed.
"""

import xml.etree.ElementTree as etree

import requests

from app.sanctions.sources.base import NormalizedRecord, SanctionsSource

DOWNLOAD_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"

_SUBJECT_TYPE_MAP = {
    "p": "person",
    "person": "person",
    "e": "legal_entity",
    "entity": "legal_entity",
}

_LEI_ID_TYPES = {"legal entity identifier (lei)", "lei"}


def _name_from_alias(alias) -> str | None:
    whole = alias.get("wholeName")
    if whole:
        return whole.strip()
    parts = [alias.get("firstName"), alias.get("middleName"), alias.get("lastName")]
    parts = [p.strip() for p in parts if p and p.strip()]
    return " ".join(parts) if parts else None


class EUFSFSource(SanctionsSource):
    name = "EU_FSF"
    source_url = DOWNLOAD_URL

    def fetch(self) -> bytes:
        response = requests.get(self.source_url, timeout=60)
        response.raise_for_status()
        return response.content

    def parse(self, raw: bytes):
        root = etree.fromstring(raw)

        for entry in root.iter("sanctionEntity"):
            yield self._parse_entry(entry)

    def _parse_entry(self, entry) -> NormalizedRecord:
        logical_id = entry.get("logicalId") or ""

        subject_type_elem = entry.find("subjectType")
        code = (subject_type_elem.get("code") if subject_type_elem is not None else "") or ""
        entity_type = _SUBJECT_TYPE_MAP.get(code.strip().lower(), "legal_entity")

        aliases_elems = entry.findall("nameAlias")
        names = [n for a in aliases_elems if (n := _name_from_alias(a))]
        primary_name = names[0] if names else ""
        aliases = names[1:]

        birthdate_elem = entry.find("birthdate")
        date_of_birth = birthdate_elem.get("birthdate") if birthdate_elem is not None else None

        citizenship_elem = entry.find("citizenship")
        nationality = citizenship_elem.get("countryDescription") if citizenship_elem is not None else None

        national_ids = []
        lei = None
        for id_elem in entry.findall("identification"):
            id_type = id_elem.get("identificationTypeDescription")
            id_number = id_elem.get("number")
            if not id_number:
                continue
            national_ids.append({"type": id_type, "value": id_number})
            if id_type and id_type.strip().lower() in _LEI_ID_TYPES:
                lei = id_number

        addresses = []
        for addr_elem in entry.findall("address"):
            addresses.append({
                "city": addr_elem.get("city"),
                "country": addr_elem.get("countryDescription"),
            })
        country_of_residence = addresses[0]["country"] if addresses else None

        programs = []
        for reg_elem in entry.findall("regulation"):
            programme = reg_elem.get("programme") or reg_elem.get("numberTitle")
            if programme:
                programs.append(programme)

        remark_elem = entry.find("remark")
        place_of_birth = None  # EU FSF doesn't carry a separate place-of-birth field the way OFAC does

        return NormalizedRecord(
            source=self.name,
            source_entity_id=logical_id,
            entity_type=entity_type,
            primary_name=primary_name,
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
                "logicalId": logical_id,
                "euReferenceNumber": entry.get("euReferenceNumber"),
                "subjectTypeCode": code,
                "remark": remark_elem.text if remark_elem is not None else None,
            },
        )
