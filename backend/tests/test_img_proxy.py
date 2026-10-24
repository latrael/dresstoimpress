"""GET /img: allowlisted image proxy for the Flutter web build (no key, only retailer image hosts)."""
import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from app.main import app

    monkeypatch.setenv("API_SHARED_KEY", "k")  # /img must work without the key
    return TestClient(app)


class R:
    def __init__(self, url, ctype="image/jpeg", body=b"\xff\xd8jpeg"):
        self.url, self.headers, self.content = url, {"content-type": ctype}, body

    def raise_for_status(self):
        pass


def test_proxies_allowed_host_without_key(client, monkeypatch):
    seen = []
    monkeypatch.setattr(httpx, "get", lambda url, **k: seen.append(url) or R(url))
    r = client.get("/img", params={"url": "https://image.hm.com/assets/hm/x.jpg?imwidth=657"})
    assert r.status_code == 200 and r.content == b"\xff\xd8jpeg"
    assert r.headers["content-type"] == "image/jpeg" and "max-age" in r.headers["cache-control"]
    assert seen == ["https://image.hm.com/assets/hm/x.jpg?imwidth=657"]


@pytest.mark.parametrize("url", ["https://evil.example.com/x.jpg", "http://image.hm.com/x.jpg",
                                 "file:///etc/passwd", "https://image.hm.com.evil.com/x.jpg"])
def test_rejects_other_hosts(client, monkeypatch, url):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("must not fetch"))
    assert client.get("/img", params={"url": url}).status_code == 400


def test_rejects_redirect_off_allowlist_and_non_images(client, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, **k: R("https://evil.example.com/x.jpg"))
    assert client.get("/img", params={"url": "https://image.hm.com/a.jpg"}).status_code == 400
    monkeypatch.setattr(httpx, "get", lambda url, **k: R(url, ctype="text/html", body=b"<html>"))
    assert client.get("/img", params={"url": "https://image.hm.com/a.jpg"}).status_code == 415


def test_other_routes_still_need_the_key(client):
    assert client.get("/closet/u_demo").status_code == 401
