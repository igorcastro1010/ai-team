"""Contract tests for a local-only prepublication manifest; no external writes."""

import copy

import pytest
from test_repository_flow import advance
from test_repository_flow import setup as setup

from ai_team.repository_policy import fingerprint
from ai_team.repository_review import prepare_publication


def reviewed(setup):
    store, queue, run = setup
    for _ in range(5):
        advance(store, queue)
    store.decide(run.id, store.view(run.id)["digest"], True, "owner")
    advance(store, queue)
    advance(store, queue)
    return store, store.view(run.id)


def test_multifile_manifest_matches_real_git_index_and_never_publishes(setup):
    store, view = reviewed(setup)
    result = prepare_publication(view, store.root)
    assert len(result["files"]) == 3
    assert result["published"] is False and result["external_approval_required"] is True
    assert result["checkpoint_digest"] == view["digest"]
    assert len(result["local_tree_sha"]) == 40
    assert all(file["path"].startswith("tools/") for file in result["files"])


@pytest.mark.parametrize("tamper", ["checkpoint", "content", "tests", "workspace"])
def test_manifest_rejects_stale_approval_failed_tests_and_workspace_changes(setup, tamper):
    store, original = reviewed(setup)
    view = copy.deepcopy(original)
    if tamper == "checkpoint":
        view["digest"] = "0" * 64
    elif tamper == "content":
        view["state"]["bundle"]["files"][0]["content"] = "value = 9\n"
    elif tamper == "tests":
        view["state"]["test_result"]["status"] = "failed"
    else:
        (store.root / view["run"]["id"] / "budget.py").write_text("value = 9\n")
    if tamper in {"content", "tests"}:
        run = view["run"]
        view["digest"] = fingerprint({"id": run["id"], "stage": run["stage"],
                                      "steps": run["steps"], "state": view["state"]})
    with pytest.raises(ValueError):
        prepare_publication(view, store.root)
