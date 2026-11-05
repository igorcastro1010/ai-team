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
