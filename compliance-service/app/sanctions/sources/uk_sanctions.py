"""UK Sanctions List source (FCDO).

Since 28 Jan 2026 the UK publishes a single list on sanctionslist.fcdo.gov.uk
that replaced the OFSI Consolidated List. Structure verified against a real
downloaded file (root <Designations>, one <Designation> per listing; ~6,400):

  UniqueID            unique per designation (e.g. "AFG0001"); never repeats
  OFSIGroupID         OFSI group id, present on ~80% of designations; the same
                      group can be listed under several regimes (different
                      UniqueIDs) -> those are merged into ONE record here
  Names/Name          Name1..Name6 parts (Name6 is the surname / whole name for
                      entities and ships); NameType is "Primary Name" for the
                      main name, "Primary Name Variation" / "Alias" otherwise
                      (capitalisation is inconsistent in the file)
  NonLatinNames       original-script names (kept as aliases)
  RegimeName          sanctions regime (-> programs)
  IndividualEntityShip  "Individual" | "Entity" | "Ship"
  IndividualDetails   DOBs/DOB (dd/mm/yyyy, "dd/mm/yyyy" literal for year-only,
                      or a bare 4-digit year), Nationalities, BirthDetails,
                      PassportDetails, NationalIdentifierDetails
  EntityDetails       BusinessRegistrationNumbers (free text)
  ShipDetails         IMONumbers
  Addresses/Address   AddressLine1..6 + AddressCountry (Line6 is usually the
                      town/province)

Crypto wallets are NOT structured in this file; a handful of designations
mention them in free text (OtherInformation), so they are extracted with
conservative regexes (0x-addresses, Tron addresses, "Digital Currency
Address: XXX addr").

Terms of use: the UK list is published under the Open Government Licence v3.0;
attribute as "Contains public sector information licensed under the Open
Government Licence v3.0" (FCDO, UK Sanctions List).
"""

import re
from io import BytesIO

import requests
from defusedxml import ElementTree as etree  # untrusted XML from the internet

from app.sanctions.sources.base import NormalizedRecord, SanctionsSource

DOWNLOAD_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"

_MAX = 256

_ETH_RE = re.compile(r"\b0x[0-9a-fA-F]{40}\b")
_TRON_RE = re.compile(r"(?<![A-Za-z0-9])T[1-9A-HJ-NP-Za-km-z]{33}(?![A-Za-z0-9])")
_LABELLED_RE = re.compile(r"Digital Currency Address:\s*([A-Za-z0-9]{2,6})\s+([A-Za-z0-9]{20,100})")
_LABEL_BEFORE_RE = re.compile(r"([A-Z]{3,5})\W{0,4}$")
_CRYPTO_CONTEXT_RE = re.compile(r"(?i)crypto|wallet|digital currency|\bETH\b|\bUSDT\b")


def _clip(value, limit=_MAX):
    return value[:limit] if value else value


def _text(elem, tag):
    child = elem.find(tag)
    if child is not None and child.text and child.text.strip():
        return child.text.strip()
    return None


def _name_from_parts(name_elem) -> str | None:
    parts = []
    for i in range(1, 7):
        part = _text(name_elem, f"Name{i}")
        if part:
            parts.append(part)
    return " ".join(parts) if parts else None


def _parse_dob(value: str | None) -> str | None:
    """dd/mm/yyyy -> yyyy-mm-dd; 'dd/mm/yyyy' (literal) or a bare year -> yyyy;
    'dd/mm/yyyy' with a real month and unknown day -> yyyy-mm."""
    if not value:
        return None
    value = value.strip()
    m = re.fullmatch(r"(\d{2}|dd)/(\d{2}|mm)/(\d{4})", value)
    if m:
        day, month, year = m.groups()
        if month == "mm":
            return year
        if day == "dd":
            return f"{year}-{month}"
        return f"{year}-{month}-{day}"
    if re.fullmatch(r"\d{4}", value):
        return value
    return None


def _extract_crypto(text: str | None) -> list:
    if not text or not _CRYPTO_CONTEXT_RE.search(text):
        return []
    found = []
    seen = set()

    def add(currency, address):
        key = (currency, address)
        if key not in seen:
            seen.add(key)
            found.append({"currency": currency, "address": address})

    for m in _LABELLED_RE.finditer(text):
        add(m.group(1).upper(), m.group(2))
    for regex, default in ((_ETH_RE, "ETH"), (_TRON_RE, "TRX")):
        for m in regex.finditer(text):
            label = _LABEL_BEFORE_RE.search(text[max(0, m.start() - 12):m.start()])
            currency = label.group(1) if label and default == "ETH" else default
            add(currency, m.group(0))
    return found


