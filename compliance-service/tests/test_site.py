import pytest

from app.docs_site.routes import PAGES


def test_landing_renders_both_locales(app, client):
    for loc, needle in (("en", "AI compliance officer"), ("de", "KI-Compliance-Officer")):
        app.config["UI_LOCALE"] = loc
        resp = client.get("/")
        assert resp.status_code == 200 and needle in resp.get_data(as_text=True)
        assert "/static/hero3d.js" in resp.get_data(as_text=True)
    app.config["UI_LOCALE"] = "de"


@pytest.mark.parametrize("slug", [s for s, _ in PAGES])
def test_docs_pages(client, slug):
    resp = client.get("/docs/" if slug == "overview" else f"/docs/{slug}")
    assert resp.status_code == 200 and "AML+18" in resp.get_data(as_text=True)


def test_docs_unknown_page_404(client):
    assert client.get("/docs/nope").status_code == 404


def test_static_assets_served(client):
    for f in ("site.css", "site.js", "hero3d.js"):
        assert client.get(f"/static/{f}").status_code == 200


def test_assistant_disabled_by_default(client):
    assert client.post("/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 404


def test_assistant_validation_and_degraded_fallback(app, client):
    app.config.update(ASSISTANT_ENABLED=True, ANTHROPIC_API_KEY="", ANTHROPIC_MODEL="")
    assert client.post("/assistant/chat", json={"messages": "x"}).status_code == 400
    assert client.post("/assistant/chat", json={"messages": [{"role": "assistant", "content": "x"}]}).status_code == 400
    ok = client.post("/assistant/chat", json={"messages": [{"role": "user", "content": "How do we connect?"}]})
    assert ok.status_code == 200 and ok.get_json()["degraded"] is True
    bad_origin = client.post("/assistant/chat", json={"messages": [{"role": "user", "content": "x"}]},
                             headers={"Origin": "https://evil.example"})
    assert bad_origin.status_code == 403


def test_assistant_rate_limit(app, client):
    from app.assistant import routes
    routes._hits.clear()
    app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_PER_MINUTE=2, ANTHROPIC_API_KEY="")
    body = {"messages": [{"role": "user", "content": "hi"}]}
    codes = [client.post("/assistant/chat", json=body).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_legal_pages(client):
    imp = client.get("/impressum").get_data(as_text=True)
    assert "Andrii Pylypchuk" in imp and "DE456902445" in imp and "65934 Frankfurt am Main" in imp
    assert client.get("/datenschutz").status_code == 200
    assert b"/impressum" in client.get("/").data
