def test_landing_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AML+18".encode() in resp.data
    assert "Travel Rule".encode() in resp.data


def test_landing_page_links_to_signup_and_docs_but_not_operator_ui(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'href="/developer/signup"' in resp.data
    assert b'href="/docs/"' in resp.data
    assert b'href="/review/"' not in resp.data
