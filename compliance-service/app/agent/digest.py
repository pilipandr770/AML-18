"""Daily digest for the owner: summary + case table as HTML and CSV, with
optional email delivery over SMTP (only if SMTP_HOST is configured)."""

import csv
import io
import smtplib
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape

from app.agent import journal
from app.agent.jurisdiction import profile_for
from app.agent.models import AgentAuditEntry, AgentCase
from app.sanctions.freshness import get_freshness


def build(project, hours: int = 24) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    cases = [
        c for c in AgentCase.query.filter_by(developer_project_id=project.id).order_by(AgentCase.created_at.desc()).all()
        if (c.created_at if c.created_at.tzinfo else c.created_at.replace(tzinfo=timezone.utc)) >= since
    ]
    ops = [
        e for e in AgentAuditEntry.query.filter_by(developer_project_id=project.id, event_type="operation_executed").all()
        if (e.occurred_at if e.occurred_at.tzinfo else e.occurred_at.replace(tzinfo=timezone.utc)) >= since
    ]
    ok, bad = journal.verify_chain(project.id)
    return {
        "project": project.name, "hours": hours, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total": len(cases), "by_classification": dict(Counter(c.classification or "unclassified" for c in cases)),
        "pending": [c for c in cases if c.status == "awaiting_human"], "operations_executed": len(ops),
        "freshness": get_freshness(), "journal_ok": ok, "journal_bad_seq": bad, "cases": cases,
        "jurisdiction": profile_for(project.jurisdiction),
    }


def to_csv(d: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["case_id", "created_utc", "amount", "asset", "chain", "tx_hash", "classification", "status", "sanctions", "explanation"])
    for c in d["cases"]:
        w.writerow([c.public_id, c.created_at.strftime("%Y-%m-%d %H:%M:%S"), c.amount, c.asset, c.chain, c.tx_hash or "",
                    c.classification or "", c.status, c.deterministic_decision or "", (c.explanation or "").replace("\n", " ")])
    return out.getvalue()


def to_html(d: dict) -> str:
    rows = "".join(
        f"<tr><td>{escape(c.created_at.strftime('%Y-%m-%d %H:%M'))}</td><td>{escape(str(c.amount))} {escape(c.asset)}</td>"
        f"<td>{escape(c.classification or '-')}</td><td>{escape(c.status)}</td><td>{escape((c.explanation or '')[:160])}</td></tr>"
        for c in d["cases"]
    )
    fresh = "".join(f"<li>{escape(s['source'])}: {s['record_count']} records, age {s['age_days']} day(s)</li>" for s in d["freshness"])
    summary = ", ".join(f"{escape(k)}: {v}" for k, v in d["by_classification"].items()) or "no cases"
    integrity = "verified" if d["journal_ok"] else f"TAMPERED at entry #{d['journal_bad_seq']}"
    return (
        f"<h2>AML+18 agent digest – {escape(d['project'])}</h2><p>Last {d['hours']}h, generated {d['generated_at']}</p>"
        f"<p><b>{d['total']}</b> cases ({summary}); <b>{len(d['pending'])}</b> awaiting your decision; "
        f"<b>{d['operations_executed']}</b> operations sent to your system.</p>"
        f"<p>Journal integrity: <b>{integrity}</b></p><h3>Sanctions lists</h3><ul>{fresh}</ul>"
        f"<table border='1' cellpadding='4' cellspacing='0'><tr><th>Time (UTC)</th><th>Amount</th><th>Class</th><th>Status</th><th>Why</th></tr>{rows}</table>"
        f"<p style='color:#666'>{escape(' '.join(d['jurisdiction']['notes']))}</p>"
    )


def send_email(config, to_addr: str, d: dict) -> bool:
    """Sends the digest if SMTP is configured; returns whether it was sent."""
    host = config.get("SMTP_HOST")
    if not host:
        return False
    msg = EmailMessage()
    msg["Subject"] = f"AML+18 agent digest – {d['project']}"
    msg["From"] = config.get("SMTP_FROM") or "agent@localhost"
    msg["To"] = to_addr
    msg.set_content("HTML digest attached inline; CSV attached.")
    msg.add_alternative(to_html(d), subtype="html")
    msg.add_attachment(to_csv(d).encode("utf-8"), maintype="text", subtype="csv", filename="digest.csv")
    with smtplib.SMTP(host, int(config.get("SMTP_PORT", 587)), timeout=15) as s:
        if config.get("SMTP_USER"):
            s.starttls()
            s.login(config["SMTP_USER"], config.get("SMTP_PASSWORD", ""))
        s.send_message(msg)
    return True
