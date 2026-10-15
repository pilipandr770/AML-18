from typing import List, Optional

from pydantic import BaseModel, Field


class CheckNameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    date_of_birth: Optional[str] = Field(default=None, max_length=32)
    country: Optional[str] = Field(default=None, max_length=256)


class MatchDetail(BaseModel):
    entity_id: int
    sanctioned_name: str
    name_score: float
    name_type: str
    corroborating_fields: dict
    rule_branch: str
    decision: str


class CheckAddressRequest(BaseModel):
    address: str = Field(min_length=1, max_length=128)


class AddressMatch(BaseModel):
    sanctioned_name: str
    source: str
    source_entity_id: str
    currency: str
    address: str
    programs: List[str]


class CheckAddressReply(BaseModel):
    listed: bool
    decision: str  # "rejected" on an exact listed-address match (a human still decides), else "accepted"
    matches: List[AddressMatch]


class CheckNameReply(BaseModel):
    decision: str
    score: float
    matches: List[MatchDetail]
