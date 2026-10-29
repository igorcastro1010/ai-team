import json

import httpx
import pytest
from test_github_setup import MemoryKeyring

TOKEN = "vcp_synthetic_token_for_tests_1234567890"


def test_token_uses_native_vault_without_overwrite_or_plaintext_fallback(monkeypatch):
    import ai_team.vercel_access as access

    backend = MemoryKeyring()
    vault = access.VercelVault(backend=backend)
    vault.preflight()
    vault.save(TOKEN, None)
    assert vault.load()["token"] == TOKEN
    with pytest.raises(RuntimeError):
        vault.save("replacement_token_1234567890", None)
    monkeypatch.setattr(access.keyring, "get_keyring", lambda: MemoryKeyring())
    with pytest.raises(RuntimeError):
        access.VercelVault()


def test_reader_filters_exact_project_and_never_returns_raw_project_secrets():
    from ai_team.vercel_access import VercelClient

    requests = []

    def transport(request):
        requests.append(request)
        assert request.method == "GET" and request.url.host == "api.vercel.com"
        assert request.headers["authorization"] == "Bearer " + TOKEN
        if request.url.path == "/v10/projects":
            assert request.url.params["search"] == "ai-team"
            return httpx.Response(
                200,
                json={
                    "projects": [
                        {"id": "prj_other", "name": "ai-team-other", "env": [{"value": "secret"}]},
                        {"id": "prj_approved", "name": "ai-team", "env": [{"value": "secret"}]},
                    ]
                },
            )
        assert request.url.path == "/v7/deployments"
        assert request.url.params["projectId"] == "prj_approved"
        return httpx.Response(
            200,
            json={
                "deployments": [
                    {
                        "uid": "dpl_1",
                        "name": "ai-team",
                        "state": "READY",
                        "url": "example.vercel.app",
                        "env": {"SECRET": "must-not-leak"},
                    }
                ]
            },
        )

    client = VercelClient(TOKEN, client=httpx.Client(transport=httpx.MockTransport(transport)))
    result = client.probe()
    assert result["project"] == {"id": "prj_approved", "name": "ai-team"}
    assert result["deployments"][0]["state"] == "READY"
    assert "must-not-leak" not in json.dumps(result) and "env" not in json.dumps(result)
    assert len(requests) == 2


def test_missing_project_is_reported_without_creating_any_resource():
    from ai_team.vercel_access import VercelClient

    requests = []

    def transport(request):
        requests.append(request)
        return httpx.Response(200, json={"projects": []})

    result = VercelClient(
        TOKEN, client=httpx.Client(transport=httpx.MockTransport(transport))
    ).probe()
    assert result["project"] is None and result["deployments"] == []
    assert len(requests) == 1 and requests[0].method == "GET"


@pytest.mark.parametrize("status", [401, 403, 302])
def test_failed_verification_does_not_store_or_expose_token(status):
    from ai_team.vercel_access import VercelVault, configure

    backend = MemoryKeyring()
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, json={"message": TOKEN}, headers={"Location": "https://untrusted.example"}
            )
        )
    )
    with pytest.raises(RuntimeError) as caught:
        configure(TOKEN, None, VercelVault(backend=backend), client=client)
    assert TOKEN not in str(caught.value) and backend.values == {}


def test_vault_write_failure_is_sanitized():
    from ai_team.vercel_access import VercelVault

    class BrokenKeyring(MemoryKeyring):
        def set_password(self, service, account, value):
            raise RuntimeError("Native storage error containing " + TOKEN)

    with pytest.raises(RuntimeError) as caught:
        VercelVault(backend=BrokenKeyring()).save(TOKEN, None)
    assert TOKEN not in str(caught.value)


def test_successful_configure_stores_token_only_after_read_verification():
    from ai_team.vercel_access import VercelVault, configure

    backend = MemoryKeyring()
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"projects": []}))
    )
    result = configure(TOKEN, None, VercelVault(backend=backend), client=client)
    assert result["project"] is None
    assert VercelVault(backend=backend).load() == {"token": TOKEN, "team_id": None}


def test_noninteractive_terminal_refuses_token_input(monkeypatch, capsys):
    from types import SimpleNamespace

    import ai_team.vercel_access as access

    vault = access.VercelVault(backend=MemoryKeyring())
    monkeypatch.setattr(access, "VercelVault", lambda: vault)
    monkeypatch.setattr(access.sys, "argv", ["vercel_access", "configure"])
    monkeypatch.setattr(access.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    with pytest.raises(SystemExit) as caught:
        access.main()
    assert caught.value.code == 1
    assert "terminal interativo" in capsys.readouterr().out
    assert vault.load() is None


def test_bind_team_pins_project_without_changing_token():
    from ai_team.vercel_access import VercelClient, VercelVault

    backend = MemoryKeyring()
    vault = VercelVault(backend=backend)
    vault.save(TOKEN, None)

    def transport(request):
        assert request.url.params["teamId"] == "team_test"
        if request.url.path == "/v10/projects":
            return httpx.Response(200, json={"projects": [{"id": "prj_test", "name": "ai-team"}]})
        return httpx.Response(200, json={"deployments": []})

    vault.bind_team(
        "team_test", "prj_test", client=httpx.Client(transport=httpx.MockTransport(transport))
    )
    assert vault.load() == {"token": TOKEN, "team_id": "team_test", "project_id": "prj_test"}
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"projects": [{"id": "prj_changed", "name": "ai-team"}]}
            )
        )
    )
    with pytest.raises(RuntimeError):
        VercelClient(TOKEN, project_id="prj_test", client=client).probe()
