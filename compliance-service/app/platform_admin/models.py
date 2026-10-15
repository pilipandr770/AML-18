from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class PlatformOperator(db.Model):
    """A person who runs the hosted platform (as opposed to a client's owner
    account). Created only from the command line, never through a web form,
    so there is no public path to becoming an operator."""

    __tablename__ = "platform_operators"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    totp_secret = db.Column(db.String(64), nullable=False)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
