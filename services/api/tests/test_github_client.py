import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture
def credentials():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "id": 123,
        "slug": "ai-team-test",
        "pem": key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        "public_key": key.public_key(),
    }


def fake_api(credentials, *, selection="selected", repositories=None, status=200):
    requests = []
    repository = {
        "id": 456,
        "full_name": "igorcastro1010/ai-team",
        "private": True,
        "default_branch": "main",
        "archived": False,
    }

    def transport(request):
        requests.append(request)
        assert request.url.host == "api.github.com"
        assert request.headers["x-github-api-version"] == "2026-03-10"
        path = request.url.path
        if path in {"/app", "/repos/igorcastro1010/ai-team/installation"}:
            token = request.headers["authorization"].removeprefix("Bearer ")
            claims = jwt.decode(token, credentials["public_key"], algorithms=["RS256"])
            assert claims["iss"] == "123"
            assert time.time() - 65 <= claims["iat"] <= time.time() - 55
            assert claims["exp"] - time.time() <= 600
        if path == "/app":
            return httpx.Response(
                200, json={"id": 123, "slug": "ai-team-test", "owner": {"login": "igorcastro1010"}}
            )
        if path.endswith("/installation"):
            return httpx.Response(
                200,
                json={
                    "id": 789,
                    "app_id": 123,
                    "account": {"login": "igorcastro1010"},
                    "repository_selection": selection,
                    "suspended_at": None,
                    "permissions": {
                        "contents": "write",
                        "issues": "write",
                        "pull_requests": "write",
                        "metadata": "read",
                    },
                },
            )
        if path == "/app/installations/789/access_tokens":
            assert request.method == "POST"
            assert json.loads(request.content) == {"permissions": {"metadata": "read"}}
            return httpx.Response(201, json={"token": "test-installation-secret"})
        if path == "/installation/repositories":
            repos = repositories if repositories is not None else [repository]
            return httpx.Response(200, json={"total_count": len(repos), "repositories": repos})
        if path == "/repos/igorcastro1010/ai-team":
            return httpx.Response(
                status,
                json=repository
                if status == 200
                else {"message": "do not expose test-installation-secret"},
            )
        raise AssertionError(f"Unexpected API path: {path}")

    return httpx.Client(transport=httpx.MockTransport(transport)), requests


def test_own_app_authenticates_and_verifies_exactly_one_private_repository(credentials):
    from ai_team.github_client import GitHubClient

    client, requests = fake_api(credentials)
    result = GitHubClient(credentials, client=client).verify()
    assert result["repository"] == "igorcastro1010/ai-team"
    assert result["installation_id"] == 789
    assert result["default_branch"] == "main"
    assert "token" not in json.dumps(result) and "pem" not in json.dumps(result)
    assert len(requests) == 5


@pytest.mark.parametrize(
    "selection,repositories",
    [
        ("all", None),
        ("selected", [{"id": 1, "full_name": "igorcastro1010/other"}]),
        (
            "selected",
            [
                {"id": 456, "full_name": "igorcastro1010/ai-team"},
                {"id": 999, "full_name": "igorcastro1010/other"},
            ],
        ),
    ],
)
def test_broader_or_wrong_installation_is_denied(credentials, selection, repositories):
    from ai_team.github_client import GitHubClient, GitHubError

    client, requests = fake_api(credentials, selection=selection, repositories=repositories)
    with pytest.raises(GitHubError):
        GitHubClient(credentials, client=client).verify()
    assert not any(request.url.path == "/repos/igorcastro1010/ai-team" for request in requests)


def test_api_errors_are_sanitized_and_not_retried(credentials):
    from ai_team.github_client import GitHubClient, GitHubError

    client, requests = fake_api(credentials, status=403)
    with pytest.raises(GitHubError) as caught:
        GitHubClient(credentials, client=client).verify()
    assert "test-installation-secret" not in str(caught.value)
    assert len(requests) == 5
