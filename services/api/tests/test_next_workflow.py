import io
import json
import zipfile

from test_code_workflow import Sandbox
from test_next_sandbox import steps
from test_workflow import environment as environment

from ai_team.orchestration import Draft
from ai_team.worker import Worker
from ai_team.workflow import WorkflowStore


class NextProvider:
    def ready(self):
        return True

    def generate(self, role, instructions, context, on_tick):
        artifacts = {step["agent"]: step["deliverable"] for step in steps()}
        return Draft(
            summary=f"Parecer {role}",
            tasks=[],
            deliverable=artifacts.get(role, "Plano e relatório Next.js"),
            input_tokens=10,
            output_tokens=10,
        )


def test_next_approval_build_and_report_use_separate_leases_without_repeating(
    environment, monkeypatch
):
    client, database, settings = environment
    project = client.post("/projects", json={"name": "Next local", "mode": "automatic"}).json()
    response = client.post(
        "/runs",
        json={
            "project_id": project["id"],
            "prompt": "Crie uma página Next.js AI TEAM",
            "scope": "nextjs_code",
            "executor": "hermes",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    run = response.json()
    store = WorkflowStore(database)
    sandbox = Sandbox()
    worker = Worker(database, settings, NextProvider(), sandbox=sandbox)
    for _ in range(4):
        worker.once()
    reviewed = client.get(f"/runs/{run['id']}").json()
    assert reviewed["stage"] == 4 and reviewed["status"] == "awaiting_approval"
    decision = {"stage": 4, "approve": True, "artifact_digest": reviewed["artifact_digest"]}
    assert client.post(f"/runs/{run['id']}/decision", json=decision).status_code == 200
    worker.once()
    built = store.get(run["id"])
    assert built.status == "queued" and built.stage == 4 and built.calls == 4
    assert built.steps[3]["test_result"]["status"] == "passed"
    worker.once()
    completed = store.get(run["id"])
    assert completed.status == "completed" and completed.calls == 5
    assert sandbox.calls == 1
    from ai_team import next_artifacts

    original = next_artifacts.scaffold()
    changed = {**original, "next.config.mjs": "export default {poweredByHeader:true};"}
    monkeypatch.setattr(next_artifacts, "scaffold", lambda: changed)
    historic = client.get(f"/runs/{run['id']}").json()
    assert historic["artifact_digest"] == reviewed["artifact_digest"]
    download = client.get(f"/runs/{run['id']}/artifacts")
    assert "ai-team-nextjs.zip" in download.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert archive.read("next.config.mjs").decode() == original["next.config.mjs"]
        assert {
            "package.json",
            "package-lock.json",
            "app/layout.tsx",
            "app/page.tsx",
            "app/globals.css",
            "tests/acceptance.json",
        } <= set(archive.namelist())


def test_next_codegen_does_not_change_hermes_tool_authorization():
    from ai_team.orchestration import build_graph

    provider = NextProvider()
    state = build_graph(provider, lambda: None).invoke(
        {
            "scope": "nextjs_code",
            "stage": 2,
            "prompt": "Página local",
            "steps": [],
        }
    )
    assert json.loads(state["draft"]["deliverable"])["files"][0]["path"] == "app/globals.css"


def test_server_snapshot_is_not_sent_to_the_model():
    from ai_team.orchestration import build_graph

    class InspectProvider(NextProvider):
        def generate(self, role, instructions, context, on_tick):
            assert context["previous_steps"] == [
                {"agent": "QA", "test_result": {"status": "passed"}}
            ]
            return super().generate(role, instructions, context, on_tick)

    build_graph(InspectProvider(), lambda: None).invoke(
        {
            "scope": "nextjs_code",
            "stage": 4,
            "prompt": "Relatório",
            "steps": [
                {
                    "agent": "QA",
                    "project_snapshot": {"huge": "lockfile"},
                    "test_result": {"status": "passed"},
                }
            ],
        }
    )
