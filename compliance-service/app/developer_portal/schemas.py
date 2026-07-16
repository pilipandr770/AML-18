from typing import Optional

from pydantic import BaseModel, Field

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class ProjectSignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    contact_email: str = Field(min_length=3, max_length=256, pattern=_EMAIL_PATTERN)
    webhook_url: Optional[str] = Field(default=None, max_length=512)


class ProjectReply(BaseModel):
    project_id: str
    name: str
    contact_email: str
    webhook_url: Optional[str] = None
    api_key_prefix: str
    created_at: str
    last_used_at: Optional[str] = None
