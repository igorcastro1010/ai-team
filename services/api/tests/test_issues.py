import pytest
from fastapi import HTTPException
from test_api import app as app
from test_api import client as client
from test_api import login


def setup_issue(client):
    login(client)
    project = client.post("/projects", json={"name": "Issues"}).json()
    return {
        "project_id": project["id"],
        "request_id": "request-001",
        "title": "Issue supervisionada",
        "body": "Critérios revisáveis",
    }


def test_issue_local_proposal_persists_dedup_and_requires_digest(client, app):
    from ai_team.github_actions import GitHubStore
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    store = IssueStore(app.state.database)
    row = store.create(data, "igor")
    assert IssueStore(app.state.database).create(data, "igor")["id"] == row["id"]
    assert store.list(data["project_id"])["issues"][0]["id"] == row["id"]
    assert GitHubStore(app.state.database).claim() is None
    with pytest.raises(HTTPException) as error:
        store.create({**data, "title": "Conteúdo diferente"}, "igor")
    assert error.value.status_code == 409
    GitHubStore(app.state.database).decide(
        row["action"]["id"], row["action"]["digest"], True, "igor"
    )
    assert GitHubStore(app.state.database).claim().id == row["action"]["id"]


def test_issue_task_project_scope_and_local_links(client, app):
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    other = client.post("/projects", json={"name": "Other"}).json()
    task = client.post(
        "/tasks", json={"project_id": other["id"], "title": "Outra tarefa", "agent": "DEV"}
    ).json()
    store = IssueStore(app.state.database)
    with pytest.raises(HTTPException):
        store.create({**data, "task_id": task["id"]}, "igor")
    parent = store.create(data, "igor")
    child = store.create(
        {
            **data,
            "request_id": "child",
            "parent_issue_id": parent["id"],
            "agent": "QA",
            "priority": "high",
        },
        "igor",
    )
    assert child["parent_issue_id"] == parent["id"]
    assert len(store.list(data["project_id"], agent="QA", priority="high")["issues"]) == 1
    updated = store.update(
        child["id"],
        {
            "status": "done",
            "branch": "codex/ai-team/example",
            "commit_sha": "a" * 40,
            "pull_request_number": 12,
        },
        "igor",
    )
    assert updated["status"] == "done" and updated["action"]["digest"] == child["action"]["digest"]
    assert store.list(other["id"])["issues"] == []


def test_ceo_delegation_prepares_local_issue_without_publication(client, app):
    from ai_team.github_actions import GitHubStore
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    task = client.post(
        "/tasks", json={"project_id": data["project_id"], "title": "Tarefa do CEO", "agent": "DEV"}
    ).json()
    row = IssueStore(app.state.database).prepare_task(task["id"], "ceo-task-001")
    assert row["task_id"] == task["id"] and row["agent"] == "DEV"
    assert GitHubStore(app.state.database).claim() is None


