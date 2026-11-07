"""Offline FFmpeg renderer. Text is data in UTF-8 files, never shell/filter code."""

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

from .config import ROOT


class RenderUnavailable(RuntimeError):
    pass


def artifact_root():
    # Server-controlled only; no request field selects paths or binaries.
    return Path(os.environ.get("AI_TEAM_VIDEO_ROOT", str(ROOT / ".data" / "videos")))


def executable_path(executable=None):
    candidate = executable or os.environ.get("AI_TEAM_FFMPEG", "ffmpeg")
    found = shutil.which(candidate)
    if found or executable or "AI_TEAM_FFMPEG" in os.environ:
        return found
    # Known user-scoped distributor only; never scan repositories or download binaries.
    local = os.environ.get("LOCALAPPDATA")
    if local:
        package = (
            Path(local)
            / "Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        )
        for binary in sorted(package.glob("ffmpeg-*-full_build/bin/ffmpeg.exe"), reverse=True):
            if binary.is_file() and not binary.is_symlink():
                return str(binary)
    return None


def font_path():
    for path in (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.is_file():
            return path
    return None


def renderer_status(executable=None):
    available = bool(executable_path(executable) and font_path())
    return {
        "available": available,
        "engine": "ffmpeg",
        "network": False,
        "reason": "" if available else "FFmpeg e fonte local necessários no worker",
        "max_seconds": 60,
        "fps": 24,
    }


def render(job, output, active, executable=None):
    binary, font = executable_path(executable), font_path()
    if not binary or not font:
        raise RenderUnavailable("FFmpeg e fonte local necessários no worker")
    width, height = (720, 1280) if job["format"] == "vertical" else (1280, 720)
    deadline = time.monotonic() + 180

    def execute(args, cwd):
        # A deliberately tiny environment avoids passing server credentials into FFmpeg.
        env = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        }
        with subprocess.Popen(
            [binary, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        ) as process:
            try:
                while process.poll() is None:
                    if not active():
                        raise InterruptedError("Renderização cancelada")
                    if time.monotonic() > deadline:
                        raise TimeoutError("Tempo de renderização excedido")
                    time.sleep(0.15)
                if process.returncode:
                    raise RuntimeError("FFmpeg não conseguiu renderizar o roteiro")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai-team-video-", dir=output.parent) as directory:
        temp = Path(directory)
        shutil.copyfile(font, temp / "font.ttf")
        for index, scene in enumerate(job["scenes"]):
            text = temp / f"caption{index}.txt"
            lines = []
            for paragraph in scene["text"].splitlines():
                lines.extend(textwrap.wrap(paragraph, width=27 if width == 720 else 48))
            text.write_text("\n".join(lines), encoding="utf-8", newline="\n")
            caption = (
                "drawtext=fontfile=font.ttf:"
                f"textfile=caption{index}.txt:expansion=none:fontsize=36:"
                "fontcolor=white:line_spacing=14:x=(w-text_w)/2:y=(h-text_h)/2"
            )
            execute(
                [
                    "-protocol_whitelist",
                    "file,pipe",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=0x13233c:s={width}x{height}:r=24:d={scene['duration']}",
                    "-vf",
                    caption,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-threads",
                    "2",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    f"scene{index}.mp4",
                ],
                temp,
            )
        listing = temp / "concat.txt"
        listing.write_text(
            "\n".join(f"file 'scene{i}.mp4'" for i in range(len(job["scenes"]))), encoding="ascii"
        )
        intermediate = temp / "result.mp4"
        execute(
            [
                "-protocol_whitelist",
                "file",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                "concat.txt",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                "result.mp4",
            ],
            temp,
        )
        if not active():
            raise InterruptedError("Renderização cancelada")
        if not intermediate.is_file() or intermediate.stat().st_size < 100:
            raise RuntimeError("Artefato MP4 inválido")
        intermediate.replace(output)
