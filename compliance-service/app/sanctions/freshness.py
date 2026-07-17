from datetime import datetime, timezone

from app.sanctions.models import ListSnapshot


def get_freshness() -> list[dict]:
    """One row per ingested source, describing its current *active*
    snapshot's age. Rendered in the compliance-officer UI header on every
    page (see review_ui/templates/base.html) -- a screening decision made
    against a stale list is a real compliance gap, not just a UI nicety,
    so this is deliberately always visible rather than tucked into a
    settings page."""
    sources = sorted(
        row[0] for row in ListSnapshot.query.with_entities(ListSnapshot.source).distinct()
    )
    now = datetime.now(timezone.utc)

    results = []
    for source in sources:
        snapshot = (
            ListSnapshot.query
            .filter_by(source=source, status="active")
            .order_by(ListSnapshot.activated_at.desc())
            .first()
        )
        if snapshot is None or snapshot.activated_at is None:
            results.append({
                "source": source,
                "activated_at": None,
                "age_days": None,
                "record_count": None,
            })
            continue

        activated_at = snapshot.activated_at
        if activated_at.tzinfo is None:
            # SQLite drops tzinfo on round-trip even for DateTime(timezone=True)
            # columns; the value was always written in UTC.
            activated_at = activated_at.replace(tzinfo=timezone.utc)

        results.append({
            "source": source,
            "activated_at": activated_at,
            "age_days": (now - activated_at).days,
            "record_count": snapshot.record_count,
        })
    return results
