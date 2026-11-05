import pytest
from test_api import app as app
from test_api import client as client
from test_issues import setup_issue


def test_issue_api_auth_origin_and_filters(client):
    assert client.get("/issues?project_id=missing").status_code == 401
    assert client.post("/issues", json={}).status_code == 401
    data = setup_issue(client)
    assert (
        client.post("/issues", json=data, headers={"origin": "https://evil.example"}).status_code
        == 403
    )
    response = client.post("/issues", json=data)
    assert response.status_code == 201
    issue = response.json()
    assert client.post("/issues", json=data).json()["id"] == issue["id"]
    assert (
        client.get("/issues", params={"project_id": data["project_id"]}).json()["issues"][0]["id"]
        == issue["id"]
    )
    assert (
        client.patch(f"/issues/{issue['id']}", json={"status": "done"}).json()["status"] == "done"
    )
    assert (
        client.patch(f"/issues/{issue['id']}", json={"title": "Mutation interdite"}).status_code
        == 422
    )
    assert client.post(f"/issues/{issue['id']}/sync").status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"branch": "../main"},
        {"commit_sha": "bad"},
        {"pull_request_number": -1},
        {"agent": "shell"},
        {"request_id": "http://evil/x"},
    ],
)
def test_issue_invalid_metadata_denied(client, changes):
    data = setup_issue(client)
    assert client.post("/issues", json={**data, **changes}).status_code == 422


@pytest.mark.parametrize(
    "changes", [{"title": "ghp_" + "a" * 30}, {"body": "-----BEGIN PRIVATE KEY-----"}]
)
def test_issue_api_credentials_are_validation_errors(client, changes):
    data = setup_issue(client)
    assert client.post("/issues", json={**data, **changes}).status_code == 422


def test_issue_patch_invalid_links_preserve_original_proposal(client):
    data = setup_issue(client)
    issue = client.post("/issues", json=data).json()
    for changes in [{"branch": "main"}, {"commit_sha": "bad"}, {"agent": None}]:
        assert client.patch(f"/issues/{issue['id']}", json=changes).status_code == 422
    fetched = client.get("/issues", params={"project_id": data["project_id"]}).json()["issues"][0]
    assert fetched["branch"] == "" and fetched["commit_sha"] == ""
    assert fetched["action"]["digest"] == issue["action"]["digest"]
