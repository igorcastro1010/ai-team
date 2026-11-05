"""Fixed Next.js runtime reuses the reviewed Docker process controller."""

import json
import re

from .config import ROOT
from .next_artifacts import NextProject, runtime_fingerprint
from .python_sandbox import PythonSandbox

MANIFEST = ROOT / ".data" / "next-sandbox" / "image.json"


def prepared_image():
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        image = manifest["image_id"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            raise ValueError("image")
        if manifest["runtime_hash"] != runtime_fingerprint():
            raise ValueError("runtime")
        return image
    except (OSError, ValueError, KeyError, TypeError):
        raise RuntimeError("Prepare a imagem Next.js revisada antes de executar") from None


def next_command(name, image):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("ID imutável obrigatório")
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--label",
        "ai-team.scope=next-test",
        "--pull",
        "never",
        "--network",
        "none",
        "--user",
        "65532:65532",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--read-only",
        "--cpus",
        "2",
        "--memory",
        "1g",
        "--memory-swap",
        "1g",
        "--pids-limit",
        "128",
        "--ulimit",
        "nofile=512:512",
        "--init",
        "--log-driver",
        "none",
        "--tmpfs",
        "/work:rw,noexec,nosuid,size=256m,mode=1777",
        "--workdir",
        "/work",
        "-i",
        image,
        "timeout",
        "--signal=KILL",
        "120s",
        "node",
        "/opt/runner/run.mjs",
    ]


class NextSandbox(PythonSandbox):
    max_time = 120

    def __init__(self, time_limit=120):
        super().__init__(time_limit)

    def command(self, name):
        self.image = prepared_image()
        return next_command(name, self.image)

    def validate_bundle(self, bundle):
        return NextProject.model_validate(bundle.model_dump())
