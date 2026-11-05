from test_api import app as app
from test_api import client as client
from test_api import login


def test_optimizer_routes_require_owner_csrf_and_project(client):
    url = "/projects/missing/optimizer"
    assert client.get(url).status_code == 401
    login(client)
    assert client.get(url).status_code == 404
    project = client.post("/projects", json={"name": "Contexto"}).json()["id"]
    url = f"/projects/{project}/optimizer"
    assert (
        client.put(
            url + "/budgets",
            json={"scope": "project", "limit": 100},
            headers={"origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert client.put(url + "/budgets", json={"scope": "project", "limit": 100}).status_code == 200
    assert client.get(url).json()["budgets"][0]["limit"] == 100
    response = client.post(
        url + "/preview",
        json={"context": {"request": "Python", "snapshot": {"main.py": "required"}}, "budget": 1},
    )
    assert response.status_code == 200
    assert response.json()["context"]["snapshot"] == {"main.py": "required"}
    assert response.json()["measured_savings"] is None


def test_optimizer_preview_rejects_oversized_payload(client):
    login(client)
    project = client.post("/projects", json={"name": "Limites"}).json()["id"]
    response = client.post(
        f"/projects/{project}/optimizer/preview", json={"context": {"request": "x" * 250001}}
    )
    assert response.status_code == 422
