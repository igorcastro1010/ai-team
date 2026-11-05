import pytest
from pydantic import ValidationError

from ai_team.repository_policy import RepositoryBundle, RepositoryFile, RepositoryPolicy


def test_corrupted_python_is_rejected_before_workspace_or_test_approval():
    with pytest.raises(ValueError, match="Python inválido"):
        RepositoryFile(path="budget.py", content="MAX_TOKENS=*** remaining_tokens(used):\n")
    assert RepositoryFile(path="budget.py", content="MAX_TOKENS: int = 50_000\n")


def policy(**values):
    return RepositoryPolicy(
        base_sha="a" * 40, directory="docs/agent-output/python",
        read_paths=["calculator.py"],
        write_paths=["calculator.py", "test_calculator.py", "guide.md"], **values,
    )


@pytest.mark.parametrize("path", ["../foo", ".git", ".env", "a\\b", "/tmp", "a//b"])
def test_directory_denies_escape_and_sensitive_paths(path):
    data = policy().model_dump()
    data["directory"] = path
    with pytest.raises(ValidationError):
        RepositoryPolicy.model_validate(data)


def test_bundle_is_bound_to_snapshot_and_write_allowlist():
    p = policy()
    bundle = RepositoryBundle(policy=p, files=[{"path": "calculator.py", "content": "x=1\n"}])
    changed = bundle.model_copy(update={"policy": p.model_copy(update={"base_sha": "b" * 40})})
    assert changed.digest != bundle.digest
    with pytest.raises(ValidationError):
        RepositoryBundle(policy=p, files=[{"path": "other.py", "content": "x=1"}])


@pytest.mark.parametrize("path", ["os.py", "con.py", "../foo.py", "foo.sh", "a/b.py"])
def test_file_profile_restricts_host_paths_and_runtime_modules(path):
    data = policy().model_dump()
    data["write_paths"] = [path]
    with pytest.raises(ValidationError):
        RepositoryPolicy.model_validate(data)


def test_bundle_does_not_change_read_only_file():
    p = policy().model_copy(update={"write_paths": ["test_calculator.py", "guide.md"]})
    with pytest.raises(ValidationError):
        RepositoryBundle(policy=p, files=[{"path": "calculator.py", "content": "changed"}])
