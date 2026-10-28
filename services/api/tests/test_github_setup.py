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
