"""Owner dashboard: the only place mode and policy can be changed, and only
after password + TOTP authentication. The agent has no route or tool that
reaches this module. Every state change is written to the hash-chained
journal with the owner as actor."""

import json
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import pyotp
import qrcode
import qrcode.image.svg
from flask import (
    Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, session, url_for,
)
from pydantic import ValidationError
from werkzeug.security import check_password_hash, generate_password_hash

from app.agent import journal
from app.agent.factory import get_runtime
from app.agent.models import (
    MODE_MONITOR, MODE_OPERATE, AgentAuditEntry, AgentCase, ModeConsent, OwnerAccount,
)
from app.agent.policy import ALL_OPERATIONS, Policy
from app.agent.settings import get_settings_row, load_effective
from app.developer_portal.auth import hash_api_key
from app.developer_portal.models import DeveloperProject
from app.extensions import db

owner_bp = Blueprint("owner", __name__, url_prefix="/owner", template_folder="templates")

MAX_FAILED = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 12


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---- guards ---------------------------------------------------------------

@owner_bp.before_request
def _guard():
    if not current_app.config["AGENT_ENABLED"]:
        abort(404)
    if not current_app.config.get("SECRET_KEY"):
        return render_template("owner_secret_missing.html"), 503
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400)


@owner_bp.app_context_processor
def _inject():
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]
    return {"csrf_token": csrf_token}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        owner_id = session.get("owner_id")
        owner = db.session.get(OwnerAccount, owner_id) if owner_id else None
        if owner is None or not owner.totp_enabled:
            return redirect(url_for("owner.login"))
        g.owner = owner
        g.project = db.session.get(DeveloperProject, owner.developer_project_id)
        return view(*args, **kwargs)
    return wrapped


def _actor():
    return f"owner:{g.owner.email}"


def _valid_totp(owner: OwnerAccount, code: str) -> bool:
    return bool(owner.totp_secret) and pyotp.TOTP(owner.totp_secret).verify((code or "").strip(), valid_window=1)


# ---- registration / login --------------------------------------------------

@owner_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("owner_register.html")
    api_key = request.form.get("api_key", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    project = DeveloperProject.query.filter_by(api_key_hash=hash_api_key(api_key), is_active=True).first() if api_key else None
    error = None
    if project is None:
        error = "Invalid project API key."
    elif "@" not in email or len(email) > 256:
        error = "Enter a valid email address."
    elif len(password) < MIN_PASSWORD:
        error = f"Password must be at least {MIN_PASSWORD} characters."
    elif OwnerAccount.query.filter_by(developer_project_id=project.id).first() or OwnerAccount.query.filter_by(email=email).first():
        error = "An owner account already exists for this project or email."
    if error:
        return render_template("owner_register.html", error=error), 400
    owner = OwnerAccount(
        developer_project_id=project.id, email=email, password_hash=generate_password_hash(password),
        totp_secret=pyotp.random_base32(), totp_enabled=False,
    )
    db.session.add(owner)
    db.session.commit()
    journal.append(project.id, f"owner:{email}", "owner_registered", {"email": email})
    session.clear()
    session["enroll_owner_id"] = owner.id
    return redirect(url_for("owner.enroll_2fa"))


@owner_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("owner_login.html")
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    code = request.form.get("code", "")
    owner = OwnerAccount.query.filter_by(email=email).first()
    generic = ("Invalid credentials.", 401)
    if owner is None:
        return render_template("owner_login.html", error=generic[0]), generic[1]
    locked = _aware(owner.locked_until)
    if locked and locked > _utcnow():
        return render_template("owner_login.html", error="Too many attempts. Try again later."), 429

    ok = check_password_hash(owner.password_hash, password)
    if ok and owner.totp_enabled:
        ok = _valid_totp(owner, code)
    if not ok:
        owner.failed_attempts += 1
        if owner.failed_attempts >= MAX_FAILED:
            owner.locked_until = _utcnow() + timedelta(minutes=LOCK_MINUTES)
            owner.failed_attempts = 0
            journal.append(owner.developer_project_id, "system", "owner_locked", {"email": email})
        db.session.commit()
        return render_template("owner_login.html", error=generic[0]), generic[1]

    owner.failed_attempts = 0
    owner.locked_until = None
    db.session.commit()
    session.clear()
    if not owner.totp_enabled:
        session["enroll_owner_id"] = owner.id
        return redirect(url_for("owner.enroll_2fa"))
    session["owner_id"] = owner.id
    journal.append(owner.developer_project_id, f"owner:{email}", "owner_login", {})
    return redirect(url_for("owner.feed"))


@owner_bp.route("/2fa", methods=["GET", "POST"])
def enroll_2fa():
    owner = db.session.get(OwnerAccount, session.get("enroll_owner_id") or 0)
    if owner is None:
        return redirect(url_for("owner.login"))
    uri = pyotp.TOTP(owner.totp_secret).provisioning_uri(name=owner.email, issuer_name="AML+18 Agent")
    if request.method == "POST":
        if _valid_totp(owner, request.form.get("code", "")):
            owner.totp_enabled = True
            db.session.commit()
            journal.append(owner.developer_project_id, f"owner:{owner.email}", "owner_2fa_enabled", {})
            session.clear()
            session["owner_id"] = owner.id
            return redirect(url_for("owner.feed"))
        return render_template("owner_2fa.html", secret=owner.totp_secret, error="Wrong code, try again."), 400
    return render_template("owner_2fa.html", secret=owner.totp_secret)


@owner_bp.get("/2fa/qr.svg")
def qr():
    owner = db.session.get(OwnerAccount, session.get("enroll_owner_id") or 0)
    if owner is None:
        abort(404)
    uri = pyotp.TOTP(owner.totp_secret).provisioning_uri(name=owner.email, issuer_name="AML+18 Agent")
    svg = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage).to_string().decode("utf-8")
    return Response(svg, mimetype="image/svg+xml")


