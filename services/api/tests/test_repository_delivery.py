import hashlib

import pytest

from ai_team.repository_delivery import publish
from ai_team.repository_policy import RepositoryBundle, RepositoryPolicy


class Client:
    def __init__(self, current="a" * 40):
        self.current, self.calls = current, []
        self.entries = []
        self.tamper = None
        self.unchanged = set()

    def verify(self):
        return {}

    def _token(self, verified, permissions):
        assert permissions == {"contents": "write", "pull_requests": "write"}
        return "test"

    def _request(self, method, path, token, **kwargs):
        self.calls.append((method, path, kwargs.get("body")))
        if "/ref/heads/" in path:
            return {"object": {"sha": self.current if path.endswith("main") else "d" * 40}}
        if "/git/commits/" in path:
            if path.endswith("a" * 40):
                return {"tree": {"sha": "b" * 40}}
            return {"sha": "d" * 40, "tree": {"sha": "c" * 40},
                    "parents": [{"sha": "f" * 40 if self.tamper == "parent" else "a" * 40}]}
        if "/compare/" in path:
            files = [{"filename": f["path"], "sha": blob_sha(f["content"]), "status": "modified"}
                     for f in self.entries if f["path"] not in self.unchanged]
            if self.tamper == "content":
                files[0]["sha"] = "f" * 40
            if self.tamper == "extra":
                files.append({"filename": "secrets.txt", "sha": "e" * 40, "status": "added"})
            return {"status": "ahead", "ahead_by": 1, "total_commits": 1, "files": files}
        if "/contents/" in path:
            file = next(f for f in self.entries if f["path"] in path)
            return {"type": "file", "sha": "f" * 40 if self.tamper == "unchanged"
                    else blob_sha(file["content"])}
        if path.endswith("/trees"):
            body = kwargs["body"]
            assert body["base_tree"] == "b" * 40
            assert body["tree"][0]["path"] == "tools/budget.py"
            assert body["tree"][0]["mode"] == "100644"
            self.entries = body["tree"]
            return {"sha": "c" * 40}
        if path.endswith("/commits"):
            return {"sha": "d" * 40}
        if path.endswith("/refs"):
            assert kwargs["body"]["ref"].startswith("refs/heads/codex/ai-team/task-")
            return {}
        assert path.endswith("/pulls") and kwargs["body"]["draft"] is True
        return {
            "number": 99,
            "html_url": "https://github.com/igorcastro1010/ai-team/pull/99",
            "head": {"sha": "d" * 40},
        }


def blob_sha(content):
    raw = content.encode("utf-8")
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


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


def test_multifile_delivery_reads_back_utf8_content_before_creating_branch():
    data = bundle()
    data.policy.write_paths.append("guide.md")
    from ai_team.repository_policy import RepositoryFile
    data.files.append(RepositoryFile(path="guide.md", content="# Orçamento\n"))
    client = Client()
    result = publish(client, "00000000-0000-4000-8000-000000000001", data, "feat: budget", "tests")
    assert result["bundle_digest"] == data.digest
    assert result["verified_paths"] == ["tools/budget.py", "tools/guide.md"]
    compare = next(i for i, call in enumerate(client.calls) if "/compare/" in call[1])
    ref = next(i for i, call in enumerate(client.calls) if call[1].endswith("/refs"))
    assert compare < ref


@pytest.mark.parametrize("tamper", ["content", "extra", "parent"])
def test_remote_content_mismatch_never_creates_branch_or_pr(tamper):
    client = Client()
    client.tamper = tamper
    with pytest.raises(ValueError):
        publish(client, "00000000-0000-4000-8000-000000000001", bundle(), "feat: budget", "tests")
    assert not any(path.endswith(("/refs", "/pulls")) for _, path, _ in client.calls)


@pytest.mark.parametrize("tamper", [None, "unchanged"])
def test_unchanged_generated_file_still_has_immutable_readback(tamper):
    from ai_team.repository_policy import RepositoryFile

    data = bundle()
    data.policy.write_paths.append("guide.md")
    data.files.append(RepositoryFile(path="guide.md", content="# Existing guide\n"))
    client = Client()
    client.unchanged = {"tools/guide.md"}
    client.tamper = tamper
    args = (client, "00000000-0000-4000-8000-000000000001", data, "feat: budget", "tests")
    if tamper:
        with pytest.raises(ValueError):
            publish(*args)
        assert not any(path.endswith("/refs") for _, path, _ in client.calls)
    else:
        assert publish(*args)["bundle_digest"] == data.digest
    assert any("/contents/tools/guide.md?ref=" + "d" * 40 in p for _, p, _ in client.calls)
