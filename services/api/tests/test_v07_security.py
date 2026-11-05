from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project


def test_concurrent_memory_content_dedup(tmp_path):
    from ai_team.memory_store import MemoryStore

    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'concurrent.db'}"))
    database.initialize()
    with database.session() as db:
        db.add(Project(id="p", name="Concurrency"))
        db.commit()
    barrier = Barrier(6)

    def put(_):
        barrier.wait(timeout=10)
        return MemoryStore(database).put("p", "Plano", "Usar Python privado.", "owner", "test")

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(put, range(6)))
    assert len({result["id"] for result in results}) == 1


@pytest.mark.parametrize("prefix", ["vcp_", "sk-", "Bearer "])
def test_all_remote_issue_proposals_reject_credentials(prefix):
    from ai_team.github_actions import Proposal

    with pytest.raises(ValueError):
        Proposal(
            project_id="p", operation="issue", title="Revisar credenciais", body=prefix + "A" * 36
        )