@owner_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("owner.login"))


# ---- dashboard pages --------------------------------------------------------

def _describe(e: AgentAuditEntry) -> str:
    p = e.payload or {}
    if e.event_type == "policy_verdict":
        return f"{p.get('operation')} -> {p.get('outcome')} ({', '.join(p.get('reasons', []))})"
    if e.event_type == "decision_recorded":
        return f"classified {p.get('final')} (floor {p.get('floor')})"
    if e.event_type == "deterministic_checks":
        return f"sanctions: {p.get('screening_decision')}, funds verified: {p.get('funds_verified')}"
    if e.event_type == "case_finalized":
        return f"status {p.get('status')}"
    if e.event_type == "owner_notified":
        return f"[{p.get('severity')}] {p.get('message')}"
    if e.event_type == "operation_executed":
        return f"{p.get('operation')} sent to client system"
    return ", ".join(f"{k}={v}" for k, v in list(p.items())[:3] if not isinstance(v, (dict, list)))[:160]


@owner_bp.get("/")
@login_required
def feed():
    entries = (
        AgentAuditEntry.query.filter_by(developer_project_id=g.project.id)
        .order_by(AgentAuditEntry.seq.desc()).limit(60).all()
    )
    mode, _policy, kill = load_effective(g.project.id)
    ok, bad = journal.verify_chain(g.project.id)
    return render_template("owner_feed.html", entries=entries, describe=_describe, mode=mode, kill=kill,
                           chain_ok=ok, chain_bad=bad)


@owner_bp.get("/approvals")
@login_required
def approvals():
    cases = (
        AgentCase.query.filter_by(developer_project_id=g.project.id, status="awaiting_human")
        .order_by(AgentCase.created_at.desc()).all()
    )
    mode, _policy, kill = load_effective(g.project.id)
    return render_template("owner_approvals.html", cases=cases, mode=mode, kill=kill)


@owner_bp.post("/approvals/<case_id>")
@login_required
def decide(case_id):
    case = AgentCase.query.filter_by(public_id=case_id, developer_project_id=g.project.id).first_or_404()
    if case.status != "awaiting_human":
        abort(409)
    decision = request.form.get("decision")
    if decision not in ("approve", "reject"):
        abort(400)
    note = request.form.get("note", "")[:500]
    operation = "release" if decision == "approve" else "reject"
    case.status = "resolved"
    case.resolution = "cleared" if decision == "approve" else "blocked"
    case.resolved_by = _actor()
    case.resolved_at = _utcnow()
    db.session.commit()
    journal.append(g.project.id, _actor(), "owner_decision",
                   {"decision": decision, "note": note, "operation": operation}, case.public_id)

    mode, policy, kill = load_effective(g.project.id)
    consent = ModeConsent.query.filter_by(developer_project_id=g.project.id, revoked_at=None).first()
    if mode == MODE_OPERATE and not kill and operation in policy.enabled_operations and consent and operation in consent.operations:
        try:
            result = get_runtime(current_app).executor.execute(operation, case, g.project)
            journal.append(g.project.id, "system", "operation_executed",
                           {"operation": operation, "amount": str(case.amount), "result": result, "approved_by": _actor()},
                           case.public_id)
            flash(f"Decision recorded and '{operation}' sent to your system.")
        except Exception as exc:
            journal.append(g.project.id, "system", "operation_failed", {"operation": operation, "error": type(exc).__name__}, case.public_id)
            flash("Decision recorded, but delivery to your system failed. See the journal.")
    else:
        flash("Decision recorded. No instruction was sent (monitor mode, operation not enabled, or kill switch).")
    return redirect(url_for("owner.approvals"))


SAMPLE_POLICY = {
    "enabled_operations": ["release", "hold"],
    "max_amount_per_operation": "1000",
    "daily_cap": "5000",
    "allowed_assets": ["ETH"],
    "allowed_chains": ["sepolia"],
    "blocked_jurisdictions": [],
    "require_human_above": "500",
    "new_counterparty_rule": "require_human",
}


