"""Pydantic models mirroring envoy's pkg/webhook/api.go Request/Reply/Payload
shapes, plus the subset of IVMS101 needed to extract screenable parties.
Field shapes verified against tests/fixtures/*.json (copied verbatim from
envoy/pkg/webhook/testdata).

Deliberately loose in a few places (e.g. `pending`/`transaction`/`sunrise`,
`error` kept as plain dicts): Phase 0 only needs the identity payload, not
the transfer-state machinery, so those are passed through opaquely rather
than fully modeled.
"""

from typing import Optional

from pydantic import BaseModel, Field


class NameIdentifier(BaseModel):
    # Natural person convention: secondaryIdentifier = given/forename,
    # primaryIdentifier = surname/family name (confirmed via fixture).
    primaryIdentifier: Optional[str] = None
    secondaryIdentifier: Optional[str] = None
    nameIdentifierType: Optional[str] = None
    # Legal person convention: name carried in legalPersonName instead.
    legalPersonName: Optional[str] = None
    legalPersonNameIdentifierType: Optional[str] = None


class PersonName(BaseModel):
    nameIdentifier: list[NameIdentifier] = Field(default_factory=list)


class GeographicAddress(BaseModel):
    addressType: Optional[str] = None
    address_lines: list[str] = Field(default_factory=list)
    country: Optional[str] = None


class NationalIdentification(BaseModel):
    nationalIdentifier: Optional[str] = None
    nationalIdentifierType: Optional[str] = None  # e.g. "LEIX" for a VASP's LEI


class NaturalPerson(BaseModel):
    name: PersonName = Field(default_factory=PersonName)
    geographicAddress: list[GeographicAddress] = Field(default_factory=list)
    customerIdentification: Optional[str] = None
    countryOfResidence: Optional[str] = None
    nationalIdentification: Optional[NationalIdentification] = None


class LegalPerson(BaseModel):
    name: PersonName = Field(default_factory=PersonName)
    geographicAddress: list[GeographicAddress] = Field(default_factory=list)
    nationalIdentification: Optional[NationalIdentification] = None


class PersonEnvelope(BaseModel):
    naturalPerson: Optional[NaturalPerson] = None
    legalPerson: Optional[LegalPerson] = None


class OriginatorBlock(BaseModel):
    originatorPersons: list[PersonEnvelope] = Field(default_factory=list)
    accountNumber: list[str] = Field(default_factory=list)


class BeneficiaryBlock(BaseModel):
    beneficiaryPersons: list[PersonEnvelope] = Field(default_factory=list)
    accountNumber: list[str] = Field(default_factory=list)


class OriginatingVASPBlock(BaseModel):
    # IVMS101's protobuf-to-JSON naming nests a field of the same name as its
    # wrapper message -- confirmed via fixture: {"originatingVASP": {"originatingVASP": {...}}}
    originatingVASP: Optional[PersonEnvelope] = None


class BeneficiaryVASPBlock(BaseModel):
    beneficiaryVASP: Optional[PersonEnvelope] = None


class IdentityPayload(BaseModel):
    originator: Optional[OriginatorBlock] = None
    beneficiary: Optional[BeneficiaryBlock] = None
    originatingVASP: Optional[OriginatingVASPBlock] = None
    beneficiaryVASP: Optional[BeneficiaryVASPBlock] = None


class Payload(BaseModel):
    identity: Optional[IdentityPayload] = None
    pending: Optional[dict] = None
    transaction: Optional[dict] = None
    sunrise: Optional[dict] = None
    sent_at: Optional[str] = None
    received_at: Optional[str] = None


class Counterparty(BaseModel):
    id: Optional[str] = None
    source: Optional[str] = None
    directory_id: Optional[str] = None
    registered_directory: Optional[str] = None
    protocol: Optional[str] = None
    common_name: Optional[str] = None
    endpoint: Optional[str] = None
    travel_address: Optional[str] = None
    name: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    business_category: Optional[str] = None
    vasp_categories: list[str] = Field(default_factory=list)
    verified_on: Optional[str] = None
    ivms101: Optional[str] = None


class WebhookRequest(BaseModel):
    transaction_id: str
    timestamp: Optional[str] = None
    counterparty: Optional[Counterparty] = None
    hmac_signature: Optional[str] = None
    public_key_signature: Optional[str] = None
    transfer_state: Optional[str] = None
    error: Optional[dict] = None
    payload: Optional[Payload] = None


class WebhookReply(BaseModel):
    transaction_id: str
    error: Optional[dict] = None
    payload: Optional[dict] = None
    transfer_action: Optional[str] = None
