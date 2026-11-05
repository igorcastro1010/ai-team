"""Bounded SQL relationships and optional, strictly local Graphify interchange.

Graph JSON is untrusted data. It never controls a path, SQL scope, command or approval.
The adapter intentionally supports a safe subset of Graphify's node-link format.
"""

import json
import os
import re
import stat
import tempfile
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from .models import Event, GitHubAction, Project, RepositoryJob, Run, Task

MAX_NODES = 500
MAX_LINKS = 2000
MAX_GRAPH_BYTES = 512 * 1024
ROLES = frozenset({"CEO", "PESQUISADOR", "DEV", "DESIGNER", "QA"})
KINDS = frozenset(
    {
        "project",
        "task",
        "run",
        "agent",
        "memory",
        "decision",
        "issue",
        "branch",
        "commit",
        "pull_request",
        "github_action",
        "symbol",
        "file",
    }
)
SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|(?:postgres(?:ql)?|mysql|https?)://[^\s/@]+:[^\s/@]+@|"
    r"(?:sk-[A-Za-z0-9_-]{16,})|(?:api[_-]?key|password|secret|token)\s*[:=]\s*\S+",
    re.I,
)


def project_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError("Identificador de projeto inválido")
    if value.lower() in {"con", "prn", "aux", "nul"} or re.fullmatch(
        r"(?:com|lpt)[0-9]", value.lower()
    ):
        raise ValueError("Identificador de projeto reservado")
    return value


def _label(value):
    value = str(value)
    return "[conteúdo protegido]" if SECRET.search(value) else value[:200]


