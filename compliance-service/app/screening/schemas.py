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


class CheckNameReply(BaseModel):
    decision: str
    score: float
    matches: List[MatchDetail]