def test_concurrent_request_id_creates_one_issue_and_one_action(client, app):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import func, select

    from ai_team.github_actions import GitHubStore
    from ai_team.issue_models import IssueLink
    from ai_team.issue_store import IssueStore
    from ai_team.models import GitHubAction

    data = setup_issue(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(
            pool.map(lambda _: IssueStore(app.state.database).create(data, "igor"), range(2))
        )
    assert rows[0]["id"] == rows[1]["id"]
    with app.state.database.session() as db:
        assert db.scalar(select(func.count()).select_from(IssueLink)) == 1
        assert db.scalar(select(func.count()).select_from(GitHubAction)) == 1
    assert GitHubStore(app.state.database).claim() is None


def test_remote_issue_sync_only_after_publication_and_does_not_mutate_proposal(client, app):
    from ai_team.github_actions import GitHubStore
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    store = IssueStore(app.state.database)
    issue = store.create(data, "igor")
    calls = []

    class Reader:
        def issue(self, number):
            calls.append(number)
            return {
                "number": 17,
                "state": "closed",
                "html_url": "https://github.com/igorcastro1010/ai-team/issues/17",
            }

    with pytest.raises(HTTPException):
        store.sync(issue["id"], Reader(), "igor")
    assert calls == []
    queue = GitHubStore(app.state.database)
    queue.decide(issue["action"]["id"], issue["action"]["digest"], True, "igor")
    claim = queue.claim()
    queue.finish(
        claim,
        "succeeded",
        {"number": 17, "url": "https://github.com/igorcastro1010/ai-team/issues/17"},
    )
    result = store.sync(issue["id"], Reader(), "igor")
    assert result["remote_state"] == "closed" and result["synced_at"] > 0
    assert result["status"] == "todo"
    assert result["action"]["digest"] == issue["action"]["digest"]
    assert calls == [17]


def test_uncertain_issue_never_replayed_even_for_duplicate_request(client, app):
    from ai_team.github_actions import GitHubStore, GitHubWorker
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    store = IssueStore(app.state.database)
    issue = store.create(data, "igor")
    queue = GitHubStore(app.state.database)
    queue.decide(issue["action"]["id"], issue["action"]["digest"], True, "igor")
    attempts = []

    class LostResponse:
        mutation_attempted = True

        def execute(self, payload):
            attempts.append(payload)
            raise RuntimeError("lost response")

        def close(self):
            pass

    assert GitHubWorker(app.state.database, provider_factory=LostResponse).once()
    assert store.create(data, "igor")["action"]["status"] == "uncertain"
    assert not GitHubWorker(app.state.database, provider_factory=LostResponse).once()
    assert len(attempts) == 1


@pytest.mark.parametrize("secret", ["ghp_" + "a" * 30, "-----BEGIN PRIVATE KEY-----"])
def test_issue_credentials_in_title_are_rejected(client, app, secret):
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    with pytest.raises(ValueError):
        IssueStore(app.state.database).create({**data, "title": secret}, "igor")


@pytest.mark.parametrize(
    "remote",
    [
        {"number": 17, "state": "closed", "html_url": "https://github.com/other/repo/issues/17"},
        {
            "number": 18,
            "state": "open",
            "html_url": "https://github.com/igorcastro1010/ai-team/issues/17",
        },
        {
            "number": 17,
            "state": "open",
            "html_url": "https://github.com/igorcastro1010/ai-team/issues/17",
            "pull_request": {},
        },
    ],
)
def test_sync_rejects_other_repository_number_or_pull_request(client, app, remote):
    from ai_team.github_actions import GitHubStore
    from ai_team.github_client import GitHubError
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    store = IssueStore(app.state.database)
    issue = store.create(data, "igor")
    queue = GitHubStore(app.state.database)
    queue.decide(issue["action"]["id"], issue["action"]["digest"], True, "igor")
    claim = queue.claim()
    queue.finish(claim, "succeeded", {"number": 17})

    class Reader:
        def issue(self, number):
            return remote

    with pytest.raises(GitHubError):
        store.sync(issue["id"], Reader(), "igor")
    assert store.list(data["project_id"])["issues"][0]["synced_at"] == 0


def test_dedup_survives_new_database_engine_and_wrong_digest_cannot_approve(client, app):
    from ai_team.db import Database
    from ai_team.github_actions import GitHubStore
    from ai_team.issue_store import IssueStore

    data = setup_issue(client)
    original = IssueStore(app.state.database).create(data, "igor")
    settings = app.state.settings
    reopened = Database(settings)
    try:
        repeated = IssueStore(reopened).create(data, "igor")
        assert repeated["id"] == original["id"]
        with pytest.raises(HTTPException) as error:
            GitHubStore(reopened).decide(original["action"]["id"], "0" * 64, True, "igor")
        assert error.value.status_code == 409
        assert GitHubStore(reopened).claim() is None
    finally:
        reopened.engine.dispose()
