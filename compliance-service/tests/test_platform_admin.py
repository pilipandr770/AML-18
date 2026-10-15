import pyotp
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.agent import journal
from app.agent.models import AgentAuditEntry, AgentSettings, ModeConsent
from app.audit.models import AuditLog
from app.developer_portal.auth import generate_api_key, hash_api_key
from app.developer_portal.models import DeveloperProject
from app.extensions import db
from app.platform_admin.models import PlatformOperator
from tests.conftest import TestConfig

PASSWORD = "operator password long enough"


class HostedConfig(TestConfig):
    AGENT_ENABLED = True
    PLATFORM_ADMIN_ENABLED = True
    SECRET_KEY = "hosted-test-secret"
    REVIEW_UI_REQUIRE_OPERATOR = True


@pytest.fixture
def happ():
    app = create_app(HostedConfig)
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def operator(happ):
    secret = pyotp.random_base32()
    op = PlatformOperator(email="ops@example.com", password_hash=generate_password_hash(PASSWORD), totp_secret=secret)
    db.session.add(op)
    db.session.commit()
    return op, pyotp.TOTP(secret)


def _token(client):
    client.get("/admin/login")
    with client.session_transaction() as s:
        return s["csrf"]


def _post(client, url, **data):
    return client.post(url, data={"csrf_token": _token(client), **data})


def _login(client, op, totp, password=PASSWORD, code=None):
    return _post(client, "/admin/login", email=op.email, password=password, code=code or totp.now())


def _tenant(name="Pilot Co", active=True):
    key = generate_api_key()
    p = DeveloperProject(name=name, contact_email="p@example.com", api_key_prefix=key[:16],
                         api_key_hash=hash_api_key(key), is_active=active)
    db.session.add(p)
    db.session.commit()
    return p, {"Authorization": f"Bearer {key}"}


def test_admin_is_404_when_disabled(client):
    assert client.get("/admin/login").status_code == 404


def test_dashboard_requires_login_and_totp(happ, operator):
    op, totp = operator
    c = happ.test_client()
    assert c.get("/admin/").status_code == 302
    assert _login(c, op, totp, code="000000").status_code == 401
    assert _login(c, op, totp, password="wrong password!!!").status_code == 401
    assert _login(c, op, totp).status_code == 302
    assert c.get("/admin/").status_code == 200


def test_operator_lockout_after_failures(happ, operator):
    op, totp = operator
    c = happ.test_client()
    for _ in range(5):
        _login(c, op, totp, code="000000")
    assert _login(c, op, totp).status_code == 429


def test_post_without_csrf_rejected(happ):
    assert happ.test_client().post("/admin/login", data={"email": "a", "password": "b", "code": "1"}).status_code == 400


def test_client_owner_session_does_not_grant_operator_access(happ):
    c = happ.test_client()
    with c.session_transaction() as s:
        s["owner_id"] = 1
    assert c.get("/admin/").status_code == 302


def test_dashboard_lists_tenants_and_sources(happ, operator):
    op, totp = operator
    _tenant("Visible Client")
    c = happ.test_client()
    _login(c, op, totp)
    page = c.get("/admin/?verify=1").data.decode()
    assert "Visible Client" in page and "Sanctions lists" in page and "TAMPERED" not in page


def test_kill_switch_by_operator_is_journaled_and_revokes_consent(happ, operator):
    op, totp = operator
    p, _h = _tenant()
    db.session.add(AgentSettings(developer_project_id=p.id, mode="operate", policy={}))
    db.session.add(ModeConsent(developer_project_id=p.id, owner_id=1, operations=["release"]))
    db.session.commit()
    c = happ.test_client()
    _login(c, op, totp)
    _post(c, f"/admin/tenants/{p.public_id}/kill", reason="suspicious volume")
    row = AgentSettings.query.filter_by(developer_project_id=p.id).one()
    assert row.kill_switch is True and row.mode == "monitor"
    assert ModeConsent.query.filter_by(developer_project_id=p.id, revoked_at=None).count() == 0
    entry = AgentAuditEntry.query.filter_by(event_type="operator_action").one()
    assert entry.actor == "operator:ops@example.com" and entry.payload["action"] == "kill_switch"
    assert journal.verify_chain(p.id) == (True, None)
    assert AuditLog.query.filter_by(action="platform_kill_switch").count() == 1


