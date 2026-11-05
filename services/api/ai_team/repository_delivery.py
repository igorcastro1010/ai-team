"""Fixed Git Database operations. No force update, merge, deletion or deployment."""

import uuid
from urllib.parse import quote

from .github_client import REPOSITORY
from .repository_policy import RepositoryBundle


def publish(client, run_id, bundle, title, body):
    run_id = str(uuid.UUID(run_id))
    bundle = RepositoryBundle.model_validate(bundle.model_dump())
    policy = bundle.policy
    verified = client.verify()
    token = client._token(verified, {"contents": "write", "pull_requests": "write"})
    root = f"/repos/{REPOSITORY}"
    ref = client._request(
        "GET", root + "/git/ref/heads/" + quote(policy.base_branch, safe=""), token
    )
    if ref["object"]["sha"] != policy.base_sha:
        raise ValueError("Branch de origem mudou; é necessária nova revisão")
    parent = client._request("GET", root + "/git/commits/" + policy.base_sha, token)
    tree = client._request(
        "POST",
        root + "/git/trees",
        token,
        expected=201,
        body={
            "base_tree": parent["tree"]["sha"],
            "tree": [
                {
                    "path": policy.directory + "/" + file.path,
                    "mode": "100644",
                    "type": "blob",
                    "content": file.content,
                }
                for file in bundle.files
            ],
        },
    )
    commit = client._request(
        "POST",
        root + "/git/commits",
        token,
        expected=201,
        body={
            "message": title[:140],
            "parents": [policy.base_sha],
            "tree": tree["sha"],
        },
    )
    branch = "codex/ai-team/task-" + run_id
    client._request(
        "POST",
        root + "/git/refs",
        token,
        expected=201,
        body={"ref": "refs/heads/" + branch, "sha": commit["sha"]},
    )
    pr = client._request(
        "POST",
        root + "/pulls",
        token,
        expected=201,
        body={
            "title": title[:140],
            "head": branch,
            "base": policy.base_branch,
            "body": body[:20000],
            "draft": True,
        },
    )
    expected = f"https://github.com/{REPOSITORY}/pull/{pr['number']}"
    if pr.get("html_url") != expected:
        raise ValueError("Endereço de PR inesperado")
    return {"status": "published", "url": expected, "sha": commit["sha"], "branch": branch}
