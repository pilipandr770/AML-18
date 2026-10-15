import json
import re
from decimal import Decimal

import pyotp
import pytest

from app import create_app
from app.agent import journal
from app.agent.factory import AgentRuntime
from app.agent.models import AgentAuditEntry, AgentCase, AgentSettings, ModeConsent, OwnerAccount
from app.agent.operations import OperationError, RecordingExecutor, WebhookExecutor
from app.developer_portal.auth import generate_api_key, hash_api_key
from app.developer_portal.models import DeveloperProject
from app.extensions import db
from tests.conftest import TestConfig

PASSWORD = "correct horse battery staple"


class OwnerConfig(TestConfig):
    AGENT_ENABLED = True
    SECRET_KEY = "test-secret-key-not-for-production"


@pytest.fixture
def oapp():
    app = create_app(OwnerConfig)
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def project_key(oapp):
    key = generate_api_key()
    p = DeveloperProject(name="Owner Co", contact_email="o@example.com", api_key_prefix=key[:16],
                         api_key_hash=hash_api_key(key), webhook_url="https://client.example/hook")
    db.session.add(p)
    db.session.commit()
    return p, key


def _token(client):
    client.get("/owner/login")
    with client.session_transaction() as s:
        return s["csrf"]


def _post(client, url, **data):
    return client.post(url, data={"csrf_token": _token(client), **data})


def _signed_in(oapp, project_key):
    """Registers an owner, enrolls TOTP and returns (client, owner, totp)."""
    project, key = project_key
    client = oapp.test_client()
    r = _post(client, "/owner/register", api_key=key, email="owner@example.com", password=PASSWORD)
    assert r.status_code == 302
    owner = OwnerAccount.query.filter_by(email="owner@example.com").one()
    totp = pyotp.TOTP(owner.totp_secret)
    r = _post(client, "/owner/2fa", code=totp.now())
    assert r.status_code == 302
    return client, owner, totp


def test_owner_pages_404_when_agent_disabled(client):
    assert client.get("/owner/login").status_code == 404


def test_login_refused_without_secret_key():
    class NoSecret(OwnerConfig):
        SECRET_KEY = ""
    app = create_app(NoSecret)
    with app.app_context():
        db.create_all()
        assert app.test_client().get("/owner/login").status_code == 503


def test_dashboard_requires_login(oapp):
    c = oapp.test_client()
    for url in ("/owner/", "/owner/approvals", "/owner/policy", "/owner/reports"):
        assert c.get(url).status_code == 302


def test_post_without_csrf_is_rejected(oapp):
    assert oapp.test_client().post("/owner/login", data={"email": "a@b.c", "password": "x"}).status_code == 400


def test_register_requires_valid_project_key_and_strong_password(oapp, project_key):
    c = oapp.test_client()
    assert _post(c, "/owner/register", api_key="aml18_sk_wrong", email="a@b.co", password=PASSWORD).status_code == 400
    _p, key = project_key
    assert _post(c, "/owner/register", api_key=key, email="a@b.co", password="short").status_code == 400


def test_full_registration_2fa_and_login_flow(oapp, project_key):
    client, owner, totp = _signed_in(oapp, project_key)
    assert client.get("/owner/").status_code == 200
    client.post("/owner/logout", data={"csrf_token": _token(client)})
    assert client.get("/owner/").status_code == 302
    # password alone is not enough once 2FA is on
    assert _post(client, "/owner/login", email=owner.email, password=PASSWORD, code="000000").status_code == 401
    assert _post(client, "/owner/login", email=owner.email, password=PASSWORD, code=totp.now()).status_code == 302
    assert client.get("/owner/").status_code == 200


def test_lockout_after_repeated_failures(oapp, project_key):
    client, owner, totp = _signed_in(oapp, project_key)
    client.post("/owner/logout", data={"csrf_token": _token(client)})
    for _ in range(5):
        _post(client, "/owner/login", email=owner.email, password="wrong password!!", code="")
    r = _post(client, "/owner/login", email=owner.email, password=PASSWORD, code=totp.now())
    assert r.status_code == 429