class UKSanctionsListSource(SanctionsSource):
    name = "UK_SANCTIONS_LIST"
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
        # One designation can appear under several regimes with the same
        # OFSIGroupID; merge them so the same entity is emitted once.
        merged: dict[str, NormalizedRecord] = {}

        for _event, elem in etree.iterparse(BytesIO(raw), events=("end",)):
            if elem.tag != "Designation":
                continue
            record = self._parse_designation(elem)
            elem.clear()
            if record is None:
                continue
            existing = merged.get(record.source_entity_id)
            if existing is None:
                merged[record.source_entity_id] = record
            else:
                self._merge(existing, record)

        yield from merged.values()

    @staticmethod
    def _merge(target: NormalizedRecord, other: NormalizedRecord) -> None:
        for alias in [other.primary_name, *other.aliases]:
            if alias != target.primary_name and alias not in target.aliases:
                target.aliases.append(alias)
        for list_name in ("national_ids", "addresses", "crypto_addresses"):
            mine = getattr(target, list_name)
            for item in getattr(other, list_name):
                if item not in mine:
                    mine.append(item)
        for program in other.programs:
            if program not in target.programs:
                target.programs.append(program)
        for attr in ("date_of_birth", "place_of_birth", "nationality", "country_of_residence", "lei"):
            if not getattr(target, attr) and getattr(other, attr):
                setattr(target, attr, getattr(other, attr))
        target.raw_record.setdefault("unique_ids", [target.raw_record.get("unique_id")]).append(
            other.raw_record.get("unique_id")
        )

    def _parse_designation(self, d) -> NormalizedRecord | None:
        unique_id = _text(d, "UniqueID")
        group_id = _text(d, "OFSIGroupID")
        entity_id = group_id or unique_id
        if not entity_id:
            return None

        kind = (_text(d, "IndividualEntityShip") or "").lower()
        entity_type = "person" if kind == "individual" else "legal_entity"

        primary = None
        names = []
        names_elem = d.find("Names")
        if names_elem is not None:
            for n in names_elem.findall("Name"):
                full = _name_from_parts(n)
                if not full:
                    continue
                if primary is None and (_text(n, "NameType") or "").strip().lower() == "primary name":
                    primary = full
                else:
                    names.append(full)
        non_latin = [
            t.text.strip()
            for t in d.iter("NameNonLatinScript")
            if t.text and t.text.strip()
        ]
        names.extend(non_latin)
        if primary is None:
            if not names:
                return None
            primary = names.pop(0)

        seen = {primary.casefold()}
        aliases = []
        for n in names:
            key = n.casefold()
            if key not in seen:
                seen.add(key)
                aliases.append(_clip(n))

        dobs = [_text(x, ".") for x in d.iter("DOB")]
        dobs = [x for x in dobs if x]
        parsed = [_parse_dob(x) for x in dobs]
        parsed = [p for p in parsed if p]
        date_of_birth = next((p for p in parsed if len(p) == 10), parsed[0] if parsed else None)

        nationalities = [t.text.strip() for t in d.iter("Nationality") if t.text and t.text.strip()]
        nationality = _clip(nationalities[0]) if nationalities else None

        place_of_birth = None
        loc = next(d.iter("Location"), None)
        if loc is not None:
            bits = [_text(loc, "TownOfBirth"), _text(loc, "CountryOfBirth")]
            bits = [b for b in bits if b]
            place_of_birth = _clip(", ".join(bits)) if bits else None

        national_ids = []

        def add_id(id_type, value):
            if value:
                item = {"type": id_type, "value": _clip(value)}
                if item not in national_ids:
                    national_ids.append(item)

        for p in d.iter("PassportNumber"):
            add_id("Passport", p.text.strip() if p.text else None)
        for p in d.iter("NationalIdentifierNumber"):
            add_id("National ID", p.text.strip() if p.text else None)
        for p in d.iter("BusinessRegistrationNumber"):
            add_id("Business Registration Number", " ".join(p.text.split()) if p.text else None)
        for p in d.iter("IMONumber"):
            add_id("IMO Number", p.text.strip() if p.text else None)

        addresses = []
        addrs_elem = d.find("Addresses")
        if addrs_elem is not None:
            for a in addrs_elem.findall("Address"):
                city = next(
                    (v for v in (_text(a, f"AddressLine{i}") for i in (6, 5, 4, 3)) if v),
                    None,
                )
                country = _text(a, "AddressCountry")
                if not city and not country:
                    continue
                item = {"city": _clip(city), "country": _clip(country)}
                if item not in addresses:
                    addresses.append(item)
        country_of_residence = next((a["country"] for a in addresses if a["country"]), None)

        regime = _text(d, "RegimeName")
        programs = [regime] if regime else []

        other_info = _text(d, "OtherInformation")
        crypto = _extract_crypto(other_info)

        return NormalizedRecord(
            source=self.name,
            source_entity_id=entity_id,
            entity_type=entity_type,
            primary_name=_clip(primary),
            aliases=aliases,
            date_of_birth=date_of_birth,
            place_of_birth=place_of_birth,
            nationality=nationality,
            country_of_residence=country_of_residence,
            national_ids=national_ids,
            addresses=addresses,
            programs=programs,
            lei=None,
            raw_record={
                "unique_id": unique_id,
                "ofsi_group_id": group_id,
                "un_reference": _text(d, "UNReferenceNumber"),
                "designation_source": _text(d, "DesignationSource"),
                "date_designated": _text(d, "DateDesignated"),
                "kind": kind,
                "dobs": dobs[:10],
            },
            crypto_addresses=crypto,
        )
