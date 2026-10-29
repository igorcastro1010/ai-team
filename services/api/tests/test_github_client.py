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


def fake_api(credentials, *, selection="selected", repositories=None, status=200, operation=None):
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
            scope = json.loads(request.content)
            if scope != {"permissions": {"metadata": "read"}}:
                assert scope["repository_ids"] == [456]
                if scope["permissions"].get("pull_requests") == "write":
                    assert scope["permissions"].get("contents") == "read"
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
        if operation:
            return operation(request)
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


def test_branch_creation_uses_reviewed_sha_and_scoped_token(credentials):
    from ai_team.github_client import GitHubClient

    def operation(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        assert request.url.path.endswith("/git/refs")
        assert json.loads(request.content) == {
            "ref": "refs/heads/codex/ai-team/test",
            "sha": "a" * 40,
        }
        return httpx.Response(201, json={"object": {"sha": "a" * 40}})

    client, requests = fake_api(credentials, operation=operation)
    provider = GitHubClient(credentials, client=client)
    result = provider.execute(
        {
            "project_id": "synthetic",
            "operation": "branch",
            "title": "Criar branch revisada",
            "branch": "codex/ai-team/test",
            "expected_sha": "a" * 40,
        }
    )
    assert result["sha"] == "a" * 40 and provider.mutation_attempted
    assert len(requests) == 8


def test_executor_denies_main_before_any_network(credentials):
    from ai_team.github_client import GitHubClient

    client, requests = fake_api(credentials)
    with pytest.raises(ValueError):
        GitHubClient(credentials, client=client).execute(
            {
                "project_id": "synthetic",
                "operation": "branch",
                "title": "Invalid branch",
                "branch": "main",
                "expected_sha": "a" * 40,
            }
        )
    assert requests == []


def test_commit_is_atomic_fast_forward_and_never_forces_other_work(credentials):
    from ai_team.github_client import GitHubClient, GitHubError

    def operation(request):
        path = request.url.path
        if path.endswith("/git/ref/heads/codex/ai-team/test"):
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        if path.endswith("/git/commits/" + "a" * 40):
            return httpx.Response(200, json={"tree": {"sha": "b" * 40}})
        body = json.loads(request.content)
        if request.method == "PATCH":
            assert body == {"sha": "c" * 40, "force": False}
            return httpx.Response(409, json={"message": "Concurrent change"})
        if path.endswith("/git/commits"):
            assert body["parents"] == ["a" * 40]
        if path.endswith("/git/trees"):
            assert body["base_tree"] == "b" * 40
            assert body["tree"][0]["path"] == "docs/agent-output/test.md"
        return httpx.Response(201, json={"sha": "c" * 40})

    client, requests = fake_api(credentials, operation=operation)
    provider = GitHubClient(credentials, client=client)
    with pytest.raises(GitHubError):
        provider.execute(
            {
                "project_id": "synthetic",
                "operation": "commit",
                "title": "docs: synthetic proposal",
                "branch": "codex/ai-team/test",
                "expected_sha": "a" * 40,
                "path": "docs/agent-output/test.md",
                "content": "Synthetic approved document",
            }
        )
    assert provider.mutation_attempted
    assert len([r for r in requests if r.method == "PATCH"]) == 1


def test_private_pull_request_token_can_read_the_head_branch(credentials):
    from ai_team.github_client import GitHubClient

    def operation(request):
        if request.method == "GET":
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        assert request.url.path.endswith("/pulls")
        body = json.loads(request.content)
        assert body["base"] == "main" and body["head"] == "codex/ai-team/test"
        assert body["draft"] is True
        return httpx.Response(201, json={"number": 2, "head": {"sha": "a" * 40}})

    client, _ = fake_api(credentials, operation=operation)
    result = GitHubClient(credentials, client=client).execute(
        {
            "project_id": "synthetic",
            "operation": "pull_request",
            "title": "Synthetic pull request",
            "branch": "codex/ai-team/test",
            "expected_sha": "a" * 40,
        }
    )
    assert result["number"] == 2


def test_changed_pull_request_head_is_rejected_before_writing(credentials):
    from ai_team.github_client import GitHubClient, GitHubError

    def operation(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"object": {"sha": "b" * 40}})

    client, requests = fake_api(credentials, operation=operation)
    with pytest.raises(GitHubError):
        GitHubClient(credentials, client=client).execute(
            {
                "project_id": "synthetic",
                "operation": "pull_request",
                "title": "Reviewed pull request",
                "branch": "codex/ai-team/test",
                "expected_sha": "a" * 40,
            }
        )
    assert not any(r.url.path.endswith("/pulls") for r in requests)
