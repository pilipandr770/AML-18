"""Operator console for the hosted platform (/admin). Separate from the
per-client owner console: different accounts, different session key. It
shows platform health and tenant status, and offers a few safety actions
(kill switch, suspend, plan). It deliberately does NOT show clients' case
contents -- only counts and metadata. Every action is written to the
affected client's hash-chained journal and to the platform audit log."""

import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import pyotp
from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash

from app.agent import journal
from app.agent.models import MODE_MONITOR, AgentAuditEntry, AgentCase, AgentSettings, ModeConsent
from app.audit.models import AuditLog
from app.billing.models import UsageEvent
from app.developer_portal.models import DeveloperProject
from app.extensions import db
from app.platform_admin.models import PlatformOperator
from app.sanctions.freshness import get_freshness
from app.sanctions.models import ListSnapshot

admin_bp = Blueprint("platform_admin", __name__, url_prefix="/admin", template_folder="templates")

MAX_FAILED = 5
LOCK_MINUTES = 15
PLAN_STATUSES = ("free", "active", "trialing", "past_due", "canceled")


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@admin_bp.before_request
def _guard():
    if not current_app.config["PLATFORM_ADMIN_ENABLED"]:
        abort(404)
    if not current_app.config.get("SECRET_KEY"):
        return render_template("admin_secret_missing.html"), 503
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400)


@admin_bp.app_context_processor
def _inject():
    def admin_csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]
    return {"admin_csrf": admin_csrf}


def operator_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        op = db.session.get(PlatformOperator, session.get("operator_id") or 0)
        if op is None:
            return redirect(url_for("platform_admin.login"))
        g.operator = op
        return view(*args, **kwargs)
    return wrapped


def current_operator_or_none():
    """Used by other blueprints (e.g. the Travel Rule review console) to ask
    whether the visitor is a signed-in platform operator."""
    return db.session.get(PlatformOperator, session.get("operator_id") or 0)


def _record(project, action: str, detail: dict):
    actor = f"operator:{g.operator.email}"
    db.session.add(AuditLog(actor=actor, action=f"platform_{action}", target_type="developer_project",
                            target_id=project.public_id, detail=detail))
    db.session.commit()
    journal.append(project.id, actor, "operator_action", {"action": action, **detail})


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("admin_login.html")
    email = request.form.get("email", "").strip().lower()
    op = PlatformOperator.query.filter_by(email=email).first()
    error = ("Invalid credentials.", 401)
    if op is None:
        return render_template("admin_login.html", error=error[0]), error[1]
    locked = _aware(op.locked_until)
    if locked and locked > _utcnow():
        return render_template("admin_login.html", error="Too many attempts. Try again later."), 429
    ok = check_password_hash(op.password_hash, request.form.get("password", "")) and \
        pyotp.TOTP(op.totp_secret).verify(request.form.get("code", "").strip(), valid_window=1)
    if not ok:
        op.failed_attempts += 1
        if op.failed_attempts >= MAX_FAILED:
            op.locked_until = _utcnow() + timedelta(minutes=LOCK_MINUTES)
            op.failed_attempts = 0
        db.session.commit()
        return render_template("admin_login.html", error=error[0]), error[1]
    op.failed_attempts = 0
    op.locked_until = None
    db.session.add(AuditLog(actor=f"operator:{op.email}", action="platform_login", detail={}))
    db.session.commit()
    session.clear()
    session["operator_id"] = op.id
    return redirect(url_for("platform_admin.dashboard"))


@admin_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("platform_admin.login"))


def _tenant_row(p: DeveloperProject, month_start, since, verify: bool) -> dict:
    settings = AgentSettings.query.filter_by(developer_project_id=p.id).first()
    cases = AgentCase.query.filter(AgentCase.developer_project_id == p.id)
    row = {
        "project": p,
        "mode": settings.mode if settings else "-",
        "kill": bool(settings.kill_switch) if settings else False,
        "cases_30d": cases.filter(AgentCase.created_at >= since).count(),
        "pending": cases.filter_by(status="awaiting_human").count(),
        "usage_month": UsageEvent.query.filter(
            UsageEvent.developer_project_id == p.id, UsageEvent.occurred_at >= month_start).count(),
        "journal_entries": AgentAuditEntry.query.filter_by(developer_project_id=p.id).count(),
        "journal_ok": None,
    }
    if verify:
        row["journal_ok"] = journal.verify_chain(p.id)[0]
    return row


