import pytest

from app import create_app
from app.agent.demo import run_demo
from app.extensions import db
from app.sanctions.ingest import ingest_source
from tests.conftest import TestConfig
from tests.test_engine import _FixtureOFACSource


class DemoConfig(TestConfig):
    AGENT_ENABLED = True
    SECRET_KEY = "demo-test-secret"
    SCREENING_REJECT_THRESHOLD = 99  # makes "Evan Ivanov" an uncorroborated mid-band (fuzzy) hit


@pytest.fixture(scope="module")
def results():
    app = create_app(DemoConfig)
    with app.app_context():
        db.create_all()
        ingest_source(_FixtureOFACSource())
        yield run_demo(app, out=lambda *_: None)


def _by_case(rows):
    return {r["case"].split(" ", 1)[0]: r for r in rows}


def test_monitor_mode_five_cases_and_no_instruction_ever_sent(results):
    m = _by_case(results["monitor"])
    assert m["1"]["classification"] == "clear" and m["1"]["status"] == "auto_cleared"
    assert m["2"]["status"] == "awaiting_human" and m["2"]["sanctions"] == "review"
    assert m["3"]["status"] == "awaiting_human"
    assert m["4"]["status"] == "awaiting_human"  # policy preview: over the limit
    assert m["5"]["status"] == "awaiting_human" and m["5"]["operation_sent"] is False
    assert all(r["operation_sent"] is False for r in results["monitor"])


def test_operate_mode_acts_only_on_the_clean_case(results):
    o = _by_case(results["operate"])
    assert o["1"]["operation_sent"] is True and o["1"]["status"] == "operated"
    for k in ("2", "3", "4", "5"):
        assert o[k]["operation_sent"] is False and o[k]["status"] == "awaiting_human"
    assert o["4"]["reasons"] is None or "over_require_human_above" in (o["4"]["reasons"] or [])


def test_exactly_one_instruction_and_intact_journal(results):
    assert [x["operation"] for x in results["operations_sent"]] == ["release"]
    assert results["journal_ok"] is True

