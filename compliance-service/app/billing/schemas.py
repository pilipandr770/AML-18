from pydantic import BaseModel


class UsageReply(BaseModel):
    plan_status: str
    period_usage: int
    free_tier_monthly_call_limit: int
