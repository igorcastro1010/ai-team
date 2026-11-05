from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project, Run, Task


def test_run_checkpoints_index_summaries_and_prepare_issues_without_publication(tmp_path):
    from ai_team.issue_store import IssueStore
    from ai_team.knowledge_automation import index_run
    from ai_team.knowledge_automation_models import DelegatedTask
    from ai_team.memory_store import MemoryStore

    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'automation.db'}"))
    database.initialize()
    with database.session() as db:
        project = Project(name="Automation")
        db.add(project)
        db.flush()
        task = Task(project_id=project.id, title="Implementar Python", agent="DEV")
        db.add(task)
        db.flush()
        run = Run(
            project_id=project.id,
            prompt="Python",
            mode="supervised",
            steps=[
                {
                    "stage": 0,
                    "agent": "CEO",
                    "summary": "Plano Python com testes.",
                    "tasks": [{"title": task.title, "agent": "DEV", "description": ""}],
                }
            ],
        )
        db.add(run)
        db.flush()
        db.add(DelegatedTask(run_id=run.id, task_id=task.id, project_id=project.id))
        invalid = Task(project_id=project.id, title="X", agent="DEV")
        db.add(invalid)
        db.flush()
        db.add(DelegatedTask(run_id=run.id, task_id=invalid.id, project_id=project.id))
        db.commit()
        run_id, project_id = run.id, project.id
    index_run(database, run_id)
    index_run(database, run_id)
    notes = MemoryStore(database).search(project_id, "Python")
    assert len(notes) == 1 and notes[0]["version"] == 1
    issues = IssueStore(database).list(project_id)["issues"]
    assert len(issues) == 1 and issues[0]["action"]["status"] == "pending"


def test_worker_context_imports_vault_before_retrieval_without_manual_sync(tmp_path):
    from ai_team.memory_vault import Vault
    from ai_team.orchestration import Draft
    from ai_team.token_optimizer import OptimizedProvider

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'automatic.db'}", memory_vault=str(tmp_path / "vault")
    )
    database = Database(settings)
    database.initialize()
    with database.session() as db:
        project = Project(name="Automatic import")
        db.add(project)
        db.flush()
        run = Run(project_id=project.id, prompt="PostgreSQL", mode="supervised")
        db.add(run)
        db.commit()
    Vault(settings.memory_vault).write(project.id, "database.md", "PostgreSQL usa schema privado.")

    class Provider:
        def generate(self, role, instructions, context, on_tick):
            assert instructions == "Preservar limites"
            assert context["request"] == "PostgreSQL"
            assert (
                context["untrusted_project_memory"]["notes"][0]["source"] == "obsidian:database.md"
            )
            return Draft(
                summary="Revisado",
                deliverable="Proposta",
                tasks=[],
                input_tokens=10,
                output_tokens=5,
            )

    OptimizedProvider(Provider(), database, run).generate(
        "QA", "Preservar limites", {"request": "PostgreSQL"}, lambda: None
    )
