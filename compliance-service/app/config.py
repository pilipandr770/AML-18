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
