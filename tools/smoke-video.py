"""Local developer smoke: disposable DB, exact approval, real worker and ffprobe.

Run with the project virtualenv; no provider calls or application credentials.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project
from ai_team.video_render import executable_path
from ai_team.video_routes import VideoInput
from ai_team.video_store import VideoStore
from ai_team.video_worker import VideoWorker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = executable_path()
    probe = shutil.which("ffprobe") or (
        str(Path(binary).with_name("ffprobe.exe")) if binary else None
    )
    if not binary or not probe or not Path(probe).is_file():
        raise SystemExit("FFmpeg e ffprobe locais são necessários")
    with tempfile.TemporaryDirectory(prefix="ai-team-video-smoke-") as directory:
        root = Path(directory)
        database = Database(
            Settings(
                _env_file=None,
                environment="test",
                database_url=f"sqlite:///{(root / 'test.db').as_posix()}",
            )
        )
        database.initialize()
        try:
            with database.session() as db:
                project = Project(name="Vídeo local descartável")
                db.add(project)
                db.commit()
            data = VideoInput(
                project_id=project.id,
                request_id=uuid.uuid4(),
                title="Cenas e legendas AI TEAM",
                scenes=[
                    {
                        "text": "AI TEAM: transforme seu roteiro em cenas e legendas.",
                        "duration": 2,
                    },
                    {
                        "text": "Revise, aprove e baixe seu vídeo. Tudo renderizado localmente.",
                        "duration": 2,
                    },
                ],
                consent=True,
            )
            store = VideoStore(database)
            job = store.create(data, "local-smoke")
            assert job["status"] == "pending_approval"
            assert (
                store.decide(job["id"], job["digest"], True, "local-smoke")["status"]
                == "queued"
            )
            assert VideoWorker(store, output=root, executable=binary).once()
            assert store.get(job["id"])["status"] == "completed"
            output = args.output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / f"{job['id']}.mp4", output)
            result = subprocess.run(
                [
                    probe,
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=codec_name,width,height,r_frame_rate:format=duration,size",
                    "-of",
                    "json",
                    str(output),
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
            evidence = {
                "inference_calls": 0,
                "test_data_only": True,
                "approval_digest": job["digest"],
                "status": "completed",
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "ffprobe": json.loads(result.stdout),
            }
            output.with_suffix(".json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(json.dumps(evidence, ensure_ascii=False))
        finally:
            database.engine.dispose()


if __name__ == "__main__":
    main()
