from decimal import Decimal

import pytest

from app import create_app
from app.agent.chain import MockLedger
from app.agent.factory import AgentRuntime
from app.agent.llm import LLMResponse, ScriptedLLM
from app.agent.models import AgentCase, AgentSettings, DepositAddress
from app.agent.monitor import scan_address
from app.agent.operations import RecordingExecutor
from app.developer_portal.models import DeveloperProject
from app.extensions import db
from app.sanctions.ingest import ingest_source
from tests.conftest import TestConfig, _mint_project
from tests.test_engine import _FixtureOFACSource


class AgentConfig(TestConfig):
    AGENT_ENABLED = True


@pytest.fixture
def agent_app():
    app = create_app(AgentConfig)
    with app.app_context():
        db.create_all()
        ingest_source(_FixtureOFACSource())  # US profile requires a fresh OFAC_SDN list
        yield app


def _llm_clear():
    return ScriptedLLM([
        LLMResponse("tool_use", [{"type": "tool_use", "id": "1", "name": "record_decision",
                                  "input": {"classification": "clear", "explanation": "ok"}}]),
        LLMResponse("end_turn", [{"type": "text", "text": "done"}]),
    ])


def _body(**over):
    base = {"chain": "sepolia", "asset": "ETH", "amount": "0.5", "tx_hash": "0x1", "deposit_address": "0xDep",
            "counterparty_name": "Anna Schmidt", "counterparty_country": "DE", "memo": "Invoice 1"}
    base.update(over)
    return base


def test_agent_routes_are_404_when_disabled(client, auth_headers):
    assert client.post("/agent/transfers", json=_body(), headers=auth_headers).status_code == 404


def test_transfer_requires_api_key(agent_app):
    assert agent_app.test_client().post("/agent/transfers", json=_body()).status_code == 401


def test_submit_transfer_runs_the_agent_and_is_idempotent(agent_app):
    ledger = MockLedger(1)
    ledger.add("0x1", "0xDep", "0.5", 5)
    agent_app.extensions["agent_runtime"] = AgentRuntime(_llm_clear(), ledger, RecordingExecutor())
    _pid, headers = _mint_project(agent_app, jurisdiction="US")
    client = agent_app.test_client()

    r = client.post("/agent/transfers", json=_body(), headers=headers)
    assert r.status_code == 201
    data = r.get_json()
    assert data["classification"] == "clear" and data["status"] == "auto_cleared" and data["funds_verified"] is True

    again = client.post("/agent/transfers", json=_body(), headers=headers)
    assert again.status_code == 200 and again.get_json()["case_id"] == data["case_id"]
    assert AgentCase.query.count() == 1


def test_bad_amount_rejected(agent_app):
    _pid, headers = _mint_project(agent_app)
    assert agent_app.test_client().post("/agent/transfers", json=_body(amount="-1"), headers=headers).status_code == 400


def test_cases_are_tenant_isolated(agent_app):
    ledger = MockLedger(1)
    ledger.add("0x1", "0xDep", "0.5", 5)
    agent_app.extensions["agent_runtime"] = AgentRuntime(_llm_clear(), ledger, RecordingExecutor())
    _a, ha = _mint_project(agent_app, jurisdiction="US")
    _b, hb = _mint_project(agent_app, name="B", contact_email="b@example.com")
    client = agent_app.test_client()
    cid = client.post("/agent/transfers", json=_body(), headers=ha).get_json()["case_id"]
    assert client.get(f"/agent/cases/{cid}", headers=ha).status_code == 200
    assert client.get(f"/agent/cases/{cid}", headers=hb).status_code == 404


def test_unidentified_counterparty_goes_to_human(agent_app):
    agent_app.extensions["agent_runtime"] = AgentRuntime(_llm_clear(), MockLedger(1), RecordingExecutor())
    _pid, headers = _mint_project(agent_app)
    r = agent_app.test_client().post("/agent/transfers", json=_body(counterparty_name=None, tx_hash="0x9"), headers=headers)
    assert r.get_json()["deterministic_decision"] == "review"
    assert r.get_json()["status"] == "awaiting_human"


def test_monitor_opens_cases_for_deposits_and_dedupes(agent_app):
    p = DeveloperProject(name="M", contact_email="m@example.com", api_key_prefix="x", api_key_hash="h" * 64)
    db.session.add(p)
    db.session.commit()
    dep = DepositAddress(developer_project_id=p.id, chain="sepolia", asset="ETH", address="0xDEP", last_scanned_block=99)
    db.session.add(dep)
    db.session.commit()

    blocks = {
        "0x64": {"transactions": [
            {"hash": "0xaa", "to": "0xdep", "value": hex(5 * 10**17)},
            {"hash": "0xbb", "to": "0xother", "value": hex(1)},
        ]},
    }

    def rpc(method, params):
        if method == "eth_blockNumber":
            return "0x64"
        return blocks[params[0]]

    created = scan_address(rpc, dep)
    assert [c.tx_hash for c in created] == ["0xaa"] and created[0].amount == Decimal("0.5")
    assert dep.last_scanned_block == 100
    assert scan_address(rpc, dep) == []  # nothing new, no duplicates
