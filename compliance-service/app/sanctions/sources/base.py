"""Common interface every sanctions list source implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NormalizedRecord:
    """The common shape every source's parse() yields, before it's written
    to SanctionedEntity/EntityNameIndex. Deliberately source-agnostic -- the
    ingestion pipeline doesn't need to know OFAC vs EU vs UN internals."""

    source: str  # "OFAC_SDN" | "EU_FSF" | "UN_CONSOLIDATED"
    source_entity_id: str
    entity_type: str  # "person" | "legal_entity"
    primary_name: str
    aliases: list = field(default_factory=list)
    date_of_birth: str | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    country_of_residence: str | None = None
    national_ids: list = field(default_factory=list)  # [{"type": ..., "value": ...}]
    addresses: list = field(default_factory=list)
    programs: list = field(default_factory=list)
    lei: str | None = None
    raw_record: dict = field(default_factory=dict)


class SanctionsSource(ABC):
    """fetch() downloads the raw list file; parse() yields NormalizedRecord
    instances from it. ingest.py drives fetch -> parse -> stage uniformly
    across every registered source."""

    name: str
    source_url: str

    @abstractmethod
    def fetch(self) -> bytes:
        """Download the raw list file. Must use standard TLS verification
        (never disable certificate checking) -- this is compliance-critical
        data fetched over the public internet."""

    @abstractmethod
    def parse(self, raw: bytes):
        """Yields NormalizedRecord instances parsed from the raw file."""
