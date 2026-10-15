"""Swiss SECO sanctions list source (SESAM "whole list" XML download).

Structure, verified against a real downloaded file (not guessed):

* Root ``swiss-sanctions-list`` holds, in this order: ``sanctions-program``
  elements (program-key / sanctions-set per language), ``target`` elements,
  and finally ``place`` elements.
* A ``target`` (ssid = stable id) holds a ``sanctions-set-id`` (-> program)
  and one of ``individual`` / ``entity`` / ``object`` (vessels).
* The same target ssid appears SEVERAL times: older versions are plain
  snapshots without ``modification`` children; the current version is the one
  carrying the ``modification`` history (newest first). A target whose newest
  modification is ``de-listed`` is no longer sanctioned and is skipped.
* Names live in ``identity/name`` (name-type primary-name | alias |
  formerly-known-as), assembled from ``name-part`` (given-name, family-name,
  father-name, whole-name, ...). ``spelling-variant`` children carry other
  scripts/spellings of a part and become additional aliases.
* Birth place and addresses only reference ``place`` elements by ``place-id``,
  which come after the targets, so records are resolved after the full pass.
* Crypto wallets are not structured; they appear in free-text
  ``other-information`` ("Known ... wallet addresses: ETH: 0x..; BTC: ...").

Terms of use: published by the Swiss State Secretariat for Economic Affairs
(SECO) as open government data; please attribute SECO as the source.
"""

import io
import re

import requests
from defusedxml import ElementTree as etree  # untrusted XML from the internet: no entity expansion

from app.sanctions.sources.base import NormalizedRecord, SanctionsSource

DOWNLOAD_URL = (
    "https://www.sesam.search.admin.ch/sesam-search-web/pages/downloadXmlGesamtliste.xhtml"
    "?lang=en&action=downloadXmlGesamtlisteAction"
)

_MAX = 256

# Display order of name parts: given names first, family name last.
_PART_RANK = {
    "given-name": 1,
    "further-given-name": 2,
    "father-name": 3,
    "grand-father-name": 4,
    "whole-name": 5,
    "other": 5,
    "family-name": 6,
    "maiden-name": 7,
    "suffix": 8,
}
_SKIP_PARTS = {"title"}

_EVM = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BTC = re.compile(r"^(bc1[0-9a-z]{20,80}|[13][1-9A-HJ-NP-Za-km-z]{25,34})$")
_TRX = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
_LABEL = re.compile(r"\b([A-Z]{2,6})\s*:")


def _clip(value, limit=_MAX):
    if value is None:
        return None
    value = " ".join(str(value).split())
    return value[:limit] if value else None


def _text(elem):
    return (elem.text or "").strip() if elem is not None else ""


def _assemble(parts, variant_key=None):
    """parts: list of (order, type, value, {variant_key: text}). Returns the
    assembled name or None. With variant_key, uses that spelling variant per
    part, falling back to the base value for parts that lack it."""
    pieces = []
    used_variant = False
    for order, ptype, value, variants in parts:
        if ptype in _SKIP_PARTS:
            continue
        text = value
        if variant_key is not None and variants.get(variant_key):
            text = variants[variant_key]
            used_variant = True
        if text:
            pieces.append((_PART_RANK.get(ptype, 5), order, text))
    if variant_key is not None and not used_variant:
        return None
    pieces.sort(key=lambda p: (p[0], p[1]))
    name = " ".join(p[2] for p in pieces).strip()
    return _clip(name, 512) if name else None


def _parse_name(name_elem):
    """Returns (name_type, [assembled base name + spelling-variant names])."""
    parts = []
    variant_keys = []
    for np_ in name_elem.findall("name-part"):
        try:
            order = int(np_.get("order") or 0)
        except ValueError:
            order = 0
        variants = {}
        for sv in np_.findall("spelling-variant"):
            key = (sv.get("lang"), sv.get("script"))
            text = _text(sv)
            if text:
                variants.setdefault(key, text)
                if key not in variant_keys:
                    variant_keys.append(key)
        parts.append((order, np_.get("name-part-type") or "", _text(np_.find("value")), variants))
    names = []
    base = _assemble(parts)
    if base:
        names.append(base)
    for key in variant_keys:
        v = _assemble(parts, key)
        if v and v not in names:
            names.append(v)
    return name_elem.get("name-type"), names


