from datetime import datetime, timedelta, timezone

from app.billing.metering import get_current_period_usage, record_usage
from app.billing.models import UsageEvent
from app.extensions import db


def test_record_usage_and_get_current_period_usage(app):
    with app.app_context():
        record_usage(1, module="wallet_ownership", endpoint="wallet_ownership.create_challenge_route")
        record_usage(1, module="wallet_ownership", endpoint="wallet_ownership.create_challenge_route")

        assert get_current_period_usage(1) == 2


def test_usage_is_isolated_per_project(app):
    with app.app_context():
        record_usage(1, module="ageverify", endpoint="ageverify.age_verify_check")
        record_usage(2, module="ageverify", endpoint="ageverify.age_verify_check")
        record_usage(2, module="ageverify", endpoint="ageverify.age_verify_check")

        assert get_current_period_usage(1) == 1
        assert get_current_period_usage(2) == 2


def test_usage_before_period_start_is_not_counted(app):
    with app.app_context():
        now = datetime.now(timezone.utc)
        last_month = now.replace(day=1) - timedelta(days=1)

        db.session.add(UsageEvent(developer_project_id=1, module="ageverify", endpoint="x", occurred_at=last_month))
        db.session.commit()

        assert get_current_period_usage(1, now=now) == 0

        record_usage(1, module="ageverify", endpoint="x")
        assert get_current_period_usage(1, now=now) == 1
