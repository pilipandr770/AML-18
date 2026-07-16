import pytest

from app import create_app
from app.config import Config


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WEBHOOK_AUTH_KEY_ID = "01JXTESTKEYID0000000000000"
    WEBHOOK_AUTH_KEY_SECRET = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
    WEBHOOK_SIGN_REPLIES = False


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        from app.extensions import db
        db.create_all()
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """A valid Authorization header for a freshly registered developer
    project -- required by every gated wallet-ownership/age-verify route."""
    from app.developer_portal.auth import generate_api_key, hash_api_key
    from app.developer_portal.models import DeveloperProject
    from app.extensions import db

    with app.app_context():
        api_key = generate_api_key()
        db.session.add(DeveloperProject(
            name="Test Project",
            contact_email="dev@example.com",
            api_key_prefix=api_key[:16],
            api_key_hash=hash_api_key(api_key),
        ))
        db.session.commit()

    return {"Authorization": f"Bearer {api_key}"}