def test_operate_requires_totp_and_consent_and_is_journaled(oapp, project_key):
    project, _ = project_key
    client, owner, totp = _signed_in(oapp, project_key)
    bad = _post(client, "/owner/mode", mode="operate", operations="release", consent="yes", code="000000")
    assert bad.status_code == 302
    assert AgentSettings.query.filter_by(developer_project_id=project.id).one().mode == "monitor"
    _post(client, "/owner/mode", mode="operate", operations="release", code=totp.now())  # no consent box
    assert AgentSettings.query.filter_by(developer_project_id=project.id).one().mode == "monitor"

    _post(client, "/owner/mode", mode="operate", operations="release", consent="yes", code=totp.now())
    row = AgentSettings.query.filter_by(developer_project_id=project.id).one()
    assert row.mode == "operate" and row.webhook_secret
    consent = ModeConsent.query.filter_by(developer_project_id=project.id, revoked_at=None).one()
    assert consent.operations == ["release"] and consent.owner_id == owner.id
    last = AgentAuditEntry.query.filter_by(event_type="mode_changed").order_by(AgentAuditEntry.seq.desc()).first()
    assert last.actor == "owner:owner@example.com" and last.payload["mode"] == "operate"
    assert journal.verify_chain(project.id) == (True, None)


def test_kill_switch_returns_to_monitor_and_revokes_consent(oapp, project_key):
    project, _ = project_key
    client, owner, totp = _signed_in(oapp, project_key)
    _post(client, "/owner/mode", mode="operate", operations="release", consent="yes", code=totp.now())
    _post(client, "/owner/kill")
    row = AgentSettings.query.filter_by(developer_project_id=project.id).one()
    assert row.mode == "monitor" and row.kill_switch is True
    assert ModeConsent.query.filter_by(developer_project_id=project.id, revoked_at=None).count() == 0
    # clearing needs the authenticator code and does NOT re-enable operate
    _post(client, "/owner/kill/clear", code="000000")
    assert AgentSettings.query.one().kill_switch is True
    _post(client, "/owner/kill/clear", code=totp.now())
    row = AgentSettings.query.one()
    assert row.kill_switch is False and row.mode == "monitor"


def test_policy_validation_and_versioning(oapp, project_key):
    project, _ = project_key
    client, _owner, _totp = _signed_in(oapp, project_key)
    _post(client, "/owner/policy", policy="{not json")
    _post(client, "/owner/policy", policy=json.dumps({"enabled_operations": ["move_funds"]}))
    assert AgentSettings.query.filter_by(developer_project_id=project.id).first() is None or \
        AgentSettings.query.one().policy_version == 1
    _post(client, "/owner/policy", policy=json.dumps({"enabled_operations": ["hold"], "allowed_assets": ["ETH"]}))
    row = AgentSettings.query.one()
    assert row.policy_version == 2 and row.policy["enabled_operations"] == ["hold"]
    assert AgentAuditEntry.query.filter_by(event_type="policy_changed").count() == 1


def _awaiting_case(project):
    c = AgentCase(developer_project_id=project.id, chain="sepolia", asset="ETH", amount=Decimal("1"),
                  deposit_address="0xd", counterparty_name="Ivan Ivanov", status="awaiting_human",
                  classification="needs_review", explanation="sanctions hit")
    db.session.add(c)
    db.session.commit()
    return c


