"""Separate, bounded local renderer process: python -m ai_team.video_worker --once."""

import argparse
import signal
import threading

from .video_render import RenderUnavailable, artifact_root, render
from .video_routes import VideoInput
from .video_store import VideoStore


class VideoWorker:
    def __init__(self, store, output=None, executable=None):
        self.store, self.output, self.executable = store, output or artifact_root(), executable
        self.stopped = threading.Event()

    def once(self):
        if self.stopped.is_set():
            return False
        job = self.store.claim()
        if not job:
            return False
        job_id, token = job["id"], job["lease_token"]
        output = self.output / f"{job_id}.mp4"
        try:
            # Executor revalidates bounded schema and consent, beyond approval at HTTP boundary.
            VideoInput(
                **{
                    key: job[key]
                    for key in ("project_id", "request_id", "title", "format", "scenes", "consent")
                }
            )
            render(
                job,
                output,
                lambda: not self.stopped.is_set() and self.store.active(job_id, token),
                self.executable,
            )
            if not self.store.finish(job_id, token, "completed"):
                output.unlink(missing_ok=True)
        except RenderUnavailable:
            self.store.finish(
                job_id, token, "blocked", "FFmpeg e fonte local necessários no worker"
            )
        except InterruptedError:
            output.unlink(missing_ok=True)
            self.store.finish(job_id, token, "failed", "Worker interrompido")
        except Exception:
            output.unlink(missing_ok=True)
            # Avoid surfacing process output, filesystem locations or input text.
            self.store.finish(
                job_id, token, "failed", "Falha na renderização local; revise o worker"
            )
        return True


def main():
    from .config import Settings
    from .db import Database

    parser = argparse.ArgumentParser(description="Worker local de vídeo, sem inferência")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    database = Database(Settings())
    worker = VideoWorker(VideoStore(database))
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: worker.stopped.set())
    if args.once:
        worker.once()
    else:
        while not worker.stopped.is_set():
            if not worker.once():
                worker.stopped.wait(2)


if __name__ == "__main__":
    main()
