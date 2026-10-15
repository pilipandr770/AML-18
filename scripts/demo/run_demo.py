#!/usr/bin/env python3
"""One-command demo of the AML+18 compliance agent.

    python scripts/demo/run_demo.py            # real model if ANTHROPIC_API_KEY is in .env, else offline stand-in
    python scripts/demo/run_demo.py --offline  # never calls an LLM
    python scripts/demo/run_demo.py --serve    # keep the owner console running afterwards on :8310

Runs five cases (clean, sanctions match, ambiguous match, over the limit,
prompt injection in the memo) through the real pipeline in MONITOR and then
OPERATE mode, against a throwaway SQLite database, a mock ledger and a small
bundled sanctions fixture. No real funds, no mainnet, nothing leaves your
machine except the model call (when a key is configured)."""

import argparse
import os
import re
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "compliance-service"
sys.path.insert(0, str(SERVICE))


def _env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    env_file = ROOT / ".env"
    if env_file.exists():
        m = re.search(rf"^{name}=(.+)$", env_file.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="use the deterministic offline stand-in instead of the model")
    ap.add_argument("--serve", action="store_true", help="after the run, serve the owner console on :8310")
    args = ap.parse_args()

    from app import create_app
    from app.agent.demo import OWNER_EMAIL, OWNER_PASSWORD, OfflineDemoLLM, run_demo
    from app.agent.llm import AnthropicClient
    from app.agent.models import OwnerAccount
    from app.config import Config
    from app.extensions import db
    from app.sanctions.ingest import ingest_source
    from tests.test_engine import _FixtureOFACSource  # bundled fixture list (Ivan Ivanov etc.)

    workdir = Path(tempfile.mkdtemp(prefix="aml18-demo-"))

    class DemoConfig(Config):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(workdir / 'demo.db').as_posix()}"
        AGENT_ENABLED = True
        SECRET_KEY = secrets.token_hex(32)
        SCREENING_REJECT_THRESHOLD = 99  # puts the fuzzy demo name in the uncorroborated mid band
        ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
        ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL")

    app = create_app(DemoConfig)
    with app.app_context():
        db.create_all()
        ingest_source(_FixtureOFACSource())

        llm = OfflineDemoLLM()
        if not args.offline and DemoConfig.ANTHROPIC_API_KEY and DemoConfig.ANTHROPIC_MODEL:
            llm = AnthropicClient(DemoConfig.ANTHROPIC_API_KEY, DemoConfig.ANTHROPIC_MODEL, 30, 60)
            print(f"LLM: {DemoConfig.ANTHROPIC_MODEL}")
        else:
            print("LLM: offline stand-in (no model call)")

        results = run_demo(app, llm)
        if not results["journal_ok"]:
            return 1

        if args.serve:
            import pyotp

            owner = OwnerAccount.query.filter_by(email=OWNER_EMAIL).one()
            print("\nOwner console: http://127.0.0.1:8310/owner/login")
            print(f"  email: {OWNER_EMAIL}\n  password: {OWNER_PASSWORD}")
            print(f"  authenticator secret (add to any TOTP app): {owner.totp_secret}")
            print(f"  current code: {pyotp.TOTP(owner.totp_secret).now()}  (changes every 30s)")
            app.run(host="127.0.0.1", port=8310, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
