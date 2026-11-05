"""Prepare local evidence only. This module cannot call GitHub or authorize publication."""

import hashlib

from .repository_policy import RepositoryBundle, fingerprint
from .repository_runs import execution_bundle
from .repository_workspace import TaskWorkspace


def prepare_publication(view, workspace_root):
    run, state = view["run"], view["state"]
    checkpoint = fingerprint({"id": run["id"], "stage": run["stage"],
                              "steps": run["steps"], "state": state})
    if (
        checkpoint != view["digest"] or run["stage"] != 6 or run["calls"] != 6
        or run["status"] not in {"awaiting_approval", "completed"}
        or state.get("delivery") or state.get("proposal", {}).get("published") is not False
    ):
        raise ValueError("Checkpoint não está disponível para revisão local")
    if run["status"] == "completed":
        before_review = dict(state)
        reviewed_digest = before_review.pop("reviewed_digest", None)
        expected_review = fingerprint({"id": run["id"], "stage": run["stage"],
                                       "steps": run["steps"], "state": before_review})
        if reviewed_digest != expected_review:
            raise ValueError("Aprovação final não corresponde ao checkpoint")
    execution = execution_bundle(state)
    bundle = RepositoryBundle.model_validate(state["bundle"])
    if (
        state.get("approved_execution") != execution.digest
        or state.get("test_result", {}).get("artifact_digest") != execution.digest
        or state.get("test_result", {}).get("status") != "passed"
    ):
        raise ValueError("Conteúdo não corresponde aos testes aprovados")
    workspace = TaskWorkspace(workspace_root, run["id"])
    branch = "codex/ai-team/task-" + run["id"]
    if (
        workspace.git("remote").strip()
        or workspace.git("branch", "--show-current").strip() != branch
    ):
        raise ValueError("Workspace não está isolado na branch da tarefa")
    if (
        workspace.git("diff", "--no-ext-diff", "--no-textconv", "--name-only").strip()
        or workspace.git("ls-files", "--others", "--exclude-standard").strip()
        or workspace.git("diff", "--cached", "--no-ext-diff", "--no-textconv", "--binary")
        != state.get("diff")
    ):
        raise ValueError("Workspace diverge do diff revisado")
    entries = workspace.git("ls-files", "--stage").splitlines()
    expected = {}
    for file in execution.files:
        raw = file.content.encode("utf-8")
        sha = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        expected[file.path] = f"100644 {sha} 0\t{file.path}"
    if set(entries) != set(expected.values()):
        raise ValueError("Índice Git não corresponde aos bytes aprovados")
    return {
        "published": False, "external_approval_required": True,
        "checkpoint_digest": checkpoint, "execution_digest": execution.digest,
        "bundle_digest": bundle.digest, "base_sha": bundle.policy.base_sha,
        "base_branch": bundle.policy.base_branch, "branch": branch,
        "local_tree_sha": workspace.git("write-tree").strip(),
        "files": [{"path": bundle.policy.directory + "/" + file.path,
                   "sha256": hashlib.sha256(file.content.encode()).hexdigest(),
                   "git_blob_sha": expected[file.path].split()[1]} for file in bundle.files],
    }
