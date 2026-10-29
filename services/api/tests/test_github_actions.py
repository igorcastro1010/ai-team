import time

import pytest
from test_api import app as app
from test_api import client as client
from test_api import login


def proposal(client, **changes):
    project = client.post("/projects", json={"name": "GitHub testing"}).json()
    return {
        "project_id": project["id"],
        "operation": "branch",
        "title": "Criar branch revisada",
        "branch": "codex/ai-team/test",
        "expected_sha": "a" * 40,
        **changes,
    }


def test_github_routes_require_login_and_origin(client):
    assert client.get("/github").status_code == 401
    assert client.post("/github/proposals", json={}).status_code == 401
    assert (
        client.post("/github/verify", headers={"origin": "https://evil.example"}).status_code == 403
    )


def test_immutable_approval_and_single_claim_survive_restart(client, app):
    from ai_team.github_actions import GitHubStore

    login(client)
    data = proposal(client)
    response = client.post("/github/proposals", json=data)
    assert response.status_code == 201
    action = response.json()
    store = GitHubStore(app.state.database)
    assert store.claim() is None
    url = f"/github/proposals/{action['id']}/decision"
    assert client.post(url, json={"digest": "wrong", "approve": True}).status_code == 409
    assert client.post(url, json={"digest": action["digest"], "approve": True}).status_code == 200
    assert client.post(url, json={"digest": action["digest"], "approve": True}).status_code == 409
    claimed = GitHubStore(app.state.database).claim()
    assert claimed.id == action["id"]
    assert store.claim() is None
    store.finish(claimed, "succeeded", {"url": "https://github.com/igorcastro1010/ai-team"})
    assert client.get("/github").json()["actions"][0]["status"] == "succeeded"


@pytest.mark.parametrize(
    "changes",
    [
        {"branch": "main"},
        {"branch": "codex/other"},
        {"expected_sha": "bad"},
        {"operation": "delete"},
        {"operation": "commit", "path": ".env", "content": "x"},
        {"operation": "commit", "path": ".github/workflows/test.yml", "content": "x"},
        {"operation": "commit", "path": "docs/agent-output/../secrets.md", "content": "x"},
    ],
)
def test_dangerous_or_invalid_proposals_are_rejected(client, changes):
    login(client)
    assert client.post("/github/proposals", json=proposal(client, **changes)).status_code == 422


def test_rejection_prevents_execution_and_stale_execution_is_not_retried(client, app):
    from ai_team.github_actions import GitHubStore
    from ai_team.models import GitHubAction

    login(client)
    action = client.post("/github/proposals", json=proposal(client)).json()
    url = f"/github/proposals/{action['id']}/decision"
    client.post(url, json={"digest": action["digest"], "approve": False})
    store = GitHubStore(app.state.database)
    assert store.claim() is None
    next_action = client.post("/github/proposals", json=proposal(client)).json()
    client.post(
        f"/github/proposals/{next_action['id']}/decision",
        json={"digest": next_action["digest"], "approve": True},
    )
    claim = store.claim()
    with app.state.database.session() as db:
        row = db.get(GitHubAction, claim.id)
        row.lease_expires_at = int(time.time()) - 1
        db.commit()
    assert store.claim() is None
    assert store.snapshot()["actions"][0]["status"] == "uncertain"


def test_executor_revalidates_policy_even_after_database_tampering(client, app):
    from ai_team.github_actions import GitHubStore, GitHubWorker
    from ai_team.models import GitHubAction

    login(client)
    action = client.post("/github/proposals", json=proposal(client)).json()
    client.post(
        f"/github/proposals/{action['id']}/decision",
        json={"digest": action["digest"], "approve": True},
    )
    with app.state.database.session() as db:
        row = db.get(GitHubAction, action["id"])
        row.payload = {**row.payload, "branch": "main"}
        db.commit()

    network_calls = []

    class NoNetwork:
        def __init__(self):
            network_calls.append(True)
            raise AssertionError("No network before policy validation")

    assert GitHubWorker(app.state.database, provider_factory=NoNetwork).once()
    assert network_calls == []
    assert GitHubStore(app.state.database).snapshot()["actions"][0]["status"] == "failed"


def test_two_workers_cannot_claim_the_same_approved_action(client, app):
    from concurrent.futures import ThreadPoolExecutor

    from ai_team.github_actions import GitHubStore

    login(client)
    action = client.post("/github/proposals", json=proposal(client)).json()
    client.post(
        f"/github/proposals/{action['id']}/decision",
        json={"digest": action["digest"], "approve": True},
    )

    def claim(_):
        return GitHubStore(app.state.database).claim()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert len([result for result in results if result is not None]) == 1


def test_worker_cycle_services_text_and_github_queues():
    from ai_team.worker import process_cycle

    calls = []

    class Queue:
        def __init__(self, name):
            self.name = name

        def once(self):
            calls.append(self.name)
            return True

    assert process_cycle(Queue("text"), Queue("github"))
    assert calls == ["text", "github"]


def test_old_pending_proposal_remains_visible_after_200_results(client, app):
    from ai_team.github_actions import GitHubStore
    from ai_team.models import GitHubAction

    login(client)
    action = client.post("/github/proposals", json=proposal(client)).json()
    with app.state.database.session() as db:
        for _ in range(201):
            db.add(
                GitHubAction(
                    project_id=action["project_id"],
                    payload=action["payload"],
                    digest=action["digest"],
                    status="succeeded",
                )
            )
        db.commit()
    assert GitHubStore(app.state.database).snapshot()["actions"][0]["id"] == action["id"]


def test_racing_pull_request_preserves_url_for_reconciliation(client, app):
    from ai_team.github_actions import GitHubStore, GitHubWorker

    login(client)
    action = client.post("/github/proposals", json=proposal(client)).json()
    client.post(
        f"/github/proposals/{action['id']}/decision",
        json={"digest": action["digest"], "approve": True},
    )

    class RacingProvider:
        def execute(self, payload):
            return {
                "url": "https://github.com/igorcastro1010/ai-team/pull/999",
                "requires_review": True,
            }

        def close(self):
            pass

    GitHubWorker(app.state.database, provider_factory=RacingProvider).once()
    result = GitHubStore(app.state.database).snapshot()["actions"][0]
    assert result["status"] == "uncertain" and result["result"]["url"].endswith("/pull/999")