def test_owner_approval_in_monitor_mode_records_only(oapp, project_key):
    project, _ = project_key
    client, _o, _t = _signed_in(oapp, project_key)
    case = _awaiting_case(project)
    ex = RecordingExecutor()
    oapp.extensions["agent_runtime"] = AgentRuntime(None, None, ex)
    _post(client, f"/owner/approvals/{case.public_id}", decision="approve", note="verified manually")
    db.session.refresh(case)
    assert case.status == "resolved" and case.resolved_by == "owner:owner@example.com"
    assert ex.executed == []  # MONITOR: nothing is sent to the client's system
    assert AgentAuditEntry.query.filter_by(event_type="owner_decision").one().payload["note"] == "verified manually"


def test_owner_approval_in_operate_mode_sends_instruction(oapp, project_key):
    project, _ = project_key
    client, _o, totp = _signed_in(oapp, project_key)
    _post(client, "/owner/policy", policy=json.dumps({"enabled_operations": ["release", "reject"]}))
    _post(client, "/owner/mode", mode="operate", operations=["release", "reject"], consent="yes", code=totp.now())
    case = _awaiting_case(project)
    ex = RecordingExecutor()
    oapp.extensions["agent_runtime"] = AgentRuntime(None, None, ex)
    _post(client, f"/owner/approvals/{case.public_id}", decision="reject")
    assert [e["operation"] for e in ex.executed] == ["reject"]


def test_reports_and_case_report_render_and_are_tenant_scoped(oapp, project_key):
    project, _ = project_key
    client, _o, _t = _signed_in(oapp, project_key)
    case = _awaiting_case(project)
    assert client.get("/owner/reports").status_code == 200
    page = client.get(f"/owner/reports/{case.public_id}")
    assert page.status_code == 200 and b"untrusted external text" in page.data
    other = DeveloperProject(name="x", contact_email="x@e.co", api_key_prefix="p", api_key_hash="z" * 64)
    db.session.add(other)
    db.session.commit()
    foreign = AgentCase(developer_project_id=other.id, chain="c", asset="ETH", amount=Decimal("1"), deposit_address="d")
    db.session.add(foreign)
    db.session.commit()
    assert client.get(f"/owner/reports/{foreign.public_id}").status_code == 404


def test_webhook_executor_signs_body_with_project_secret(oapp, project_key, monkeypatch):
    import hashlib
    import hmac

    project, _ = project_key
    db.session.add(AgentSettings(developer_project_id=project.id, mode="operate", policy={}, webhook_secret="s3cret"))
    db.session.commit()
    case = _awaiting_case(project)
    sent = {}

    class R:
        status_code = 200

    def fake_post(url, data=None, headers=None, timeout=None):
        sent.update(url=url, data=data, headers=headers)
        return R()

    monkeypatch.setattr("requests.post", fake_post)
    WebhookExecutor().execute("release", case, project)
    ts = re.search(r"t=(\d+)", sent["headers"]["X-AML18-Signature"]).group(1)
    expected = hmac.new(b"s3cret", f"{ts}.{sent['data']}".encode(), hashlib.sha256).hexdigest()
    assert sent["headers"]["X-AML18-Signature"].endswith(f"v1={expected}")
    assert sent["headers"]["Idempotency-Key"] == f"{case.public_id}:release"


def test_webhook_executor_without_config_raises(oapp, project_key):
    project, _ = project_key
    project.webhook_url = None
    with pytest.raises(OperationError):
        WebhookExecutor().execute("release", _awaiting_case(project), project)


def test_approvals_page_explains_why_a_case_is_waiting(oapp, project_key):
    project, _ = project_key
    client, _o, _t = _signed_in(oapp, project_key)
    case = _awaiting_case(project)
    journal.append(project.id, "policy_engine", "policy_verdict",
                   {"operation": "release", "outcome": "recommend_only", "reasons": ["inv_monitor_mode"],
                    "preview_outcome": "needs_human", "preview_reasons": ["over_require_human_above"]},
                   case.public_id)
    page = client.get("/owner/approvals").data.decode()
    assert "Why it is waiting for you" in page
    assert "above your &#39;require human above&#39; limit" in page or "above your 'require human above' limit" in page
