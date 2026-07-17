def test_landing_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AML+18".encode() in resp.data
    assert "Travel Rule".encode() in resp.data


def test_landing_page_links_to_developer_portal_and_review_ui(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'href="/developer/"' in resp.data
    assert b'href="/review/"' in resp.data
