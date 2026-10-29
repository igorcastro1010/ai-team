import os
import subprocess
import sys
import time

from test_schedules import database as database
from test_schedules import payload


def test_scheduler_process_enqueues_once_without_inference(database):
    from ai_team.schedules import ScheduleStore

    now = int(time.time())
    store = ScheduleStore(database)
    schedule = store.create(payload(starts_at=now - 1), "owner", now=now - 10)
    environment = {
        **os.environ,
        "AI_TEAM_DATABASE_URL": str(database.engine.url),
        "AI_TEAM_ENVIRONMENT": "test",
    }
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "ai_team.scheduler", "--once"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
    assert store.get(schedule.id).emitted == 1
    from ai_team.workflow import WorkflowStore

    runs = WorkflowStore(database).all()
    assert len(runs) == 1 and runs[0].calls == 0
