from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project


def test_optimizer_never_caches_secrets(tmp_path):
    import pytest
    from fastapi import HTTPException

    from ai_team.token_optimizer import OptimizerStore

    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'cache.db'}"))
    database.initialize()
    with database.session() as db:
        project = Project(name="Cache")
        db.add(project)
        db.commit()
    store = OptimizerStore(database)
    with pytest.raises(HTTPException):
        store.prepare(
            project_id=project.id,
            agent="CEO",
            task_id="preview",
            stage=0,
            instructions="safe",
            context={"request": "ghp_" + "A" * 36},
            memories=[],
            revision="1",
            permissions="read",
            budget=50000,
        )


def test_serialization_cannot_hide_credentials_in_nested_text(tmp_path):
    import pytest
    from fastapi import HTTPException

    from ai_team.token_optimizer import OptimizerStore

    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'nested.db'}"))
    database.initialize()
    with database.session() as db:
        project = Project(name="Nested context")
        db.add(project)
        db.commit()
    with pytest.raises(HTTPException):
        OptimizerStore(database).prepare(
            project_id=project.id,
            agent="CEO",
            task_id="preview",
            stage=0,
            instructions="safe",
            context={"request": '{"password":"synthetic-private-value"}'},
            memories=[],
            revision="1",
            permissions="read",
            budget=50000,
        )
