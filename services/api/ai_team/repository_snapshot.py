"""Bounded Git Database reads, never follows symlinks or downloads a whole repo."""

import base64
import re

from .github_client import REPOSITORY
from .repository_policy import RepositoryFile, RepositoryPolicy


def read_snapshot(client, policy):
    policy = RepositoryPolicy.model_validate(policy.model_dump())
    verified = client.verify()
    token = client._token(verified, {"contents": "read"})
    root = f"/repos/{REPOSITORY}/git"
    commit = client._request("GET", root + "/commits/" + policy.base_sha, token)
    if commit.get("sha") != policy.base_sha:
        raise ValueError("SHA da origem divergente")
    tree_sha = commit["tree"]["sha"]
    for directory in policy.directory.split("/"):
        tree = client._request("GET", root + "/trees/" + tree_sha, token)
        if tree.get("truncated"):
            raise ValueError("Árvore incompleta")
        matches = [e for e in tree["tree"] if e["path"] == directory]
        if len(matches) != 1 or matches[0].get("mode") != "040000":
            raise ValueError("Pasta autorizada inexistente ou não regular")
        tree_sha = matches[0]["sha"]
    tree = client._request("GET", root + "/trees/" + tree_sha, token)
    if tree.get("truncated"):
        raise ValueError("Árvore incompleta")
    entries = {e["path"]: e for e in tree["tree"]}
    if any(p in entries and p not in policy.read_paths for p in policy.write_paths):
        raise ValueError("Arquivo existente precisa de autorização de leitura antes da escrita")
    files = {}
    for path in policy.read_paths:
        entry = entries.get(path, {})
        if entry.get("mode") != "100644" or entry.get("type") != "blob":
            raise ValueError("Somente arquivos de texto regulares autorizados")
        if not 0 < entry.get("size", 16001) <= 16000:
            raise ValueError("Arquivo excede limite")
        if not re.fullmatch(r"[a-f0-9]{40}", entry["sha"]):
            raise ValueError("Blob inválido")
        blob = client._request("GET", root + "/blobs/" + entry["sha"], token)
        if blob.get("encoding") != "base64":
            raise ValueError("Codificação inválida")
        content = base64.b64decode(blob["content"], validate=False).decode("utf-8")
        file = RepositoryFile(path=path, content=content)
        # Defense in depth: authorized code is still not a credential source.
        if re.search(
            r"-----BEGIN .*PRIVATE KEY|(?:gh[pousr]_|vcp_|sk-proj-)[A-Za-z0-9]{16}", content
        ):
            raise ValueError("Possível credencial no arquivo autorizado")
        files[path] = file.content
    if sum(len(v.encode()) for v in files.values()) > 49152:
        raise ValueError("Snapshot excede 48 KiB")
    return files