class KnowledgeGraph:
    def __init__(self, database):
        self.database = database

    def snapshot(self, project_id, *, limit=MAX_NODES):
        try:
            project_key(project_id)
        except ValueError:
            raise HTTPException(422, "Identificador de projeto inválido") from None
        if type(limit) is not int or not 1 <= limit <= MAX_NODES:
            raise HTTPException(422, "Limite de grafo inválido")
        nodes, links, seen, pairs = [], [], set(), set()
        truncated = False

        def node(key, kind, label, provenance):
            nonlocal truncated
            if key not in seen:
                if len(nodes) >= limit:
                    truncated = True
                    return False
                nodes.append(
                    {"id": key, "kind": kind, "label": _label(label), "provenance": provenance}
                )
                seen.add(key)
            return True

        def edge(source, target, relation, provenance):
            nonlocal truncated
            pair = (source, target)
            if source in seen and target in seen and pair not in pairs:
                if len(links) >= MAX_LINKS:
                    truncated = True
                else:
                    links.append(
                        {
                            "source": source,
                            "target": target,
                            "relation": relation,
                            "provenance": provenance,
                        }
                    )
                    pairs.add(pair)

        def rows(db, model):
            nonlocal truncated
            result = list(
                db.scalars(
                    select(model)
                    .where(model.project_id == project_id)
                    .order_by(model.id)
                    .limit(limit + 1)
                )
            )
            if len(result) > limit:
                truncated = True
            return result[:limit]

        project_ref = f"project:{project_id}"
        with self.database.session() as db:
            project = db.get(Project, project_id)
            if project is None:
                raise HTTPException(404, "Projeto não encontrado")
            node(project_ref, "project", project.name, f"projects:{project_id}")
            for task in rows(db, Task):
                ref, provenance = f"task:{task.id}", f"tasks:{task.id}"
                node(ref, "task", task.title, provenance)
                edge(project_ref, ref, "contains", provenance)
                if task.agent in ROLES:
                    agent_ref = f"agent:{task.agent}"
                    node(agent_ref, "agent", task.agent, provenance)
                    edge(ref, agent_ref, "assigned_to", provenance)
            runs = rows(db, Run)
            deliveries = (
                dict(
                    db.execute(
                        select(RepositoryJob.run_id, RepositoryJob.state).where(
                            RepositoryJob.run_id.in_([run.id for run in runs])
                        )
                    ).all()
                )
                if runs
                else {}
            )
            for run in runs:
                ref, provenance = f"run:{run.id}", f"runs:{run.id}"
                node(ref, "run", f"Execução {run.status}", provenance)
                edge(project_ref, ref, "contains", provenance)
                for step in (run.steps or [])[:20]:
                    role = step.get("agent") if isinstance(step, dict) else None
                    if role in ROLES:
                        agent_ref = f"agent:{role}"
                        node(agent_ref, "agent", role, provenance)
                        edge(ref, agent_ref, "performed_by", provenance)
                state = deliveries.get(run.id, {})
                delivery = state.get("delivery", {})
                if (
                    isinstance(delivery, dict)
                    and delivery.get("status") == "published"
                    and re.fullmatch("[a-f0-9]{64}", str(state.get("reviewed_digest")))
                ):
                    provenance = f"repository_jobs:{run.id}"
                    sha, branch = delivery.get("sha"), delivery.get("branch")
                    if isinstance(sha, str) and re.fullmatch("[a-f0-9]{40}", sha):
                        key = f"commit:{sha}"
                        node(key, "commit", sha[:12], provenance)
                        edge(ref, key, "published", provenance)
                    if isinstance(branch, str) and re.fullmatch(
                        r"codex/ai-team/[a-z0-9][a-z0-9-]{0,60}", branch
                    ):
                        key = f"branch:{branch}"
                        node(key, "branch", branch, provenance)
                        edge(ref, key, "targets", provenance)
                    match = re.fullmatch(
                        r"https://github.com/igorcastro1010/ai-team/pull/([1-9][0-9]{0,9})",
                        str(delivery.get("url")),
                    )
                    if match:
                        number = match.group(1)
                        key = f"pull_request:{number}"
                        node(key, "pull_request", f"#{number}", provenance)
                        edge(ref, key, "published", provenance)
            if runs:
                decisions = list(
                    db.scalars(
                        select(Event)
                        .where(
                            Event.resource_id.in_([run.id for run in runs]),
                            Event.kind == "repository.decision",
                        )
                        .order_by(Event.sequence)
                        .limit(limit + 1)
                    )
                )
                truncated |= len(decisions) > limit
                for decision in decisions[:limit]:
                    ref, provenance = f"decision:{decision.id}", f"events:{decision.id}"
                    node(ref, "decision", "Decisão registrada pelo proprietário", provenance)
                    edge(f"run:{decision.resource_id}", ref, "reviewed_by", provenance)
            # Imported lazily to avoid circular registration with the models aggregate.
            try:
                from .memory_models import MemoryEntry
            except ImportError:
                MemoryEntry = None
            if MemoryEntry is not None:
                for memory in rows(db, MemoryEntry):
                    if memory.archived or memory.quarantined:
                        continue
                    ref, provenance = f"memory:{memory.id}", f"memory_entries:{memory.id}"
                    node(ref, "memory", memory.title, provenance)
                    edge(project_ref, ref, "documents", provenance)
            for action in rows(db, GitHubAction):
                ref, provenance = f"github_action:{action.id}", f"github_actions:{action.id}"
                node(ref, "github_action", f"GitHub {action.status}", provenance)
                edge(project_ref, ref, "contains", provenance)
                if action.status != "succeeded":
                    continue
                payload, result = action.payload or {}, action.result or {}
                operation = payload.get("operation")
                if operation == "commit" and re.fullmatch("[a-f0-9]{40}", str(result.get("sha"))):
                    key = f"commit:{result['sha']}"
                    node(key, "commit", result["sha"][:12], provenance)
                    edge(ref, key, "created", provenance)
                elif operation in {"issue", "pull_request"}:
                    number = result.get("number")
                    if type(number) is int and 0 < number < 2**31:
                        key = f"{operation}:{number}"
                        node(key, operation, f"#{number}", provenance)
                        edge(ref, key, "created", provenance)
                branch = payload.get("branch", "")
                if operation in {"branch", "commit", "pull_request"} and re.fullmatch(
                    r"codex/ai-team/[a-z0-9][a-z0-9-]{0,60}", branch
                ):
                    key = f"branch:{branch}"
                    node(key, "branch", branch, provenance)
                    edge(ref, key, "targets", provenance)
        return {
            "project_id": project_id,
            "nodes": nodes,
            "links": links,
            "truncated": truncated,
            "source": "native",
        }


