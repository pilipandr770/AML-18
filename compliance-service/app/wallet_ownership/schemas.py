from typing import Optional

from pydantic import BaseModel, Field


class ChallengeRequest(BaseModel):
    network: str = Field(default="ETH", min_length=1, max_length=16)
    address: str = Field(min_length=1, max_length=128)


class ChallengeReply(BaseModel):
    challenge_id: str
    network: str
    address: str
    message: str
    expires_at: str


class SignedMessageVerifyRequest(BaseModel):
    method: str = Field(default="signed_message")
    challenge_id: str = Field(min_length=1)
    signature: str = Field(min_length=1)
    transfer_amount_eur: Optional[float] = None
    transaction_id: Optional[str] = None


class TestTransferVerifyRequest(BaseModel):
    method: str = Field(default="test_transfer")
    network: str = Field(default="ETH", min_length=1, max_length=16)
    address: str = Field(min_length=1, max_length=128)
    transfer_amount_eur: Optional[float] = None
    transaction_id: Optional[str] = None


class VerificationReply(BaseModel):
    verification_id: str
    network: str
    address: str
    method: str
    status: str
    verified: Optional[bool] = None
    threshold_eur: float
    transfer_amount_eur: Optional[float] = None
    evidence: Optional[dict] = None
    last_error: Optional[str] = None
