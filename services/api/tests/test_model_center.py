import pytest
from fastapi import HTTPException
from test_api import app as app
from test_api import client as client
from test_api import login


def project(client):
    login(client)
    return client.post("/projects", json={"name": "Central"}).json()["id"]


def test_preferences_are_project_scoped_and_default_to_no_inference(client, app):
    from ai_team.model_center import ModelCenter, Preference

    first, second = project(client), project(client)
    store = ModelCenter(app.state.database)
    assert not store.preference(first, "CEO")["enabled"]
    store.configure(
        first, "CEO", Preference(mode="manual", provider="codex", model="codex-supervised"), "owner"
    )
    assert store.preference(first, "CEO")["provider"] == "codex"
    assert store.preference(second, "CEO")["provider"] == "gemini"
    for data in ({"provider": "openai-paid"}, {"model": "veo-3"}, {"rpm": 100}):
        with pytest.raises(ValueError):
            Preference(**data)


def test_central_request_is_idempotent_and_requires_immutable_content(client, app):
    from ai_team.model_center import ModelCenter

    pid = project(client)
    store = ModelCenter(app.state.database)
    first = store.request(pid, "request-1", "Planejar uma fila Python simples", "owner")
    same = store.request(pid, "request-1", "Planejar uma fila Python simples", "owner")
    assert same.id == first.id and first.executor == "central" and first.calls == 0
    with pytest.raises(HTTPException) as error:
        store.request(pid, "request-1", "Outro conteúdo diferente", "owner")
    assert error.value.status_code == 409
    assert store.snapshot(project(client))["history"] == []


def test_preflight_never_dispatches_when_permission_or_quota_is_unknown(client, app):
    from ai_team.model_center import CentralDeferred, ModelCenter

    pid = project(client)
    store = ModelCenter(app.state.database)
    run = store.request(pid, "blocked-1", "Planejar tarefas simples", "owner")
    with pytest.raises(CentralDeferred) as error:
        store.choose(run, "CEO")
    assert error.value.status == "waiting_model"
    assert store.snapshot(pid)["history"][0]["reason"]


def test_shared_google_project_quota_serializes_across_ai_team_projects(client, app):
    from concurrent.futures import ThreadPoolExecutor

    from ai_team.model_center import CentralDeferred, ModelCenter, Preference

    store = ModelCenter(app.state.database)
    first, second = project(client), project(client)
    policy = Preference(enabled=True, quotas_confirmed=True)
    for pid in (first, second):
        store.configure(pid, "CEO", policy, "owner")
    runs = [
        store.request(pid, str(index), "Plano de tarefa simples", "owner")
        for index, pid in enumerate((first, second, first))
    ]

    def admit(run):
        try:
            return store.admit(run, "CEO", "123456789", 1000)
        except CentralDeferred:
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = list(pool.map(admit, runs))
    assert sum(value is not None for value in outcomes) == 2
    with pytest.raises(CentralDeferred):
        store.admit(runs[0], "CEO", "123456789", 1000)