def _format_dmy(d):
    year, month, day = d.get("year"), d.get("month"), d.get("day")
    try:
        if year and month and day:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        if year and month:
            return f"{int(year):04d}-{int(month):02d}"
        if year:
            return f"{int(year):04d}"
        if month and day:
            return f"--{int(month):02d}-{int(day):02d}"
    except ValueError:
        return None
    return None


def _extract_crypto(text):
    """Pulls wallet addresses out of free text like
    'Known wallet addresses: ETH: 0x..; BTC: bc1..; 3My..; TRX: T..'."""
    low = text.lower()
    if "address" not in low or not ("wallet" in low or "blockchain" in low):
        return []
    found = []
    currency = None
    for chunk in re.split(r"[;,\n]", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        labels = list(_LABEL.finditer(chunk))
        if labels:
            currency = labels[-1].group(1)
            chunk = chunk[labels[-1].end():].strip()
        token = chunk.split()[-1] if chunk.split() else ""
        token = token.strip(".")
        if _EVM.match(token):
            cur = currency if currency in {"ETH", "BSC", "BNB", "ARB", "POL", "OP"} else "ETH"
        elif _TRX.match(token):
            cur = "TRX"
        elif _BTC.match(token):
            cur = "XBT" if currency in (None, "BTC", "XBT") else currency
        else:
            continue
        item = {"currency": cur, "address": token}
        if item not in found:
            found.append(item)
    return found


class SECOSource(SanctionsSource):
    name = "CH_SECO"
    source_url = DOWNLOAD_URL

    def fetch(self) -> bytes:
        response = requests.get(
            self.source_url,
            timeout=300,
            headers={"User-Agent": "Mozilla/5.0 (AML18 sanctions fetch)"},
        )
        response.raise_for_status()
        return response.content

    # ------------------------------------------------------------------ parse
    def parse(self, raw: bytes):
        set_to_program: dict[str, str] = {}
        current: dict[str, dict] = {}  # target ssid -> parsed current version
        sets_by_target: dict[str, list] = {}
        places: dict[str, dict] = {}

        depth = 0
        for event, elem in etree.iterparse(io.BytesIO(raw), events=("start", "end")):
            if event == "start":
                depth += 1
                continue
            depth -= 1
            if depth != 1:
                continue  # only react to direct children of the root
            tag = elem.tag
            if tag == "sanctions-program":
                program = _clip(
                    next((k.text for k in elem.findall("program-key") if k.get("lang") == "eng" and k.text), None)
                )
                for s in elem.findall("sanctions-set"):
                    if program and s.get("ssid"):
                        set_to_program[s.get("ssid")] = program
                elem.clear()
            elif tag == "target":
                self._collect_target(elem, current, sets_by_target)
                elem.clear()
            elif tag == "place":
                places[elem.get("ssid")] = self._parse_place(elem)
                elem.clear()

        for ssid, data in current.items():
            if data is None:
                continue  # de-listed
            record = self._build(ssid, data, sets_by_target.get(ssid, []), set_to_program, places)
            if record is not None:
                yield record

    def _collect_target(self, target, current, sets_by_target):
        ssid = target.get("ssid")
        if not ssid:
            return
        set_id = _text(target.find("sanctions-set-id"))
        if set_id:
            lst = sets_by_target.setdefault(ssid, [])
            if set_id not in lst:
                lst.append(set_id)

        mods = [m.get("modification-type") for m in target.findall("modification")]
        has_mod = bool(mods)
        existing = current.get(ssid, "absent")
        if has_mod and mods[0] == "de-listed":
            current[ssid] = None
            return
        # The version carrying the modification history is the current one;
        # plain snapshots are older versions and only serve as a fallback.
        if existing is None:
            return
        if existing != "absent" and existing["has_mod"] and not has_mod:
            return

        node = next((c for c in target if c.tag in ("individual", "entity", "object")), None)
        if node is None:
            return
        data = self._parse_node(node)
        data["has_mod"] = has_mod
        data["kind"] = node.tag
        data["object_type"] = node.get("object-type")
        current[ssid] = data

    def _parse_node(self, node):
        main_names, other_names, formerly = [], [], []
        dobs, pobs, nats, ids, addrs, crypto = [], [], [], [], [], []
        infos = []

        identities = node.findall("identity")
        identities.sort(key=lambda i: 0 if i.get("main") == "true" else 1)
        for identity in identities:
            is_main = identity.get("main") == "true"
            for name in identity.findall("name"):
                ntype, assembled = _parse_name(name)
                if not assembled:
                    continue
                if ntype == "primary-name" and is_main and not main_names:
                    main_names.extend(assembled)
                else:
                    (formerly if ntype == "formerly-known-as" else other_names).extend(assembled)
            for d in identity.findall("day-month-year"):
                value = _format_dmy(d)
                if value and value not in dobs:
                    dobs.append(value)
            for pob in identity.findall("place-of-birth"):
                if pob.get("place-id"):
                    pobs.append(pob.get("place-id"))
            for nat in identity.findall("nationality"):
                c = _text(nat.find("country"))
                if c and c not in nats:
                    nats.append(c)
            for doc in identity.findall("identification-document"):
                number = _text(doc.find("number"))
                if number:
                    issuer = _text(doc.find("issuer"))
                    dtype = doc.get("document-type") or "id"
                    ids.append({"type": dtype, "value": number, **({"issuer": issuer} if issuer else {})})
            for addr in identity.findall("address"):
                addrs.append(
                    {
                        "place_id": addr.get("place-id"),
                        "street": _clip(_text(addr.find("address-details")), 300),
                        "zip": _clip(_text(addr.find("zip-code")), 32),
                    }
                )
        # nationality / birth data sit directly under individual on some versions
        for nat in node.findall("nationality"):
            c = _text(nat.find("country"))
            if c and c not in nats:
                nats.append(c)
        for info in node.findall("other-information"):
            t = _text(info)
            if t:
                infos.append(t)
                for item in _extract_crypto(t):
                    if item not in crypto:
                        crypto.append(item)
        justification = _clip(_text(node.find("justification")), 300)
        return {
            "main_names": main_names,
            "aliases": other_names + formerly,
            "dobs": dobs,
            "pobs": pobs,
            "nats": nats,
            "ids": ids,
            "addrs": addrs,
            "crypto": crypto,
            "infos": infos,
            "justification": justification,
        }

    @staticmethod
    def _parse_place(place):
        return {
            "location": _clip(_text(place.find("location"))),
            "area": _clip(_text(place.find("area"))),
            "country": _clip(_text(place.find("country"))),
        }

    def _build(self, ssid, data, set_ids, set_to_program, places):
        names = data["main_names"] or data["aliases"][:1]
        if not names:
            return None
        primary = _clip(names[0])
        if not primary:
            return None
        aliases = []
        for n in list(names[1:]) + data["aliases"]:
            n = _clip(n)
            if n and n != primary and n not in aliases:
                aliases.append(n)

        place_pob = None
        for pid in data["pobs"]:
            p = places.get(pid)
            if p:
                place_pob = _clip(", ".join(x for x in (p["location"], p["area"], p["country"]) if x))
                if place_pob:
                    break

        addresses = []
        for a in data["addrs"]:
            p = places.get(a["place_id"]) or {}
            entry = {"city": p.get("location") or p.get("area"), "country": p.get("country")}
            if a.get("street"):
                entry["street"] = a["street"]
            if a.get("zip"):
                entry["zip"] = a["zip"]
            if entry["city"] or entry["country"] or entry.get("street"):
                addresses.append(entry)
        residence = next((a["country"] for a in addresses if a.get("country")), None)

        programs = []
        for sid in set_ids:
            prog = set_to_program.get(sid)
            if prog and prog not in programs:
                programs.append(prog)

        kind = data["kind"]
        entity_type = "person" if kind == "individual" else "legal_entity"

        raw_record = {"ssid": ssid, "kind": kind}
        if data["object_type"]:
            raw_record["object_type"] = data["object_type"]
        if data["justification"]:
            raw_record["justification"] = data["justification"]
        if len(data["dobs"]) > 1:
            raw_record["additional_dates_of_birth"] = data["dobs"][1:]
        for info in data["infos"]:
            if info.startswith("IMO Number"):
                raw_record["imo"] = _clip(info.split(":", 1)[-1], 32)
                break

        return NormalizedRecord(
            source=self.name,
            source_entity_id=str(ssid),
            entity_type=entity_type,
            primary_name=primary,
            aliases=aliases,
            date_of_birth=data["dobs"][0] if data["dobs"] else None,
            place_of_birth=place_pob,
            nationality=_clip("; ".join(data["nats"])) if data["nats"] else None,
            country_of_residence=residence,
            national_ids=data["ids"],
            addresses=addresses,
            programs=programs,
            lei=None,
            raw_record=raw_record,
            crypto_addresses=data["crypto"],
        )
