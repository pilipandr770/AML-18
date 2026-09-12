"""The rest of the test suite bypasses Alembic entirely (the `app` fixture
uses db.create_all() against an in-memory sqlite), so it would never catch
drift between the models and the actual migration files. This test runs
the real `flask db upgrade` command end-to-end against a throwaway on-disk
sqlite database and inspects the resulting schema.

Run as a real subprocess, not in-process via flask_migrate.upgrade():
migrations/env.py calls logging.config.fileConfig(...), which reconfigures
the *global* root logger for the whole process -- running that in-process
during a pytest session corrupts logging state for every test that runs
afterward (this was caught the hard way: it broke an unrelated caplog-based
webhook test purely by import/execution order). A subprocess throws that
side effect away when it exits, exactly like the real docker entrypoint
already runs `flask db upgrade` as its own process.
"""

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

COMPLIANCE_SERVICE_DIR = Path(__file__).resolve().parent.parent


def test_migrations_upgrade_head_creates_expected_schema(tmp_path):
    db_path = tmp_path / "migration_smoke_test.db"
    env = {
        **os.environ,
        "FLASK_APP": "wsgi.py",
        "DATABASE_URL": f"sqlite:///{db_path}",
    }

    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=str(COMPLIANCE_SERVICE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"flask db upgrade failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    assert "billing_usage_events" in tables

    for table, expected_column in (
        ("wallet_ownership_challenges", "developer_project_id"),
        ("wallet_ownership_verifications", "developer_project_id"),
        ("age_verification_sessions", "developer_project_id"),
        ("age_verifications", "developer_project_id"),
    ):
        columns = {c["name"] for c in inspector.get_columns(table)}
        assert expected_column in columns, f"{table} is missing {expected_column}"

    developer_project_columns = {c["name"] for c in inspector.get_columns("developer_projects")}
    for expected in ("plan_status", "stripe_customer_id", "stripe_subscription_id", "plan_updated_at"):
        assert expected in developer_project_columns
