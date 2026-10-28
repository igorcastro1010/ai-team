import json
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

from ai_team.github_setup import AppVault, SetupFlow, app_manifest


class MemoryKeyring:
    def __init__(self):
        self.values = {}

    def set_password(self, service, account, value):
        self.values[service, account] = value

    def get_password(self, service, account):
        return self.values.get((service, account))

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


def response_data():
    return {
        "id": 123,
        "slug": "ai-team-test",
        "owner": {"login": "igorcastro1010"},
        "pem": "-----BEGIN RSA PRIVATE KEY-----\n" + "x" * 6000,
        "client_secret": "unnecessary-secret",
        "webhook_secret": "unused-secret",
    }


def test_manifest_is_private_and_requests_only_needed_repository_permissions():
    manifest = app_manifest("http://127.0.0.1:8765/callback")
    assert manifest["url"] == "https://github.com/igorcastro1010/ai-team"
    assert manifest["redirect_url"] == "http://127.0.0.1:8765/callback"
    assert "callback_urls" not in manifest  # No user OAuth in this registration flow.
    assert manifest["public"] is False
    assert manifest["default_permissions"] == {
        "contents": "write",
        "issues": "write",
        "pull_requests": "write",
        "metadata": "read",
    }
    assert manifest["default_events"] == []
    assert manifest["hook_attributes"]["active"] is False
    assert manifest["hook_attributes"]["url"].startswith("https://")
    assert manifest["request_oauth_on_install"] is False


def test_large_private_key_is_chunked_in_keyring_and_unused_secrets_discarded():
    backend = MemoryKeyring()
    vault = AppVault(backend=backend)
    data = response_data()
    vault.save(data)
    loaded = vault.load()
    assert loaded["pem"] == data["pem"] and loaded["id"] == 123
    assert "client_secret" not in loaded and "webhook_secret" not in loaded
    assert max(len(value) for value in backend.values.values()) <= 1000
    with pytest.raises(RuntimeError, match="já configurado"):
        vault.save(data)


def test_setup_checks_state_before_api_and_rejects_replays():
    requests = []

    def transport(request):
        requests.append(request)
        assert request.url.host == "api.github.com"
        assert request.headers["x-github-api-version"] == "2026-03-10"
        return httpx.Response(201, json=response_data())

    vault = AppVault(backend=MemoryKeyring())
    flow = SetupFlow(vault, client=httpx.Client(transport=httpx.MockTransport(transport)))
    with pytest.raises(ValueError):
        flow.complete("invalid-state", "code123")
    assert not requests
    url = flow.complete(flow.state, "code123")
    assert url == "https://github.com/apps/ai-team-test/installations/new"
    assert vault.load()["id"] == 123
    with pytest.raises(ValueError):
        flow.complete(flow.state, "code123")
    assert len(requests) == 1


def test_wrong_owner_or_failed_exchange_never_saves_secrets():
    data = response_data()
    data["owner"]["login"] = "other-account"
    backend = MemoryKeyring()
    flow = SetupFlow(
        AppVault(backend=backend),
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(201, json=data))
        ),
    )
    with pytest.raises(ValueError):
        flow.complete(flow.state, "code123")
    assert backend.values == {}


def test_incomplete_keyring_write_cleans_partial_chunks():
    class BrokenKeyring(MemoryKeyring):
        def set_password(self, service, account, value):
            if account.endswith("-1"):
                raise RuntimeError("Storage unavailable")
            super().set_password(service, account, value)

    backend = BrokenKeyring()
    with pytest.raises(RuntimeError):
        AppVault(backend=backend).save(response_data())
    assert backend.values == {}


def test_rendered_form_posts_valid_json_manifest_and_preserves_state():
    from ai_team.github_setup import registration_form

    class FormParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "form":
                self.form = dict(attrs)
            elif tag == "input":
                self.field = dict(attrs)

    state = "random_state_123"
    parser = FormParser()
    parser.feed(registration_form("http://127.0.0.1:8765/callback", state))
    assert parser.form["method"].lower() == "post"
    assert parser.form["enctype"] == "application/x-www-form-urlencoded"
    action = urlsplit(parser.form["action"])
    assert (action.scheme, action.netloc, action.path) == (
        "https", "github.com", "/settings/apps/new"
    )
    assert parse_qs(action.query) == {"state": [state]}
    assert parser.field["name"] == "manifest"
    # Follow browser HTML entity decoding and form URL encoding, not the raw Python dict.
    posted = parse_qs(urlencode({parser.field["name"]: parser.field["value"]}))
    manifest = json.loads(posted["manifest"][0])
    assert manifest == app_manifest("http://127.0.0.1:8765/callback")
    assert manifest["url"] and manifest["hook_attributes"]["url"]


@pytest.mark.parametrize("field", ["url", "hook_attributes", "redirect_url"])
def test_form_rejects_missing_required_registration_configuration(monkeypatch, field):
    import ai_team.github_setup as setup

    manifest = app_manifest("http://127.0.0.1:8765/callback")
    del manifest[field]
    monkeypatch.setattr(setup, "app_manifest", lambda redirect_url: manifest)
    with pytest.raises(ValueError, match="manifesto"):
        setup.registration_form("http://127.0.0.1:8765/callback", "state123")


@pytest.mark.parametrize("redirect_url", [
    "https://example.com/callback",
    "http://127.0.0.1/callback",
    "http://user:password@127.0.0.1:8765/callback",
    "http://127.0.0.1:8765/other",
    "http://127.0.0.1:8765/callback?state=overridden",
    "http://127.0.0.1:8765/callback#fragment",
])
def test_form_rejects_redirects_outside_the_local_callback(redirect_url):
    from ai_team.github_setup import registration_form

    with pytest.raises(ValueError):
        registration_form(redirect_url, "state123")


def test_expired_state_and_failed_conversion_never_save_credentials():
    requests = []
    backend = MemoryKeyring()

    def transport(request):
        requests.append(request)
        return httpx.Response(422, json={"message": "invalid code"})

    flow = SetupFlow(
        AppVault(backend=backend),
        client=httpx.Client(transport=httpx.MockTransport(transport)),
    )
    flow.expires_at = 0
    with pytest.raises(ValueError):
        flow.complete(flow.state, "code123")
    assert requests == [] and backend.values == {}
    flow.expires_at = float("inf")
    with pytest.raises(ValueError):
        flow.complete(flow.state, "code123")
    assert len(requests) == 1 and backend.values == {}
    with pytest.raises(ValueError):
        flow.complete(flow.state, "code123")
    assert len(requests) == 1


def test_existing_app_review_never_recreates_app_or_displays_credentials():
    from ai_team.github_setup import existing_app_page

    data = response_data()
    page = existing_app_page(data)
    assert "https://github.com/apps/ai-team-test/installations/new" in page
    assert "Only select repositories" in page and "ai-team" in page
    assert "<form" not in page and "manifest" not in page
    assert "PRIVATE KEY" not in page and data["client_secret"] not in page
