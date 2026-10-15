"""OFAC Consolidated (non-SDN) sanctions lists source.

Verified against the real file: it uses the identical classic
sdnList/sdnEntry schema as SDN.XML (only sdnEntry children, sdnType is
"Individual" or "Entity"), so the SDN parser is reused. Differences vs SDN:
own download URL / source name, and (per the observed file) no vessels or
digital-currency address ids. Digital currency ids, if OFAC adds them, stay
in national_ids and ingest derives crypto_addresses from them.
"""

import requests

from app.sanctions.sources.ofac_sdn import OFACSDNSource

DOWNLOAD_URL = "https://sanctionslistservice.ofac.treas.gov/api/download/consolidated.xml"

_MAX = 256


class OFACConsolidatedSource(OFACSDNSource):
    name = "OFAC_CONSOLIDATED"
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
        for record in super().parse(raw):
            record.primary_name = (record.primary_name or "").strip()[:_MAX]
            if not record.primary_name:
                continue  # nameless entries are unusable for matching
            if record.nationality:
                record.nationality = record.nationality[:_MAX]
            if record.country_of_residence:
                record.country_of_residence = record.country_of_residence[:_MAX]
            yield record
