"""Review an existing disposable homologation. No inference or repository writes."""

import argparse
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import quote

from ai_team.config import ROOT, Settings
from ai_team.db import Database
from ai_team.github_client import REPOSITORY, GitHubClient
from ai_team.repository_review import prepare_publication
from ai_team.repository_runs import RepositoryStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--approve-test-review", action="store_true")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    db_path = Path(evidence["database"]).resolve()
    if (
        db_path.parent != (ROOT / ".data").resolve() or not db_path.is_file()
        or not re.fullmatch(r"v06-(?:hermes|codex)-smoke-[a-f0-9-]{36}\.db", db_path.name)
    ):
        parser.error("Somente banco descartável de homologação dentro de .data")
    database = Database(Settings(database_url=f"sqlite:///{db_path}", environment="test"))
    store = RepositoryStore(database)
    try:
        run_id = evidence["view"]["run"]["id"]
        view = store.view(run_id)
        manifest = prepare_publication(view, store.root)
        if args.approve_test_review and view["run"]["status"] == "awaiting_approval":
            # Local test-review consent is separate from external /publish authorization.
            store.decide(run_id, view["digest"], True, "homologacao-local")
            view = store.view(run_id)
            manifest = prepare_publication(view, store.root)
        policy = view["state"]["policy"]
        client = GitHubClient()
        try:
            verified = client.verify()
            token = client._token(verified, {"contents": "read"})
            root = "/repos/" + REPOSITORY
            base = client._request("GET", root + "/git/commits/" + policy["base_sha"], token)
            if base.get("sha") != policy["base_sha"]:
                raise ValueError("SHA base divergente")
            current = client._request(
                "GET", root + "/git/ref/heads/" + quote(policy["base_branch"], safe=""), token
            )["object"]["sha"]
            if client.mutation_attempted:
                raise ValueError("Prévia não admite escrita remota")
        finally:
            client.close()
        manifest.update(
            run_id=run_id, current_base_sha=current,
            base_branch_matches=current == policy["base_sha"],
            reviewed_checkpoint_digest=view["state"].get("reviewed_digest"),
            publication_authorized=False,
            git_tree_request={"base_tree": base["tree"]["sha"], "tree": [
                {"path": policy["directory"] + "/" + file["path"], "mode": "100644",
                 "type": "blob", "content": file["content"]}
                for file in view["state"]["bundle"]["files"]
            ]},
        )
        output = ROOT / "artifacts" / f"v061-prepublication-{run_id}"
        output.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with zipfile.ZipFile(output.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
            for file in view["state"]["bundle"]["files"]:
                archive.writestr(file["path"], file["content"])
            archive.writestr("review.diff", view["state"]["diff"])
            archive.writestr("test-output.txt", view["state"]["test_result"]["output"])
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        print(json.dumps({"run_id": run_id, "files": len(manifest["files"]),
                          "status": "prepared", "published": False,
                          "base_branch_matches": manifest["base_branch_matches"],
                          "manifest": str(output.with_suffix('.json'))}))
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
