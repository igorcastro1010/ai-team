import pytest
from test_workflow import environment as environment


@pytest.mark.parametrize("origin", ["https://attacker.invalid", ""])
def test_repository_endpoint_rejects_cross_origin(environment, origin):
    client, _, _ = environment
    assert client.post("/repository-runs", headers={"origin": origin}, json={}).status_code == 403


def test_repository_creation_is_authenticated_persistent_and_never_executes_in_http(environment):
    client, db, _ = environment
    project = client.post("/projects", json={"name": "Executor", "mode": "supervised"}).json()
    payload = {
        "project_id": project["id"],
        "prompt": "Improve validation safely",
        "consent": True,
        "policy": {
            "base_sha": "a" * 40,
            "directory": "tools",
            "read_paths": ["budget.py"],
            "write_paths": ["budget.py", "test_budget.py", "guide.md"],
        },
    }
    response = client.post("/repository-runs", json=payload)
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["run"]["status"] == "queued" and view["run"]["calls"] == 0
    assert "snapshot" not in view["state"]
    assert client.get("/repository-runs").json()[0]["run"]["id"] == view["run"]["id"]
    payload["consent"] = False
    assert client.post("/repository-runs", json=payload).status_code == 422
    client.cookies.clear()
    assert client.get("/repository-runs").status_code == 401
    assert client.get("/repository-runs/" + view["run"]["id"]).status_code == 401


def test_research_delegation_remains_visible_in_workspace(environment):
    client, _, _ = environment
    project = client.post("/projects", json={"name": "Research"}).json()
    response = client.post(
        "/tasks",
        json={
            "project_id": project["id"],
            "title": "Pesquisar contratos autorizados",
            "agent": "PESQUISADOR",
        },
    )
    assert response.status_code == 201, response.text
    assert client.get("/workspace").status_code == 200


def test_repository_history_limits_newest_runs_in_stable_order(environment):
    from ai_team.models import Project, RepositoryJob, Run

    client, database, _ = environment
    with database.session() as db:
        project = Project(name="History")
        db.add(project)
        db.flush()
        for index in range(101):
            run = Run(project_id=project.id, prompt=f"Request {index}", mode="manual", scope="repository_code", created_at=index)
            db.add(run)
            db.flush()
            db.add(RepositoryJob(run_id=run.id, state={}))
        db.commit()
    history = client.get("/repository-runs").json()
    assert len(history) == 100
    assert [item["run"]["prompt"] for item in history] == [f"Request {i}" for i in range(100, 0, -1)]
