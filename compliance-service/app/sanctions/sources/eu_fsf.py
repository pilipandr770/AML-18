"""EU Financial Sanctions Files (FSF) source: fetch the EU Consolidated
Financial Sanctions List XML, parse it into the common normalized schema.

Verified against a real downloaded file (generationDate 2026-10-12, 6,233
sanctionEntity records, ~26 MB). What the real structure looks like, and how
it is mapped:

* Namespace http://eu.europa.ec/fpi/fsd/export on every element; the
  sanctionEntity elements are direct children of <export> (no wrapper list).
  Tags are matched namespace-agnostically ("{*}tag").
* Most data is carried as XML ATTRIBUTES on child elements of sanctionEntity
  (nameAlias, birthdate, citizenship, identification, address, regulation),
  plus a <remark> text child.
* subjectType/@code is "person" or "enterprise" (classificationCode "P"/"E"
  is the fallback). Enterprises include vessels (IMO identification type).
* nameAlias: EVERY alias in the file has strong="true", so "strong" cannot
  distinguish primary from aka. Rule used: the primary name is the first
  nameAlias in document order that yields a name (the EU lists the main
  designation first), preferring strong="true" and Latin-script names (1,573
  entities list a non-Latin name first, all of them also have a Latin alias).
  All other distinct names become aliases. wholeName is
  used if present, else firstName/middleName/lastName joined.
* birthdate: an entity may have several. Attributes: birthdate (full ISO
  date), or year/monthOfYear/dayOfMonth, or yearRangeFrom/yearRangeTo, plus
  city/place/countryDescription. The single date_of_birth field gets the
  first full date (else the first partial one, "YYYY-MM", "YYYY" or
  "YYYY/YYYY"); every birthdate is kept in raw_record["birthdates"].
* citizenship/@countryDescription -> nationality (first one; all in raw_record).
* identification: identificationTypeCode/identificationTypeDescription/number.
  There is NO dedicated LEI type in the list; LEIs appear under "regnumber"
  or "other", so an LEI is detected by ISO 17442 shape + mod-97 checksum on
  any identification number. No crypto-address identification types exist.
* regulation: programme (e.g. "UKR", "IRN") with numberTitle as fallback.
"""

import io

from defusedxml import ElementTree as etree  # untrusted XML from the internet: no entity expansion

import requests

from app.sanctions.sources.base import NormalizedRecord, SanctionsSource

# The EU's published public access token for this open dataset (the token-less
# URL returns HTTP 403). Not a secret; override via EUFSFSource.token if the
# EU rotates it.
PUBLIC_TOKEN = "dG9rZW4tMjAxNw"
BASE_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
DOWNLOAD_URL = f"{BASE_URL}?token={PUBLIC_TOKEN}"

_SUBJECT_TYPE_MAP = {
    "person": "person",
    "p": "person",
    "enterprise": "legal_entity",
    "e": "legal_entity",
    "entity": "legal_entity",
}

_UNKNOWN_COUNTRIES = {"", "unknown"}


def _is_lei(value: str) -> bool:
    """ISO 17442: 18 alphanumerics + 2 check digits, ISO 7064 mod 97-10."""
    v = value.strip().upper()
    if len(v) != 20 or not v.isalnum() or not v[18:].isdigit():
        return False
    return int("".join(str(int(c, 36)) for c in v)) % 97 == 1


def _has_latin(name: str) -> bool:
    return any(c.isascii() and c.isalpha() for c in name)


def _clean(value) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _name_from_alias(alias) -> str | None:
    whole = _clean(alias.get("wholeName"))
    if whole:
        return whole
    parts = [_clean(alias.get(k)) for k in ("firstName", "middleName", "lastName")]
    parts = [p for p in parts if p]
    return " ".join(parts) if parts else None


def _country(elem) -> str | None:
    c = _clean(elem.get("countryDescription"))
    return None if c is None or c.lower() in _UNKNOWN_COUNTRIES else c


def _birthdate_value(b) -> str | None:
    full = _clean(b.get("birthdate"))
    if full:
        return full
    year = _clean(b.get("year"))
    if year:
        month = _clean(b.get("monthOfYear"))
        return f"{year}-{int(month):02d}" if month and month.isdigit() else year
    lo, hi = _clean(b.get("yearRangeFrom")), _clean(b.get("yearRangeTo"))
    if lo and hi:
        return f"{lo}/{hi}"
    return lo or hi


