def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in resp.headers  # plain HTTP in tests


def test_hsts_only_over_https(client):
    resp = client.get("/", base_url="https://localhost")
    assert "Strict-Transport-Security" in resp.headers