@owner_bp.get("/policy")
@login_required
def policy_page():
    row = get_settings_row(g.project.id)
    consent = ModeConsent.query.filter_by(developer_project_id=g.project.id, revoked_at=None).first()
    policy_json = json.dumps(row.policy or SAMPLE_POLICY, indent=2)
    return render_template("owner_policy.html", row=row, policy_json=policy_json, consent=consent,
                           operations=ALL_OPERATIONS)


@owner_bp.post("/policy")
@login_required
def save_policy():
    try:
        policy = Policy.model_validate(json.loads(request.form.get("policy", "")))
    except (ValueError, ValidationError) as exc:
        flash(f"Policy rejected: {str(exc)[:300]}")
        return redirect(url_for("owner.policy_page"))
    row = get_settings_row(g.project.id)
    row.policy = json.loads(policy.model_dump_json())
    row.policy_version += 1
    db.session.commit()
    journal.append(g.project.id, _actor(), "policy_changed", {"version": row.policy_version, "policy": row.policy})
    flash("Policy saved.")
    return redirect(url_for("owner.policy_page"))


@owner_bp.post("/mode")
@login_required
def set_mode():
    target = request.form.get("mode")
    row = get_settings_row(g.project.id)
    if target == MODE_MONITOR:
        row.mode = MODE_MONITOR
        for c in ModeConsent.query.filter_by(developer_project_id=g.project.id, revoked_at=None).all():
            c.revoked_at = _utcnow()
        db.session.commit()
        journal.append(g.project.id, _actor(), "mode_changed", {"mode": MODE_MONITOR})
        flash("Switched to MONITOR. The agent only records recommendations.")
        return redirect(url_for("owner.policy_page"))
    if target != MODE_OPERATE:
        abort(400)
    if not _valid_totp(g.owner, request.form.get("code", "")):
        flash("Authentication code is wrong. Mode not changed.")
        return redirect(url_for("owner.policy_page"))
    ops = [o for o in request.form.getlist("operations") if o in ALL_OPERATIONS]
    if not ops or request.form.get("consent") != "yes":
        flash("Select at least one operation and confirm consent to enable OPERATE.")
        return redirect(url_for("owner.policy_page"))
    row.mode = MODE_OPERATE
    row.kill_switch = False
    if not row.webhook_secret:
        row.webhook_secret = secrets.token_hex(24)
        flash(f"Webhook signing secret (shown once, store it in your system): {row.webhook_secret}")
    for c in ModeConsent.query.filter_by(developer_project_id=g.project.id, revoked_at=None).all():
        c.revoked_at = _utcnow()
    db.session.add(ModeConsent(developer_project_id=g.project.id, owner_id=g.owner.id, operations=ops))
    db.session.commit()
    journal.append(g.project.id, _actor(), "mode_changed", {"mode": MODE_OPERATE, "consented_operations": ops})
    flash("OPERATE enabled for the selected operations, within your policy.")
    return redirect(url_for("owner.policy_page"))


@owner_bp.post("/kill")
@login_required
def kill():
    row = get_settings_row(g.project.id)
    row.kill_switch = True
    row.mode = MODE_MONITOR
    for c in ModeConsent.query.filter_by(developer_project_id=g.project.id, revoked_at=None).all():
        c.revoked_at = _utcnow()
    db.session.commit()
    journal.append(g.project.id, _actor(), "kill_switch_engaged", {})
    flash("Kill switch engaged. The agent is back in MONITOR and cannot act.")
    return redirect(request.referrer or url_for("owner.feed"))


@owner_bp.post("/kill/clear")
@login_required
def clear_kill():
    if not _valid_totp(g.owner, request.form.get("code", "")):
        flash("Authentication code is wrong.")
        return redirect(url_for("owner.policy_page"))
    row = get_settings_row(g.project.id)
    row.kill_switch = False
    db.session.commit()
    journal.append(g.project.id, _actor(), "kill_switch_cleared", {})
    flash("Kill switch cleared. The agent stays in MONITOR until you enable OPERATE again.")
    return redirect(url_for("owner.policy_page"))


@owner_bp.get("/reports")
@login_required
def reports():
    cases = AgentCase.query.filter_by(developer_project_id=g.project.id).order_by(AgentCase.created_at.desc()).limit(100).all()
    return render_template("owner_reports.html", cases=cases)


@owner_bp.get("/reports/<case_id>")
@login_required
def report_detail(case_id):
    case = AgentCase.query.filter_by(public_id=case_id, developer_project_id=g.project.id).first_or_404()
    events = (
        AgentAuditEntry.query.filter_by(developer_project_id=g.project.id, case_public_id=case.public_id)
        .order_by(AgentAuditEntry.seq).all()
    )
    return render_template("owner_report.html", case=case, events=events, describe=_describe,
                           jurisdiction=g.project.jurisdiction)
