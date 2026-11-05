import json
import os
import subprocess

import pytest
from pydantic import ValidationError

from ai_team.next_artifacts import NextPart, NextProject, project_for_steps, scaffold
from ai_team.next_sandbox import next_command


def steps():
    parts = [
        ("DEV", "app/page.tsx", "export default function Page(){return <h1>AI TEAM</h1>}"),
        ("DESIGNER", "app/globals.css", "body { color: white; background: #111; }"),
        (
            "QA",
            "tests/acceptance.json",
            json.dumps({"checks": [{"name": "titulo", "contains": "AI TEAM"}]}),
        ),
    ]
    return [
        {"agent": role, "deliverable": json.dumps({"files": [{"path": path, "content": code}]})}
        for role, path, code in parts
    ]


@pytest.mark.parametrize(
    "path",
    [
        "../page.tsx",
        "/app/page.tsx",
        "app/../../page.tsx",
        "app/page.js",
        "app/api/route.ts",
        "package.json",
        "next.config.mjs",
        "components/../a.tsx",
    ],
)
def test_generated_next_paths_cannot_change_configuration(path):
    with pytest.raises(ValidationError):
        NextPart(files=[{"path": path, "content": "bad"}])


def test_project_digest_covers_scaffold_and_separates_roles():
    project = project_for_steps(steps())
    assert {
        "app/page.tsx",
        "app/globals.css",
        "tests/acceptance.json",
        "package.json",
        "package-lock.json",
        "app/layout.tsx",
    } <= {f.path for f in project.files}
    assert len(project.digest) == 64
    changed = project.model_dump()
    next(f for f in changed["files"] if f["path"] == "package.json")["content"] = "{}"
    with pytest.raises(ValidationError):
        NextProject(**changed)
    wrong = steps()
    wrong[1]["deliverable"] = wrong[0]["deliverable"]
    with pytest.raises(ValueError):
        project_for_steps(wrong)
    assert scaffold()["package.json"] in [f.content for f in project.files]


def test_qa_is_bounded_declarative_not_commands_or_urls():
    data = steps()
    for bad in (
        {"checks": []},
        {"checks": [{"name": "x", "command": "rm -rf /"}]},
        {"checks": [{"name": "x", "contains": "x", "url": "https://evil.test"}]},
    ):
        data[2]["deliverable"] = json.dumps(
            {"files": [{"path": "tests/acceptance.json", "content": json.dumps(bad)}]}
        )
        with pytest.raises(ValueError):
            project_for_steps(data)


def test_next_fixed_runtime_limits_and_no_host_mounts():
    command = next_command("ai-team-test-" + "a" * 32, "sha256:" + "b" * 64)
    for key, value in [
        ("--network", "none"),
        ("--user", "65532:65532"),
        ("--cpus", "2"),
        ("--memory", "1g"),
        ("--pids-limit", "128"),
    ]:
        assert command[command.index(key) + 1] == value
    assert not {"--mount", "-v", "--volume", "--privileged", "--env-file"} & set(command)
    assert "120s" in command and "--read-only" in command


def test_runtime_manifest_rejects_mutable_images_and_stale_policy(tmp_path, monkeypatch):
    from ai_team import next_sandbox
    from ai_team.next_artifacts import runtime_fingerprint

    path = tmp_path / "image.json"
    monkeypatch.setattr(next_sandbox, "MANIFEST", path)
    for image, fingerprint in [
        ("node:latest", runtime_fingerprint()),
        ("sha256:" + "a" * 64, "stale"),
    ]:
        path.write_text(json.dumps({"image_id": image, "runtime_hash": fingerprint}))
        with pytest.raises(RuntimeError):
            next_sandbox.prepared_image()
    path.write_text(
        json.dumps({"image_id": "sha256:" + "a" * 64, "runtime_hash": runtime_fingerprint()})
    )
    assert next_sandbox.prepared_image() == "sha256:" + "a" * 64


def test_historic_snapshot_is_stable_but_cannot_run_under_changed_runtime(monkeypatch):
    from ai_team import next_artifacts

    data = steps()
    original = project_for_steps(data)
    data[-1]["project_snapshot"] = original.model_dump()
    monkeypatch.setattr(next_artifacts, "runtime_fingerprint", lambda: "0" * 64)
    snapshot = project_for_steps(data)
    assert snapshot.digest == original.digest
    with pytest.raises(ValidationError, match="Runtime aprovado mudou"):
        NextProject.model_validate(snapshot.model_dump())
    data[0]["deliverable"] = data[0]["deliverable"].replace("AI TEAM", "Changed")
    with pytest.raises(ValueError, match="divergentes"):
        project_for_steps(data)


def test_html_reader_preserves_split_accents_and_enforces_byte_limit():
    from ai_team.next_artifacts import RUNTIME

    script = """
import assert from 'node:assert/strict';
import {readHtml} from './read-html.mjs';
const bytes = Buffer.from('Ação e café');
async function* chunks() { for (const byte of bytes) yield Uint8Array.of(byte); }
assert.equal(await readHtml(chunks()), 'Ação e café');
await assert.rejects(readHtml(chunks(), bytes.length - 1), /HTML limit/);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=RUNTIME, check=True, timeout=10
    )


@pytest.mark.skipif(os.getenv("AI_TEAM_NEXT_SANDBOX_TESTS") != "1", reason="Next Docker opt-in")
@pytest.mark.parametrize(
    ("contains", "status"), [("AI TEAM", "passed"), ("missing-heading", "failed")]
)
def test_real_next_build_and_rendered_checks(contains, status):
    from ai_team.next_sandbox import NextSandbox

    data = steps()
    checks = {"checks": [{"name": "conteudo", "contains": contains}]}
    data[2]["deliverable"] = json.dumps(
        {"files": [{"path": "tests/acceptance.json", "content": json.dumps(checks)}]}
    )
    result = NextSandbox().run(project_for_steps(data), lambda: None)
    assert result["status"] == status, result["output"]


@pytest.mark.skipif(os.getenv("AI_TEAM_NEXT_SANDBOX_TESTS") != "1", reason="Next Docker opt-in")
def test_real_premature_next_build_exit_never_passes():
    from ai_team.next_sandbox import NextSandbox

    data = steps()
    data[0]["deliverable"] = json.dumps(
        {
            "files": [
                {
                    "path": "app/page.tsx",
                    "content": "process.exit(0); "
                    "export default function Page(){return <h1>AI TEAM</h1>}",
                }
            ]
        }
    )
    result = NextSandbox().run(project_for_steps(data), lambda: None)
    assert result["status"] == "failed"
