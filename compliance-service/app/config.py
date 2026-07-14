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