def validate_graph(project_id, graph):
    project_key(project_id)
    if not isinstance(graph, dict) or set(graph) != {
        "directed",
        "multigraph",
        "graph",
        "nodes",
        "links",
    }:
        raise ValueError("Formato node-link não suportado")
    if graph["directed"] is not True or graph["multigraph"] is not False:
        raise ValueError("Grafo deve ser direcionado e simples")
    if graph["graph"] != {"project_id": project_id, "schema_version": 1}:
        raise ValueError("Grafo pertence a outro projeto ou versão")
    nodes, links = graph["nodes"], graph["links"]
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise ValueError("Limite de nós excedido")
    if not isinstance(links, list) or len(links) > MAX_LINKS:
        raise ValueError("Limite de relações excedido")
    ids = set()
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"id", "label", "kind", "provenance"}:
            raise ValueError("Atributos de nó não suportados")
        if not isinstance(node["kind"], str) or node["kind"] not in KINDS:
            raise ValueError("Tipo de nó inválido")
        for key, value in node.items():
            if not isinstance(value, str) or not 1 <= len(value) <= 200:
                raise ValueError("Atributo de nó inválido")
            if SECRET.search(value) or any(ord(char) < 32 for char in value):
                raise ValueError("Credenciais ou controle em grafo")
            if key != "label" and not re.fullmatch(r"[A-Za-z0-9_:/.-]+", value):
                raise ValueError("Identificador de nó inválido")
        if node["id"] in ids:
            raise ValueError("Nós duplicados")
        ids.add(node["id"])
    seen = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != {
            "source",
            "target",
            "relation",
            "provenance",
        }:
            raise ValueError("Atributos de relação não suportados")
        if any(
            not isinstance(value, str)
            or not re.fullmatch(r"[A-Za-z0-9_:/.-]{1,200}", value)
            or SECRET.search(value)
            for value in link.values()
        ):
            raise ValueError("Atributo de relação inválido")
        if link["source"] not in ids or link["target"] not in ids:
            raise ValueError("Relação sem nó correspondente")
        pair = (link["source"], link["target"])
        if pair in seen:
            raise ValueError("Relações duplicadas")
        seen.add(pair)
    if len(json.dumps(graph, ensure_ascii=False).encode()) > MAX_GRAPH_BYTES:
        raise ValueError("Grafo excede limite de bytes")
    return graph


class GraphifyAdapter:
    """Server/operator configured root; clients cannot submit arbitrary filesystem paths."""

    def __init__(self, root):
        self.root = Path(root).absolute()

    def _path(self, project_id, *, create=False):
        project_key(project_id)
        parent = self.root / project_id
        path = parent / "graph.json"
        # Check every ancestor before creating anything, including Windows reparse points.
        for item in [*path.parents, path]:
            if item.exists() or item.is_symlink():
                info = item.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise ValueError("Links ou junctions proibidos no caminho do grafo")
        if create:
            parent.mkdir(parents=True, exist_ok=True)
        if parent.resolve() != self.root.resolve() / project_id:
            raise ValueError("Caminho fora da raiz do grafo")
        return path

    def read(self, project_id):
        path = self._path(project_id)
        with path.open("rb") as file:
            payload = file.read(MAX_GRAPH_BYTES + 1)
        if len(payload) > MAX_GRAPH_BYTES:
            raise ValueError("Grafo excede limite de bytes")
        try:
            graph = json.loads(payload)
        except (ValueError, RecursionError):
            raise ValueError("JSON de grafo inválido") from None
        return validate_graph(project_id, graph)

    def write(self, project_id, graph):
        validated = validate_graph(project_id, graph)
        path = self._path(project_id, create=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
            ) as file:
                temporary = Path(file.name)
                json.dump(validated, file, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            self._path(project_id)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    def export(self, project_id, snapshot):
        if snapshot.get("project_id") != project_id:
            raise ValueError("Snapshot pertence a outro projeto")
        return self.write(
            project_id,
            {
                "directed": True,
                "multigraph": False,
                "graph": {"project_id": project_id, "schema_version": 1},
                "nodes": snapshot["nodes"],
                "links": snapshot["links"],
            },
        )
