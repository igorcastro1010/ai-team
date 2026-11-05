"""Fixed Git Database operations. No force update, merge, deletion or deployment."""

import hashlib
import uuid
from urllib.parse import quote

from .github_client import REPOSITORY
from .repository_policy import RepositoryBundle


def verify_commit(client, token, root, bundle, commit_sha, tree_sha):
    """Read back immutable objects before making the commit reachable by a branch."""
    policy = bundle.policy
    commit = client._request("GET", root + "/git/commits/" + commit_sha, token)
    if (
        commit.get("sha") != commit_sha
        or commit.get("tree", {}).get("sha") != tree_sha
        or [parent.get("sha") for parent in commit.get("parents", [])] != [policy.base_sha]
    ):
        raise ValueError("Commit remoto não corresponde à árvore/base revisadas")
    expected = {}
    for file in bundle.files:
        content = file.content.encode("utf-8")
        expected[policy.directory + "/" + file.path] = hashlib.sha1(
            f"blob {len(content)}\0".encode() + content
        ).hexdigest()
    comparison = client._request(
        "GET", root + f"/compare/{policy.base_sha}...{commit_sha}", token
    )
    files = comparison.get("files", [])
    paths = [file.get("filename") for file in files]
    if (
        comparison.get("status") != "ahead"
        or comparison.get("ahead_by") != 1 or comparison.get("total_commits") != 1
        or not files or len(paths) != len(set(paths))
        or not set(paths).issubset(expected)
        or any(file.get("status") not in {"added", "modified"}
               or file.get("sha") != expected[file["filename"]] for file in files)
    ):
        raise ValueError("Diff remoto contém alterações fora do conteúdo aprovado")
    # A generated file can be identical to its snapshot, hence absent from the diff.
    for path in expected.keys() - set(paths):
        file = client._request(
            "GET", root + "/contents/" + quote(path, safe="/") + "?ref=" + commit_sha, token
        )
        if file.get("type") != "file" or file.get("sha") != expected[path]:
            raise ValueError("Arquivo remoto diverge do conteúdo aprovado")
    return sorted(expected)


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
    verified_paths = verify_commit(client, token, root, bundle, commit["sha"], tree["sha"])
    branch = "codex/ai-team/task-" + run_id
    client._request(
        "POST",
        root + "/git/refs",
        token,
        expected=201,
        body={"ref": "refs/heads/" + branch, "sha": commit["sha"]},
    )
    current = client._request("GET", root + "/git/ref/heads/" + quote(branch, safe=""), token)
    if current.get("object", {}).get("sha") != commit["sha"]:
        raise ValueError("Branch de entrega alterada; publicação exige revisão")
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
    if pr.get("html_url") != expected or pr.get("head", {}).get("sha") != commit["sha"]:
        raise ValueError("PR não corresponde ao commit revisado")
    return {
        "status": "published", "url": expected, "sha": commit["sha"], "branch": branch,
        "tree_sha": tree["sha"], "bundle_digest": bundle.digest, "verified_paths": verified_paths,
    }
