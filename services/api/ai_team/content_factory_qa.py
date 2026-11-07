"""Bounded inspection of local renderer outputs; no model or arbitrary commands."""

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

from .video_render import executable_path


def inspect_mp4(path, document):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 300 * 1024 * 1024:
        raise ValueError("Arquivo inválido")
    ffmpeg = executable_path()
    binary = shutil.which("ffprobe") or (
        str(Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe"))
        if ffmpeg
        else None
    )
    if not binary:
        raise ValueError("FFprobe indisponível")
    result = subprocess.run(
        [
            binary,
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        timeout=15,
        check=True,
        env={k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if k in os.environ},
    )
    if len(result.stdout) > 100000:
        raise ValueError("Metadados fora dos limites")
    data = json.loads(result.stdout)
    video = [s for s in data["streams"] if s["codec_type"] == "video"]
    w, h = {"vertical": (720, 1280), "square": (720, 720), "horizontal": (1280, 720)}[
        document["format"]
    ]
    if document["resolution"] == "1080p":
        w, h = w * 3 // 2, h * 3 // 2
    seconds = float(data["format"]["duration"])
    if (
        not math.isfinite(seconds)
        or len(video) != 1
        or video[0]["codec_name"] != "h264"
        or (video[0]["width"], video[0]["height"]) != (w, h)
        or abs(seconds - sum(s["duration"] for s in document["scenes"])) > 0.5
    ):
        raise ValueError("Formato, codec ou duração divergente")
    return f"{w}×{h}, {seconds:.2f}s"
