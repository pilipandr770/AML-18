import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:////data/compliance.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Shared secret Envoy uses to sign its outgoing webhook calls (see
    # `envoy hmackey`). Both must be set for auth verification to run;
    # if either is missing the webhook route refuses all requests rather
    # than silently accepting unauthenticated calls.
    WEBHOOK_AUTH_KEY_ID = os.environ.get("WEBHOOK_AUTH_KEY_ID", "")
    WEBHOOK_AUTH_KEY_SECRET = os.environ.get("WEBHOOK_AUTH_KEY_SECRET", "")

    # If true, sign our replies with a Server-Authorization header using the
    # same shared secret, for Envoy's RequireServerAuth check.
    WEBHOOK_SIGN_REPLIES = os.environ.get("WEBHOOK_SIGN_REPLIES", "false").lower() == "true"

    # Fuzzy-match score thresholds (0-100, rapidfuzz scale).
    SCREENING_REVIEW_THRESHOLD = int(os.environ.get("SCREENING_REVIEW_THRESHOLD", "70"))
    SCREENING_REJECT_THRESHOLD = int(os.environ.get("SCREENING_REJECT_THRESHOLD", "85"))
    SCREENING_AUTO_REJECT_EXACT_MATCH = (
        os.environ.get("SCREENING_AUTO_REJECT_EXACT_MATCH", "false").lower() == "true"
    )

    # A sanctions source whose active snapshot is older than this many days
    # is flagged as stale in the compliance-officer UI (see
    # app/sanctions/freshness.py) -- a real screening decision made against
    # an outdated list is a compliance gap, not just a UI nicety.
    SANCTIONS_STALENESS_WARNING_DAYS = int(os.environ.get("SANCTIONS_STALENESS_WARNING_DAYS", "7"))

    # Age verification defaults. The implementation stores only an opaque
    # platform subject reference plus a hash of the received proof token --
    # never the raw token or source identity document payload.
    AGEVERIFY_DEFAULT_ADAPTER = os.environ.get("AGEVERIFY_DEFAULT_ADAPTER", "mock")
    AGEVERIFY_MIN_AGE = int(os.environ.get("AGEVERIFY_MIN_AGE", "18"))
    AGEVERIFY_EU_VERIFIER_BASE_URL = os.environ.get("AGEVERIFY_EU_VERIFIER_BASE_URL", "")
    AGEVERIFY_EU_VERIFIER_VERIFY_PATH = os.environ.get("AGEVERIFY_EU_VERIFIER_VERIFY_PATH", "/verify")
    AGEVERIFY_EU_VERIFIER_TIMEOUT_SECONDS = float(
        os.environ.get("AGEVERIFY_EU_VERIFIER_TIMEOUT_SECONDS", "5")
    )

    # Wallet ownership verification (EBA Travel Rule guidelines / BaFin GwG
    # Sec. 15a): self-hosted-wallet transfers at or above this EUR threshold
    # require proof of control of the counterparty address, via a signed
    # challenge message or a small on-chain test transfer.
    WALLET_OWNERSHIP_THRESHOLD_EUR = float(os.environ.get("WALLET_OWNERSHIP_THRESHOLD_EUR", "1000"))
    WALLET_OWNERSHIP_CHALLENGE_TTL_SECONDS = int(
        os.environ.get("WALLET_OWNERSHIP_CHALLENGE_TTL_SECONDS", "600")
    )

    # EVM test-transfer adapter. Left unset by default -- the adapter raises
    # AdapterNotConfiguredError rather than silently no-op'ing.
    WALLET_OWNERSHIP_EVM_RPC_URL = os.environ.get("WALLET_OWNERSHIP_EVM_RPC_URL", "")
    WALLET_OWNERSHIP_EVM_SENDER_PRIVATE_KEY = os.environ.get("WALLET_OWNERSHIP_EVM_SENDER_PRIVATE_KEY", "")
    WALLET_OWNERSHIP_EVM_CHAIN_ID = int(os.environ.get("WALLET_OWNERSHIP_EVM_CHAIN_ID", "1"))
    WALLET_OWNERSHIP_EVM_RPC_TIMEOUT_SECONDS = float(
        os.environ.get("WALLET_OWNERSHIP_EVM_RPC_TIMEOUT_SECONDS", "10")
    )
    WALLET_OWNERSHIP_TEST_TRANSFER_AMOUNT_WEI = int(
        os.environ.get("WALLET_OWNERSHIP_TEST_TRANSFER_AMOUNT_WEI", "1000000000000")
    )
    WALLET_OWNERSHIP_TEST_TRANSFER_MIN_CONFIRMATIONS = int(
        os.environ.get("WALLET_OWNERSHIP_TEST_TRANSFER_MIN_CONFIRMATIONS", "1")
    )

    # AI compliance agent (see app/agent/). Off by default: a deployment
    # that doesn't opt in never imports the LLM client or exposes /agent/*.
    # Secrets come from the environment only; there is deliberately no
    # default model id -- set ANTHROPIC_MODEL explicitly.
    AGENT_ENABLED = os.environ.get("AGENT_ENABLED", "false").lower() == "true"
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "")
    AGENT_LLM_TIMEOUT_SECONDS = float(os.environ.get("AGENT_LLM_TIMEOUT_SECONDS", "20"))
    AGENT_LLM_MAX_CALLS_PER_MINUTE = int(os.environ.get("AGENT_LLM_MAX_CALLS_PER_MINUTE", "30"))
    # Chain adapter for verify_incoming_funds / the deposit monitor: "mock"
    # (default, deterministic) or "evm" (read-only JSON-RPC, testnet only).
    AGENT_CHAIN_ADAPTER = os.environ.get("AGENT_CHAIN_ADAPTER", "mock")
    AGENT_EVM_RPC_URL = os.environ.get("AGENT_EVM_RPC_URL", "")
    AGENT_MIN_CONFIRMATIONS = int(os.environ.get("AGENT_MIN_CONFIRMATIONS", "3"))
    AGENT_EVM_RPC_TIMEOUT_SECONDS = float(os.environ.get("AGENT_EVM_RPC_TIMEOUT_SECONDS", "10"))
    # en (default) or de; applies to the agent UI and shared templates.
    UI_LOCALE = os.environ.get("UI_LOCALE", "en")
    # Flask session signing key for the owner dashboard. No default: owner
    # login is refused until a real secret is configured.
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    OWNER_COOKIE_SECURE = os.environ.get("OWNER_COOKIE_SECURE", "false").lower() == "true"

    # Hosted-platform controls (all off/neutral by default, so self-hosted is unchanged).
    # Operator console at /admin (accounts are created from the CLI only).
    PLATFORM_ADMIN_ENABLED = os.environ.get("PLATFORM_ADMIN_ENABLED", "false").lower() == "true"
    # The Travel Rule review console has no per-client scoping; on a shared host only operators may open it.
    REVIEW_UI_REQUIRE_OPERATOR = os.environ.get("REVIEW_UI_REQUIRE_OPERATOR", "false").lower() == "true"
    # New developer projects stay inactive until an operator approves them (invite-only pilots).
    SIGNUP_APPROVAL_REQUIRED = os.environ.get("SIGNUP_APPROVAL_REQUIRED", "false").lower() == "true"
    SIGNUP_RATE_LIMIT_PER_HOUR = int(os.environ.get("SIGNUP_RATE_LIMIT_PER_HOUR", "30"))
    # Hard daily ceiling of agent cases per project, so one client cannot burn the LLM budget.
    AGENT_MAX_CASES_PER_DAY = int(os.environ.get("AGENT_MAX_CASES_PER_DAY", "200"))
    # Number of reverse proxies in front of the app (Traefik = 1) so client IPs and https are read correctly.
    TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", "0"))
    SESSION_COOKIE_SECURE = OWNER_COOKIE_SECURE
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # "recording" (default) only records instructions; "webhook" sends them,
    # HMAC-signed, to the project's webhook_url.
    AGENT_EXECUTOR = os.environ.get("AGENT_EXECUTOR", "recording")
    # Optional digest email; unset SMTP_HOST = no email, HTML/CSV still available.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")

    # Hosted-SaaS billing (see app/billing/). Off by default -- a
    # self-hosted deployment needs zero Stripe setup and never has its
    # wallet-ownership/age-verify calls metered or quota-limited.
    BILLING_ENABLED = os.environ.get("BILLING_ENABLED", "false").lower() == "true"
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
    STRIPE_CHECKOUT_SUCCESS_URL = os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL", "http://localhost:8300/developer/")
    STRIPE_CHECKOUT_CANCEL_URL = os.environ.get("STRIPE_CHECKOUT_CANCEL_URL", "http://localhost:8300/developer/")
    FREE_TIER_MONTHLY_CALL_LIMIT = int(os.environ.get("FREE_TIER_MONTHLY_CALL_LIMIT", "1000"))
