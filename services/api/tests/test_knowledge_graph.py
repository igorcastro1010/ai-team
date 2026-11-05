import json
import subprocess

import pytest
from fastapi import HTTPException

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Event, GitHubAction, Project, RepositoryJob, Run, Task


@pytest.fixture
def database(tmp_path):
    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'graph.db'}"))
    database.initialize()
    return database


def sample(project_id):
    return {
        "directed": True,
        "multigraph": False,
        "graph": {"project_id": project_id, "schema_version": 1},
        "nodes": [
            {
                "id": "note:one",
                "label": "Planning",
                "kind": "memory",
                "provenance": "memory_entries:one",
            }
        ],
        "links": [],
    }


def test_native_graph_scopes_entities_and_keeps_provenance(database):
    from ai_team.knowledge_graph import KnowledgeGraph

    with database.session() as db:
        db.add_all([Project(id="alpha", name="Alpha"), Project(id="beta", name="Beta")])
        db.flush()
        db.add_all(
            [
                Task(id="t1", project_id="alpha", title="Fix", agent="DEV"),
                Task(id="t2", project_id="beta", title="Private beta", agent="QA"),
                Run(id="r1", project_id="alpha", prompt="Secret prompt", mode="supervised"),
                Run(id="r2", project_id="beta", prompt="Private beta", mode="supervised"),
            ]
        )
        db.flush()
        db.add_all(
            [
                Event(id="e1", kind="repository.decision", resource_id="r1", summary="reviewed"),
                Event(id="e2", kind="repository.decision", resource_id="r2", summary="private"),
                GitHubAction(
                    id="g1",
                    project_id="alpha",
                    digest="a" * 64,
                    status="succeeded",
                    payload={"operation": "commit"},
                    result={"sha": "b" * 40},
                ),
                GitHubAction(
                    id="g2",
                    project_id="alpha",
                    digest="c" * 64,
                    status="pending",
                    payload={"operation": "commit"},
                    result={"sha": "c" * 40},
                ),
            ]
        )
        db.commit()
    graph = KnowledgeGraph(database).snapshot("alpha")
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert {
        "project:alpha",
        "task:t1",
        "run:r1",
        "agent:DEV",
        "decision:e1",
        "commit:" + "b" * 40,
    } <= nodes.keys()
    assert not {"task:t2", "run:r2", "decision:e2", "commit:" + "c" * 40} & nodes.keys()
    assert all(node["provenance"] for node in nodes.values())
    assert {
        "source": "task:t1",
        "target": "agent:DEV",
        "relation": "assigned_to",
        "provenance": "tasks:t1",
    } in graph["links"]
    assert "Secret prompt" not in json.dumps(graph)
    with pytest.raises(HTTPException) as error:
        KnowledgeGraph(database).snapshot("missing")
    assert error.value.status_code == 404


def test_native_graph_is_bounded_without_dangling_edges(database):
    from ai_team.knowledge_graph import KnowledgeGraph

    with database.session() as db:
        db.add(Project(id="alpha", name="Alpha"))
        db.flush()
        db.add_all(Task(id=f"task-{i}", project_id="alpha", title="Task") for i in range(12))
        db.commit()
    graph = KnowledgeGraph(database).snapshot("alpha", limit=5)
    assert len(graph["nodes"]) == 5
    assert graph["truncated"] is True
    ids = {node["id"] for node in graph["nodes"]}
    assert all(edge["source"] in ids and edge["target"] in ids for edge in graph["links"])


def test_adapter_roundtrip_and_project_boundary(tmp_path):
    from ai_team.knowledge_graph import GraphifyAdapter

    adapter = GraphifyAdapter(tmp_path)
    adapter.write("alpha", sample("alpha"))
    assert adapter.read("alpha") == sample("alpha")
    with pytest.raises(ValueError):
        adapter.write("beta", sample("alpha"))
    for name in ["../outside", "C:/vault", "nul", "alpha:stream", "\\\\server\\share"]:
        with pytest.raises(ValueError):
            adapter.read(name)


