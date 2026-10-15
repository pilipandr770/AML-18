from app import create_app
from app.config import Config
from app.extensions import db


class EnglishConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def _client():
    app = create_app(EnglishConfig)
    ctx = app.app_context()
    ctx.push()
    db.create_all()
    return app.test_client(), ctx


def test_default_locale_is_english():
    assert Config.UI_LOCALE == "en"


def test_english_pages_by_default():
    client, ctx = _client()
    try:
        assert b"No screening decisions yet." in client.get("/review/").data
        assert b"Register a project" in client.get("/developer/signup").data
        page = client.get("/developer/pricing").data
        assert b"no usage limits" in page
        assert b"keine Nutzungsbeschr" not in page
        assert b"One building block" in client.get("/developer/").data
    finally:
        ctx.pop()


def test_german_available_via_env_locale():
    from tests.conftest import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        assert "Noch keine Screening-Entscheidungen".encode() in c.get("/review/").data
        assert "Projekt registrieren".encode() in c.get("/developer/signup").data


def test_english_landing_has_new_pitch_and_german_keeps_old_page():
    client, ctx = _client()
    try:
        page = client.get("/").data
        assert b"AI compliance officer for crypto and fintech" in page
        assert b"REQUIRES COUNSEL REVIEW" in page
    finally:
        ctx.pop()
    from tests.conftest import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        assert "Aus einer Blockchain-Adresse".encode() in app.test_client().get("/").data
