import base64

import pytest

from ai_team.repository_policy import RepositoryPolicy
from ai_team.repository_snapshot import read_snapshot


class Client:
    def __init__(self, mode="100644"):
        self.mode, self.paths = mode, []

    def verify(self):
        return {}

    def _token(self, verified, permissions):
        assert permissions == {"contents": "read"}
        return "test-only"

    def _request(self, method, path, token):
        assert method == "GET"
        self.paths.append(path)
        if "/commits/" in path:
            return {"sha": "a" * 40, "tree": {"sha": "b" * 40}}
        if "/trees/" in path:
            if path.endswith("b" * 40):
                return {
                    "tree": [{"path": "tools", "mode": "040000", "type": "tree", "sha": "c" * 40}]
                }
            return {
                "tree": [
                    {
                        "path": "budget.py",
                        "mode": self.mode,
                        "type": "blob",
                        "sha": "d" * 40,
                        "size": 4,
                    }
                ]
            }
        return {"encoding": "base64", "size": 4, "content": base64.b64encode(b"x=1\n").decode()}


def test_snapshot_only_reads_explicit_files_at_immutable_sha():
    policy = RepositoryPolicy(
        base_sha="a" * 40,
        directory="tools",
        read_paths=["budget.py"],
        write_paths=["budget.py", "test_budget.py"],
    )
    client = Client()
    assert read_snapshot(client, policy) == {"budget.py": "x=1\n"}
    assert len(client.paths) == 4


@pytest.mark.parametrize("mode", ["120000", "160000", "100755"])
def test_snapshot_rejects_symlinks_submodules_and_executables(mode):
    policy = RepositoryPolicy(
        base_sha="a" * 40, directory="tools", read_paths=["budget.py"], write_paths=["budget.py"]
    )
    with pytest.raises(ValueError):
        read_snapshot(Client(mode), policy)
