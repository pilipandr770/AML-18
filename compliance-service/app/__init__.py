import logging
import sys

from flask import Flask

from app.config import Config
from app.extensions import db, migrate


def _configure_logging():
    # A bare `logging.getLogger(__name__)` in each module propagates to the
    # root logger, which has no handler by default -- INFO-level messages
    # would silently vanish under gunicorn otherwise (only WARNING+ reaches
    # the interpreter's lastResort handler).
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(logging.INFO)


def create_app(config_class=Config):
    _configure_logging()

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.webhook.routes import webhook_bp
    app.register_blueprint(webhook_bp)

    from app.review_ui.routes import review_bp
    app.register_blueprint(review_bp)

    from app.ageverify.routes import ageverify_bp
    app.register_blueprint(ageverify_bp)

    from app.wallet_ownership.routes import wallet_ownership_bp
    app.register_blueprint(wallet_ownership_bp)

    from app.developer_portal.routes import developer_portal_bp
    app.register_blueprint(developer_portal_bp)

    from app.landing.routes import landing_bp
    app.register_blueprint(landing_bp)

    # Import models so Alembic/SQLAlchemy metadata picks them up.
    from app.screening import models as _screening_models  # noqa: F401
    from app.sanctions import models as _sanctions_models  # noqa: F401
    from app.ageverify import models as _ageverify_models  # noqa: F401
    from app.audit import models as _audit_models  # noqa: F401
    from app.wallet_ownership import models as _wallet_ownership_models  # noqa: F401
    from app.developer_portal import models as _developer_portal_models  # noqa: F401

    from app.cli import register_cli
    register_cli(app)

    return app