class EUFSFSource(SanctionsSource):
    name = "EU_FSF"
    token = PUBLIC_TOKEN  # overridable on the class or the instance
    source_url = DOWNLOAD_URL

    def __init__(self, token: str | None = None):
        if token is not None:
            self.token = token
        self.source_url = f"{BASE_URL}?token={self.token}"

    def fetch(self) -> bytes:
        response = requests.get(
            self.source_url,
            timeout=180,
            headers={"User-Agent": "Mozilla/5.0 (AML18 sanctions fetch)"},
        )
        response.raise_for_status()
        return response.content

    def parse(self, raw: bytes):
        # iterparse + clear() keeps memory flat on the ~26 MB file.
        for _event, elem in etree.iterparse(io.BytesIO(raw), events=("end",)):
            if elem.tag.rpartition("}")[2] == "sanctionEntity":
                yield self._parse_entry(elem)
                elem.clear()

    def _parse_entry(self, entry) -> NormalizedRecord:
        logical_id = entry.get("logicalId") or ""

        subject_type_elem = entry.find("{*}subjectType")
        code = ""
        entity_type = "legal_entity"
        if subject_type_elem is not None:
            code = subject_type_elem.get("code") or ""
            classification = subject_type_elem.get("classificationCode") or ""
            entity_type = (
                _SUBJECT_TYPE_MAP.get(code.strip().lower())
                or _SUBJECT_TYPE_MAP.get(classification.strip().lower())
                or "legal_entity"
            )

        # Primary name: first strong, Latin-script nameAlias; else first strong;
        # else first with a name (see module docstring).
        named = [(a, n) for a in entry.findall("{*}nameAlias") if (n := _name_from_alias(a))]
        primary_name = ""
        if named:
            strong = [n for a, n in named if (a.get("strong") or "").lower() == "true"] or [n for _a, n in named]
            primary_name = next((n for n in strong if _has_latin(n)), strong[0])
        aliases, seen = [], {primary_name.casefold()}
        for _a, n in named:
            if n.casefold() not in seen:
                seen.add(n.casefold())
                aliases.append(n)

        birthdates = []
        place_of_birth = None
        for b in entry.findall("{*}birthdate"):
            value = _birthdate_value(b)
            place = ", ".join(p for p in (_clean(b.get("city")), _clean(b.get("place")), _country(b)) if p) or None
            if value or place:
                birthdates.append({"date": value, "place": place, "circa": b.get("circa") == "true"})
            if place_of_birth is None:
                place_of_birth = place
        dated = [b["date"] for b in birthdates if b["date"]]
        date_of_birth = next((d for d in dated if len(d) == 10), dated[0] if dated else None)

        nationalities = [c for c in (_country(e) for e in entry.findall("{*}citizenship")) if c]
        nationality = nationalities[0] if nationalities else None

        national_ids = []
        lei = None
        for id_elem in entry.findall("{*}identification"):
            id_number = _clean(id_elem.get("number"))
            if not id_number:
                continue
            national_ids.append({
                "type": _clean(id_elem.get("identificationTypeDescription")) or _clean(id_elem.get("identificationTypeCode")),
                "value": id_number,
                "country": _country(id_elem),
            })
            if lei is None and _is_lei(id_number):
                lei = id_number.strip().upper()

        addresses = []
        for addr in entry.findall("{*}address"):
            item = {
                "street": _clean(addr.get("street")),
                "city": _clean(addr.get("city")),
                "zip": _clean(addr.get("zipCode")),
                "po_box": _clean(addr.get("poBox")),
                "region": _clean(addr.get("region")),
                "country": _country(addr),
            }
            if any(item.values()):
                addresses.append(item)
        country_of_residence = next((a["country"] for a in addresses if a["country"]), None)

        programs = []
        for reg in entry.findall("{*}regulation"):
            programme = _clean(reg.get("programme")) or _clean(reg.get("numberTitle"))
            if programme and programme not in programs:
                programs.append(programme)

        remark_elem = entry.find("{*}remark")
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
                "unitedNationId": _clean(entry.get("unitedNationId")),
                "subjectTypeCode": code,
                "birthdates": birthdates,
                "nationalities": nationalities,
                "remark": remark_elem.text if remark_elem is not None else None,
            },
        )