@admin_bp.get("/")
@operator_required
def dashboard():
    now = _utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    since = now - timedelta(days=30)
    verify = request.args.get("verify") == "1"
    projects = DeveloperProject.query.order_by(DeveloperProject.created_at.desc()).all()
    rows = [_tenant_row(p, month_start, since, verify) for p in projects]
    failed = (
        ListSnapshot.query.filter(ListSnapshot.status == "failed", ListSnapshot.fetched_at >= now - timedelta(days=7))
        .order_by(ListSnapshot.fetched_at.desc()).limit(10).all()
    )
    platform = {
        "projects": len(projects), "pending": sum(1 for p in projects if not p.is_active),
        "agent_enabled": current_app.config["AGENT_ENABLED"], "billing": current_app.config["BILLING_ENABLED"],
        "model": current_app.config["ANTHROPIC_MODEL"] or "(not set)",
        "llm_key": bool(current_app.config["ANTHROPIC_API_KEY"]),
        "approval_required": current_app.config["SIGNUP_APPROVAL_REQUIRED"],
    }
    return render_template("admin_dashboard.html", rows=rows, freshness=get_freshness(), failed=failed,
                           platform=platform, verified=verify,
                           max_age=current_app.config["SANCTIONS_STALENESS_WARNING_DAYS"])


@admin_bp.get("/tenants/<public_id>")
@operator_required
def tenant(public_id):
    p = DeveloperProject.query.filter_by(public_id=public_id).first_or_404()
    now = _utcnow()
    row = _tenant_row(p, now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now - timedelta(days=30), True)
    events = (
        AgentAuditEntry.query.filter_by(developer_project_id=p.id).order_by(AgentAuditEntry.seq.desc()).limit(40).all()
    )
    consent = ModeConsent.query.filter_by(developer_project_id=p.id, revoked_at=None).first()
    return render_template("admin_tenant.html", row=row, p=p, events=events, consent=consent, plans=PLAN_STATUSES)


def _project_or_404(public_id):
    return DeveloperProject.query.filter_by(public_id=public_id).first_or_404()


@admin_bp.post("/tenants/<public_id>/kill")
@operator_required
def kill(public_id):
    p = _project_or_404(public_id)
    from app.agent.settings import get_settings_row
    row = get_settings_row(p.id)
    row.kill_switch = True
    row.mode = MODE_MONITOR
    for c in ModeConsent.query.filter_by(developer_project_id=p.id, revoked_at=None).all():
        c.revoked_at = _utcnow()
    db.session.commit()
    _record(p, "kill_switch", {"reason": request.form.get("reason", "")[:300]})
    flash("Kill switch engaged for this client; consent revoked. Only the client's owner (with 2FA) can clear it.")
    return redirect(url_for("platform_admin.tenant", public_id=public_id))


@admin_bp.post("/tenants/<public_id>/active")
@operator_required
def set_active(public_id):
    p = _project_or_404(public_id)
    p.is_active = request.form.get("active") == "1"
    db.session.commit()
    _record(p, "activated" if p.is_active else "suspended", {"reason": request.form.get("reason", "")[:300]})
    flash("Client activated: API key works." if p.is_active else "Client suspended: API key rejected.")
    return redirect(url_for("platform_admin.tenant", public_id=public_id))


@admin_bp.post("/tenants/<public_id>/plan")
@operator_required
def set_plan(public_id):
    p = _project_or_404(public_id)
    status = request.form.get("plan_status")
    if status not in PLAN_STATUSES:
        abort(400)
    old, p.plan_status, p.plan_updated_at = p.plan_status, status, _utcnow()
    db.session.commit()
    _record(p, "plan_changed", {"from": old, "to": status})
    flash(f"Plan status set to {status}.")
    return redirect(url_for("platform_admin.tenant", public_id=public_id))
