import pytest

from ai_team.repository_delivery import publish
from ai_team.repository_policy import RepositoryBundle, RepositoryPolicy


class Client:
    def __init__(self, current="a" * 40):
        self.current, self.calls = current, []

    def verify(self):
        return {}

    def _token(self, verified, permissions):
        assert permissions == {"contents": "write", "pull_requests": "write"}
        return "test"

    def _request(self, method, path, token, **kwargs):
        self.calls.append((method, path, kwargs.get("body")))
        if "/ref/heads/" in path:
            return {"object": {"sha": self.current}}
        if "/commits/" in path:
            return {"tree": {"sha": "b" * 40}}
        if path.endswith("/trees"):
            body = kwargs["body"]
            assert body["base_tree"] == "b" * 40
            assert body["tree"][0]["path"] == "tools/budget.py"
            assert body["tree"][0]["mode"] == "100644"
            return {"sha": "c" * 40}
        if path.endswith("/commits"):
            return {"sha": "d" * 40}
        if path.endswith("/refs"):
            assert kwargs["body"]["ref"].startswith("refs/heads/codex/ai-team/task-")
            return {}
        assert path.endswith("/pulls") and kwargs["body"]["draft"] is True
        return {"number": 99, "html_url": "https://github.com/igorcastro1010/ai-team/pull/99"}


def bundle():
    return RepositoryBundle(
        policy=RepositoryPolicy(
            base_sha="a" * 40,
            directory="tools",
            read_paths=["budget.py"],
            write_paths=["budget.py"],
        ),
        files=[{"path": "budget.py", "content": "value=2\n"}],
    )


def test_atomic_tree_preserves_unselected_files_and_creates_draft_only():
    client = Client()
    result = publish(
        client,
        "00000000-0000-4000-8000-000000000001",
        bundle(),
        "feat: validate budgets",
        "Reviewed tests passed",
    )
    assert result["status"] == "published"
    assert len([c for c in client.calls if c[0] == "POST"]) == 4
    assert not any(c[0] in {"PATCH", "DELETE", "PUT"} for c in client.calls)


def test_changed_base_ref_denies_all_external_writes():
    client = Client(current="f" * 40)
    with pytest.raises(ValueError):
        publish(client, "00000000-0000-4000-8000-000000000001", bundle(), "feat: change", "tests")
    assert all(c[0] == "GET" for c in client.calls)
