from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agent.policy import (
    DENIED, EXECUTE, NEEDS_HUMAN, RECOMMEND_ONLY, Policy, Proposal, evaluate,
)


def _policy(**over):
    base = dict(
        enabled_operations=["release", "hold"],
        max_amount_per_operation=Decimal("1000"),
        daily_cap=Decimal("5000"),
        allowed_assets=["ETH"],
        allowed_chains=["sepolia"],
        blocked_jurisdictions=["KP"],
        require_human_above=Decimal("500"),
    )
    base.update(over)
    return Policy(**base)


def _proposal(**over):
    base = dict(
        operation="release", amount=Decimal("100"), asset="ETH", chain="sepolia",
        counterparty_country="DE", counterparty_known=True,
        deterministic_decision="accepted", funds_verified=True,
        spent_today=Decimal("0"), llm_classification="clear",
    )
    base.update(over)
    return Proposal(**base)


def _run(proposal=None, policy=None, mode="operate", kill=False):
    return evaluate(proposal or _proposal(), policy or _policy(), mode, kill)


def test_clean_transfer_in_operate_mode_executes():
    assert _run().outcome == EXECUTE


def test_monitor_mode_never_executes():
    v = _run(mode="monitor")
    assert v.outcome == RECOMMEND_ONLY
    assert "inv_monitor_mode" in v.reasons


def test_kill_switch_overrides_everything():
    v = _run(kill=True)
    assert v.outcome == RECOMMEND_ONLY
    assert "inv_kill_switch" in v.reasons


@pytest.mark.parametrize("decision", ["review", "rejected"])
def test_sanctions_hit_always_goes_to_human_even_if_policy_allows_everything(decision):
    permissive = _policy(
        enabled_operations=["release", "hold", "reject"],
        max_amount_per_operation=Decimal("1e9"), daily_cap=Decimal("1e9"),
        require_human_above=Decimal("1e9"), new_counterparty_rule="allow",
    )
    for op in ("release", "hold", "reject"):
        v = _run(_proposal(operation=op, deterministic_decision=decision), permissive)
        assert v.outcome == NEEDS_HUMAN
        assert v.reasons == ["inv_sanctions_always_human"]


@pytest.mark.parametrize("cls", ["needs_review", "recommend_block", None])
def test_llm_can_only_escalate(cls):
    assert _run(_proposal(llm_classification=cls)).outcome == NEEDS_HUMAN


def test_llm_clear_cannot_override_deterministic_review():
    v = _run(_proposal(deterministic_decision="review", llm_classification="clear"))
    assert v.outcome == NEEDS_HUMAN


def test_operation_not_enabled_is_denied():
    assert _run(_proposal(operation="reject")).outcome == DENIED


def test_asset_and_chain_whitelist():
    assert _run(_proposal(asset="USDC")).outcome == DENIED
    assert _run(_proposal(chain="mainnet")).outcome == DENIED


def test_blocked_jurisdiction_needs_human():
    v = _run(_proposal(counterparty_country="kp"))
    assert v.outcome == NEEDS_HUMAN and "jurisdiction_blocked" in v.reasons


def test_amount_limits():
    assert "over_require_human_above" in _run(_proposal(amount=Decimal("600"))).reasons
    v = _run(_proposal(amount=Decimal("1500")))
    assert v.outcome == NEEDS_HUMAN and "over_max_amount_per_operation" in v.reasons


def test_daily_cap():
    v = _run(_proposal(amount=Decimal("100"), spent_today=Decimal("4950")))
    assert v.outcome == NEEDS_HUMAN and "over_daily_cap" in v.reasons


def test_new_counterparty_rules():
    assert _run(_proposal(counterparty_known=False)).outcome == NEEDS_HUMAN
    assert _run(_proposal(counterparty_known=False), _policy(new_counterparty_rule="allow")).outcome == EXECUTE
    assert _run(_proposal(counterparty_known=False), _policy(new_counterparty_rule="block")).outcome == DENIED


def test_release_requires_verified_funds():
    v = _run(_proposal(funds_verified=False))
    assert v.outcome == NEEDS_HUMAN and "funds_not_verified" in v.reasons


def test_empty_policy_denies_by_default():
    assert _run(policy=Policy()).outcome == DENIED


def test_policy_is_immutable_and_rejects_unknown_fields():
    p = _policy()
    with pytest.raises(ValidationError):
        p.daily_cap = Decimal("1")
    with pytest.raises(ValidationError):
        Policy(enabled_operations=["move_funds"])
    with pytest.raises(ValidationError):
        Policy(secret_backdoor=True)