@pytest.mark.parametrize("mutation", ["duplicate", "dangling", "credentials", "path", "inferred"])
def test_adapter_rejects_untrusted_graphs(tmp_path, mutation):
    from ai_team.knowledge_graph import GraphifyAdapter

    graph = sample("alpha")
    if mutation == "duplicate":
        graph["nodes"] *= 2
    elif mutation == "dangling":
        graph["links"] = [{"source": "note:one", "target": "missing", "relation": "uses"}]
    elif mutation == "credentials":
        graph["nodes"][0]["label"] = "postgresql://owner:password@localhost/db"
    elif mutation == "path":
        graph["nodes"][0]["source_file"] = "../../.env"
    else:
        graph["links"] = [
            {
                "source": "note:one",
                "target": "note:one",
                "relation": "uses",
                "confidence": "INFERRED",
            }
        ]
    with pytest.raises(ValueError):
        GraphifyAdapter(tmp_path).write("alpha", graph)


def test_adapter_rejects_oversized_and_symlinked_files(tmp_path):
    from ai_team.knowledge_graph import MAX_GRAPH_BYTES, GraphifyAdapter

    adapter = GraphifyAdapter(tmp_path / "graphs")
    adapter.write("alpha", sample("alpha"))
    graph_path = tmp_path / "graphs" / "alpha" / "graph.json"
    graph_path.write_bytes(b" " * (MAX_GRAPH_BYTES + 1))
    with pytest.raises(ValueError):
        adapter.read("alpha")
    # Windows junctions require no developer mode or symlink privilege.
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "graphs" / "beta"
    result = (
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        if __import__("os").name == "nt"
        else None
    )
    if result and result.returncode:
        pytest.skip("Junction creation unavailable")
    if result is None:
        link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        adapter.write("beta", sample("beta"))
    assert not list(outside.iterdir())


def test_native_graph_exports_repeated_roles_without_duplicate_edges(database, tmp_path):
    from ai_team.knowledge_graph import GraphifyAdapter, KnowledgeGraph

    with database.session() as db:
        db.add(Project(id="alpha", name="Alpha"))
        db.flush()
        db.add(
            Run(
                id="r1",
                project_id="alpha",
                prompt="Request",
                mode="supervised",
                steps=[{"agent": "CEO"}, {"agent": "DEV"}, {"agent": "CEO"}],
            )
        )
        db.commit()
    graph = KnowledgeGraph(database).snapshot("alpha")
    adapter = GraphifyAdapter(tmp_path)
    adapter.export("alpha", graph)
    imported = adapter.read("alpha")
    assert len(imported["links"]) == 3
    assert {node["id"] for node in imported["nodes"]} == {
        "project:alpha",
        "run:r1",
        "agent:DEV",
        "agent:CEO",
    }


def test_graph_links_only_verified_published_repository_results(database):
    from ai_team.knowledge_graph import KnowledgeGraph

    with database.session() as db:
        db.add(Project(id="alpha", name="Alpha"))
        db.flush()
        db.add(Run(id="r1", project_id="alpha", prompt="Request", mode="supervised"))
        db.flush()
        db.add(
            RepositoryJob(
                run_id="r1",
                state={
                    "reviewed_digest": "a" * 64,
                    "delivery": {
                        "status": "published",
                        "sha": "b" * 40,
                        "branch": "codex/ai-team/task-r1",
                        "url": "https://github.com/igorcastro1010/ai-team/pull/42",
                    },
                },
            )
        )
        db.commit()
    graph = KnowledgeGraph(database).snapshot("alpha")
    assert {"commit:" + "b" * 40, "branch:codex/ai-team/task-r1", "pull_request:42"} <= {
        node["id"] for node in graph["nodes"]
    }
    with database.session() as db:
        job = db.get(RepositoryJob, "r1")
        job.state = {
            **job.state,
            "delivery": {
                **job.state["delivery"],
                "url": "https://attacker.example/pull/42",
                "sha": "invalid",
                "branch": "main",
            },
        }
        db.commit()
    assert not {"commit", "branch", "pull_request"} & {
        node["kind"] for node in KnowledgeGraph(database).snapshot("alpha")["nodes"]
    }


@pytest.mark.parametrize("mutation", ["kind_list", "non_object", "too_many_nodes"])
def test_adapter_malformed_input_is_validation_error(tmp_path, mutation):
    from ai_team.knowledge_graph import GraphifyAdapter

    graph = sample("alpha")
    if mutation == "kind_list":
        graph["nodes"][0]["kind"] = []
    elif mutation == "non_object":
        graph["nodes"] = [None]
    else:
        graph["nodes"] *= 501
    with pytest.raises(ValueError):
        GraphifyAdapter(tmp_path).write("alpha", graph)
