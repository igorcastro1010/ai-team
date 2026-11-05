import uuid

import pytest

from ai_team.repository_policy import RepositoryBundle, RepositoryPolicy
from ai_team.repository_workspace import TaskWorkspace


def test_task_git_has_no_remote_and_diff_matches_contents(tmp_path):
    p = RepositoryPolicy(base_sha="a" * 40, directory="tools", read_paths=["budget.py"],
                         write_paths=["budget.py", "test_budget.py"])
    workspace = TaskWorkspace(tmp_path, str(uuid.uuid4()))
    workspace.initialize({"budget.py": "value = 1\n"})
    bundle = RepositoryBundle(policy=p, files=[{"path": "budget.py", "content": "value = 2\n"}])
    diff = workspace.apply(bundle)
    assert "-value = 1" in diff and "+value = 2" in diff
    assert workspace.git("remote", "-v") == ""
    assert workspace.git("branch", "--show-current").startswith("codex/ai-team/task-")


def test_workspace_rejects_arbitrary_ids_and_preexisting_directories(tmp_path):
    with pytest.raises(ValueError):
        TaskWorkspace(tmp_path, "../outside")
    task_id = str(uuid.uuid4())
    workspace = TaskWorkspace(tmp_path, task_id)
    workspace.initialize({"budget.py": "x=1"})
    with pytest.raises(FileExistsError):
        workspace.initialize({"budget.py": "x=2"})


def test_workspace_rejects_untrusted_path_before_touching_disk(tmp_path):
    workspace = TaskWorkspace(tmp_path, str(uuid.uuid4()))
    with pytest.raises(ValueError):
        workspace.initialize({"../outside.py": "x=1"})
    assert not (tmp_path.parent / "outside.py").exists()
