"""Flattens an IVMS101 identity payload into a list of screenable parties.
Each party is a plain dict ready for the (future) screening engine -- this
module only extracts and normalizes fields, it makes no screening decisions.
"""

from app.webhook.schemas import IdentityPayload, LegalPerson, NaturalPerson, PersonName


def _person_name_str(name: PersonName) -> str:
    parts = []
    for ident in name.nameIdentifier:
        if ident.legalPersonName:
            parts.append(ident.legalPersonName)
            continue
        given = ident.secondaryIdentifier or ""
        family = ident.primaryIdentifier or ""
        full = " ".join(p for p in (given, family) if p)
        if full:
            parts.append(full)
    return "; ".join(parts)


def _natural_party(role: str, natural: NaturalPerson) -> dict:
    country = natural.countryOfResidence
    if not country and natural.geographicAddress:
        country = natural.geographicAddress[0].country

    national_ids = []
    if natural.nationalIdentification and natural.nationalIdentification.nationalIdentifier:
        national_ids.append({
            "type": natural.nationalIdentification.nationalIdentifierType,
            "value": natural.nationalIdentification.nationalIdentifier,
        })

    return {
        "role": role,
        "entity_type": "person",
        "name": _person_name_str(natural.name),
        "country": country,
        "national_ids": national_ids,
        "lei": None,
    }


def _legal_party(role: str, legal: LegalPerson) -> dict:
    country = legal.geographicAddress[0].country if legal.geographicAddress else None

    national_ids = []
    lei = None
    if legal.nationalIdentification and legal.nationalIdentification.nationalIdentifier:
        national_ids.append({
            "type": legal.nationalIdentification.nationalIdentifierType,
            "value": legal.nationalIdentification.nationalIdentifier,
        })
        if legal.nationalIdentification.nationalIdentifierType == "LEIX":
            lei = legal.nationalIdentification.nationalIdentifier

    return {
        "role": role,
        "entity_type": "legal_entity",
        "name": _person_name_str(legal.name),
        "country": country,
        "national_ids": national_ids,
        "lei": lei,
    }


def _envelope_party(role: str, envelope) -> dict | None:
    if envelope is None:
        return None
    if envelope.naturalPerson is not None:
        return _natural_party(role, envelope.naturalPerson)
    if envelope.legalPerson is not None:
        return _legal_party(role, envelope.legalPerson)
    return None


def extract_parties(identity: IdentityPayload) -> list:
    """Returns one dict per originator/beneficiary/VASP party found in the
    identity payload, each with role/entity_type/name/country/national_ids/lei."""
    parties = []

    if identity.originator:
        for envelope in identity.originator.originatorPersons:
            party = _envelope_party("originator", envelope)
            if party:
                parties.append(party)

    if identity.beneficiary:
        for envelope in identity.beneficiary.beneficiaryPersons:
            party = _envelope_party("beneficiary", envelope)
            if party:
                parties.append(party)

    if identity.originatingVASP:
        party = _envelope_party("originator_vasp", identity.originatingVASP.originatingVASP)
        if party:
            parties.append(party)

    if identity.beneficiaryVASP:
        party = _envelope_party("beneficiary_vasp", identity.beneficiaryVASP.beneficiaryVASP)
        if party:
            parties.append(party)

    return parties
