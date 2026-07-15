from datetime import datetime

from pydantic import BaseModel, Field


class AgeVerificationRequest(BaseModel):
    subject_reference: str = Field(min_length=1, max_length=128)
    proof_token: str = Field(min_length=1)
    adapter: str | None = Field(default=None, min_length=1, max_length=32)


class AgeVerificationReply(BaseModel):
    verification_id: int
    subject_reference: str
    adapter: str
    verified: bool
    min_age: int
    method: str | None
    verified_at: datetime | None
    expires_at: datetime | None


class AgeVerificationSessionRequest(BaseModel):
    subject_reference: str = Field(min_length=1, max_length=128)
    adapter: str | None = Field(default=None, min_length=1, max_length=32)
    min_age: int | None = Field(default=None, ge=13, le=120)


class AgeVerificationSessionReply(BaseModel):
    session_id: str
    subject_reference: str
    adapter: str
    status: str
    min_age: int
    transaction_id: str
    request_value: str | None
    verification_id: int | None = None
    verified: bool | None = None
    method: str | None = None
    last_error: str | None = None