def test_suspending_a_client_rejects_its_api_key(happ, operator):
    op, totp = operator
    p, headers = _tenant()
    client = happ.test_client()
    assert client.get("/wallet-ownership/requirement?transfer_amount_eur=1", headers=headers).status_code == 200
    _login(client, op, totp)
    _post(client, f"/admin/tenants/{p.public_id}/active", active="0", reason="abuse")
    assert client.get("/wallet-ownership/requirement?transfer_amount_eur=1", headers=headers).status_code == 401
    _post(client, f"/admin/tenants/{p.public_id}/active", active="1")
    assert client.get("/wallet-ownership/requirement?transfer_amount_eur=1", headers=headers).status_code == 200


def test_plan_change_validates_input(happ, operator):
    op, totp = operator
    p, _h = _tenant()
    c = happ.test_client()
    _login(c, op, totp)
    assert _post(c, f"/admin/tenants/{p.public_id}/plan", plan_status="bogus").status_code == 400
    _post(c, f"/admin/tenants/{p.public_id}/plan", plan_status="active")
    db.session.refresh(p)
    assert p.plan_status == "active"


def test_tenant_page_shows_metadata_but_not_case_contents(happ, operator):
    from decimal import Decimal
    from app.agent.models import AgentCase
    op, totp = operator
    p, _h = _tenant()
    db.session.add(AgentCase(developer_project_id=p.id, chain="c", asset="ETH", amount=Decimal("1"), deposit_address="d",
                             counterparty_name="SECRET COUNTERPARTY NAME", memo="SECRET MEMO"))
    db.session.commit()
    c = happ.test_client()
    _login(c, op, totp)
    page = c.get(f"/admin/tenants/{p.public_id}").data.decode()
    assert "Cases (30d)" in page and "SECRET COUNTERPARTY NAME" not in page and "SECRET MEMO" not in page


def test_review_ui_requires_operator_on_hosted_deployments(happ, operator):
    op, totp = operator
    c = happ.test_client()
    assert c.get("/review/").status_code == 302
    assert c.get("/review/health").status_code == 200
    _login(c, op, totp)
    assert c.get("/review/").status_code == 200


def test_review_ui_forbidden_if_operator_console_is_off():
    class Cfg(HostedConfig):
        PLATFORM_ADMIN_ENABLED = False
    app = create_app(Cfg)
    with app.app_context():
        db.create_all()
        assert app.test_client().get("/review/").status_code == 403


def test_signup_approval_keeps_new_projects_inactive_until_approved(happ, operator):
    op, totp = operator
    happ.config["SIGNUP_APPROVAL_REQUIRED"] = True
    c = happ.test_client()
    r = c.post("/developer/signup", data={"name": "Applicant", "contact_email": "a@example.com"})
    assert r.status_code == 200 and b"awaits approval" in r.data
    import re
    key = re.search(rb"aml18_sk_[A-Za-z0-9_-]+", r.data).group(0).decode()
    h = {"Authorization": f"Bearer {key}"}
    assert c.get("/wallet-ownership/requirement?transfer_amount_eur=1", headers=h).status_code == 401
    p = DeveloperProject.query.filter_by(name="Applicant").one()
    _login(c, op, totp)
    _post(c, f"/admin/tenants/{p.public_id}/active", active="1")
    assert c.get("/wallet-ownership/requirement?transfer_amount_eur=1", headers=h).status_code == 200


def test_signup_is_rate_limited_per_address(happ):
    from app.developer_portal import routes
    routes._signup_hits.clear()
    happ.config["SIGNUP_RATE_LIMIT_PER_HOUR"] = 2
    c = happ.test_client()
    for i in range(2):
        assert c.post("/developer/signup", data={"name": f"P{i}", "contact_email": "a@example.com"}).status_code == 200
    assert c.post("/developer/signup", data={"name": "P3", "contact_email": "a@example.com"}).status_code == 429


def test_agent_daily_case_cap(happ):
    from app.agent.factory import AgentRuntime
    from app.agent.llm import ScriptedLLM
    from app.agent.chain import MockLedger
    from app.agent.operations import RecordingExecutor
    happ.extensions["agent_runtime"] = AgentRuntime(ScriptedLLM([]), MockLedger(1), RecordingExecutor())
    happ.config["AGENT_MAX_CASES_PER_DAY"] = 1
    p, h = _tenant()
    c = happ.test_client()
    body = {"chain": "sepolia", "asset": "ETH", "amount": "1", "deposit_address": "0xd", "tx_hash": "0x1"}
    assert c.post("/agent/transfers", json=body, headers=h).status_code == 201
    assert c.post("/agent/transfers", json={**body, "tx_hash": "0x2"}, headers=h).status_code == 429
