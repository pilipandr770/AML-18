"""Deterministic policy engine. No LLM, no database, no I/O: given a
proposed operation and a snapshot of facts, it returns a verdict. Every
agent action must pass through evaluate() before anything is executed.

The policy and mode are inputs here, never outputs: nothing in this module
(or any agent tool) can modify them -- only the authenticated owner routes
write them (app/agent/owner.py).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Operation = Literal[
    "release",
    "hold",
    "reject",
    "confirm_wallet_ownership",
    "reject_wallet_ownership",
    "close_simple_review",
]
ALL_OPERATIONS = (
    "release", "hold", "reject",
    "confirm_wallet_ownership", "reject_wallet_ownership", "close_simple_review",
)

# Verdicts
EXECUTE = "execute"          # may be carried out automatically (OPERATE mode only)
NEEDS_HUMAN = "needs_human"  # park for an owner decision
DENIED = "denied"            # not permitted at all
RECOMMEND_ONLY = "recommend_only"  # MONITOR mode / kill switch: record, never act


class Policy(BaseModel):
    """Per-client policy. Frozen: an evaluated policy cannot be mutated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled_operations: list[Operation] = Field(default_factory=list)
    max_amount_per_operation: Decimal = Decimal("0")
    daily_cap: Decimal = Decimal("0")
    allowed_assets: list[str] = Field(default_factory=list)  # empty = none allowed
    allowed_chains: list[str] = Field(default_factory=list)
    blocked_jurisdictions: list[str] = Field(default_factory=list)  # ISO country codes
    require_human_above: Decimal = Decimal("0")
    new_counterparty_rule: Literal["allow", "require_human", "block"] = "require_human"


@dataclass(frozen=True)
class Proposal:
    operation: str
    amount: Decimal
    asset: str
    chain: str
    counterparty_country: Optional[str]
    counterparty_known: bool
    # Facts computed by deterministic code, NOT by the LLM:
    deterministic_decision: str          # accepted | review | rejected (sanctions screening floor)
    funds_verified: bool
    spent_today: Decimal                 # sum of already-executed amounts today
    # The LLM's view; it can only raise caution, never lower it:
    llm_classification: Optional[str] = None  # clear | needs_review | recommend_block


@dataclass(frozen=True)
class Verdict:
    outcome: str
    reasons: list[str] = field(default_factory=list)  # stable rule ids, written to the journal


def evaluate(proposal: Proposal, policy: Policy, mode: str, kill_switch: bool) -> Verdict:
    # --- Hard invariants: not configurable, checked first -----------------
    if kill_switch:
        return Verdict(RECOMMEND_ONLY, ["inv_kill_switch"])
    if mode != "operate":
        return Verdict(RECOMMEND_ONLY, ["inv_monitor_mode"])

    reasons: list[str] = []

    # A sanctions hit (exact or fuzzy above the review threshold) is never
    # processed automatically, whatever the policy or the LLM says.
    if proposal.deterministic_decision != "accepted":
        return Verdict(NEEDS_HUMAN, ["inv_sanctions_always_human"])

    # The LLM may only escalate. Anything but an explicit "clear" goes to a human.
    if proposal.llm_classification != "clear":
        return Verdict(NEEDS_HUMAN, ["inv_llm_not_clear"])

    # --- Configurable policy ---------------------------------------------
    if proposal.operation not in policy.enabled_operations:
        return Verdict(DENIED, ["op_not_enabled"])
    if proposal.asset not in policy.allowed_assets:
        return Verdict(DENIED, ["asset_not_allowed"])
    if proposal.chain not in policy.allowed_chains:
        return Verdict(DENIED, ["chain_not_allowed"])

    country = (proposal.counterparty_country or "").upper()
    if country and country in {c.upper() for c in policy.blocked_jurisdictions}:
        return Verdict(NEEDS_HUMAN, ["jurisdiction_blocked"])

    if proposal.operation == "release" and not proposal.funds_verified:
        reasons.append("funds_not_verified")

    if proposal.amount > policy.max_amount_per_operation:
        reasons.append("over_max_amount_per_operation")
    if proposal.amount > policy.require_human_above:
        reasons.append("over_require_human_above")
    if proposal.spent_today + proposal.amount > policy.daily_cap:
        reasons.append("over_daily_cap")

    if not proposal.counterparty_known:
        if policy.new_counterparty_rule == "block":
            return Verdict(DENIED, ["new_counterparty_blocked"])
        if policy.new_counterparty_rule == "require_human":
            reasons.append("new_counterparty_requires_human")

    if reasons:
        return Verdict(NEEDS_HUMAN, reasons)
    return Verdict(EXECUTE, ["policy_ok"])
