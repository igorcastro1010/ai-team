"""Offline FFmpeg renderer. Text is data in UTF-8 files, never shell/filter code."""

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

from .config import ROOT
from .video_schema import StudioDocument


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


def font_path(font="sans"):
    families = {
        "sans": ("arial.ttf", "DejaVuSans.ttf"),
        "serif": ("georgia.ttf", "DejaVuSerif.ttf"),
        "mono": ("consola.ttf", "DejaVuSansMono.ttf"),
    }
    if font not in families:
        raise ValueError("Fonte inválida")
    windows, linux = families[font]
    for path in (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / windows,
        Path("/usr/share/fonts/truetype/dejavu") / linux,
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


def render(job, output, active, executable=None, *, assets=None, progress=None):
    """Render a validated document, with legacy V0.8 defaults.

    assets are server-verified immutable local files, never request-selected paths.
    Progress reports observed FFmpeg output timestamps and completed phases.
    """
    document = StudioDocument.model_validate(
        {
            key: job[key]
            for key in ("title", "format", "resolution", "scenes", "audio")
            if key in job
        }
        | {"title": job.get("title", "Vídeo")}
    ).model_dump(mode="json")
    binary = executable_path(executable)
    if not binary or not font_path():
        raise RenderUnavailable("FFmpeg e fonte local necessários no worker")
    width, height = {"vertical": (720, 1280), "square": (720, 720), "horizontal": (1280, 720)}[
        document["format"]
    ]
    if document["resolution"] == "1080p":
        width, height = width * 3 // 2, height * 3 // 2
    deadline = time.monotonic() + (600 if document["resolution"] == "1080p" else 300)
    output = Path(output)
    assets = {str(key): Path(value) for key, value in (assets or {}).items()}
    references = {scene["media_id"] for scene in document["scenes"] if scene["media_id"]}
    if document["audio"]:
        references.add(document["audio"]["media_id"])
    for reference in references:
        source = assets.get(reference)
        if source is None or source.is_symlink() or not source.is_file():
            raise ValueError("Mídia local verificada necessária")
    if not active():
        raise InterruptedError("Renderização cancelada")
    total = sum(scene["duration"] for scene in document["scenes"])
    reported = -1

    def report(value, phase):
        nonlocal reported
        value = min(100, max(reported, int(value)))
        if progress and value > reported:
            progress(value, phase)
        reported = value

    def execute(args, cwd, base, span, seconds, phase):
        env = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        }
        status = cwd / "progress.txt"
        status.unlink(missing_ok=True)
        with subprocess.Popen(
            [
                binary,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-filter_threads",
                "2",
                "-filter_complex_threads",
                "2",
                "-progress",
                "progress.txt",
                *args,
            ],
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
                    if any(path.stat().st_size > 100 * 1024 * 1024 for path in cwd.glob("*.mp4")):
                        raise RuntimeError("Artefato excede limite de 100MB")
                    if status.exists():
                        try:
                            timestamps = [
                                int(line.split("=", 1)[1])
                                for line in status.read_text().splitlines()
                                if line.startswith("out_time_us=")
                            ]
                            if timestamps:
                                report(
                                    base + span * min(timestamps[-1] / 1e6 / seconds, 0.99), phase
                                )
                        except (OSError, ValueError):
                            pass  # FFmpeg may be in the middle of writing a progress record.
                    time.sleep(0.1)
                if process.returncode:
                    raise RuntimeError("FFmpeg não conseguiu renderizar o roteiro")
                report(base + span, phase)
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
        staged = {}
        for index, reference in enumerate(sorted(references)):
            destination = temp / f"asset{index}.media"
            shutil.copyfile(assets[reference], destination)
            with destination.open("rb") as source:
                header = source.read(16)
            image = header.startswith((b"\x89PNG", b"\xff\xd8")) or (
                header.startswith(b"RIFF") and header[8:12] == b"WEBP"
            )
            staged[reference] = (destination.name, image)
        for family in {scene["font"] for scene in document["scenes"]}:
            font = font_path(family)
            if not font:
                raise RenderUnavailable("Fonte local necessária no worker")
            shutil.copyfile(font, temp / f"font-{family}.ttf")
        report(0, "preparando")
        elapsed = 0
        for index, scene in enumerate(document["scenes"]):
            duration = scene["duration"]
            text = temp / f"caption{index}.txt"
            lines = []
            for paragraph in scene["text"].splitlines():
                lines.extend(textwrap.wrap(paragraph, width=27 if width <= 1080 else 48))
            text.write_text("\n".join(lines), encoding="utf-8", newline="\n")
            inputs = ["-protocol_whitelist", "file,pipe"]
            filters = []
            if scene["media_id"]:
                filename, image = staged[scene["media_id"]]
                inputs += ["-loop", "1", "-framerate", "24"] if image else ["-stream_loop", "-1"]
                inputs += ["-threads", "2", "-i", filename]
                filters += [
                    f"scale={width}:{height}:force_original_aspect_ratio=increase",
                    f"crop={width}:{height}",
                    "setsar=1",
                    "fps=24",
                ]
            else:
                inputs += [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=0x{scene['background'][1:]}:s={width}x{height}:r=24",
                ]
            frames = duration * 24 - 1
            if scene["animation"] in ("zoom", "pan"):
                zoom = f"1+0.08*on/{frames}" if scene["animation"] == "zoom" else "1.08"
                x = (
                    "iw/2-iw/zoom/2"
                    if scene["animation"] == "zoom"
                    else (f"(iw-iw/zoom)*on/{frames}")
                )
                filters += [
                    f"zoompan=z='{zoom}':x='{x}':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=24"
                ]
            ramp = min(0.4, duration / 2)
            if scene["animation"] == "fade":
                filters += [f"fade=t=in:d={ramp}", f"fade=t=out:st={duration - ramp}:d={ramp}"]
            x = f"(w-text_w)*{scene['x']}/100"
            y = f"(h-text_h)*{scene['y']}/100"
            if scene["text_animation"] == "slide":
                y += (
                    f"+{16 * width / 720}*(1-min(t/{ramp},1)-max(0,(t-({duration}-{ramp}))/{ramp}))"
                )
            caption = (
                f"drawtext=fontfile=font-{scene['font']}.ttf:"
                f"textfile=caption{index}.txt:expansion=none:"
                f"fontsize={scene['font_size'] * width / 720}:"
                f"fontcolor=0x{scene['color'][1:]}:line_spacing={14 * width / 720}:"
                f"x='{x}':y='{y}'"
            )
            if scene["text_animation"] in ("fade", "slide"):
                caption += f":alpha='min(min(t/{ramp},({duration}-t)/{ramp}),1)'"
            filters += [caption]
            if scene["transition"] == "fade":
                filters += [f"fade=t=in:d={ramp}", f"fade=t=out:st={duration - ramp}:d={ramp}"]
            execute(
                inputs
                + [
                    "-vf",
                    ",".join(filters),
                    "-t",
                    str(duration),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-threads",
                    "2",
                    "-pix_fmt",
                    "yuv420p",
                    f"scene{index}.mp4",
                ],
                temp,
                85 * elapsed / total,
                85 * duration / total,
                duration,
                "cenas",
            )
            elapsed += duration
        (temp / "concat.txt").write_text(
            "\n".join(f"file 'scene{i}.mp4'" for i in range(len(document["scenes"]))),
            encoding="ascii",
        )
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
                "joined.mp4",
            ],
            temp,
            85,
            5 if document["audio"] else 14,
            total,
            "montagem",
        )
        intermediate = temp / "joined.mp4"
        if document["audio"]:
            audio = document["audio"]
            fade_in, fade_out = min(audio["fade_in"], total), min(audio["fade_out"], total)
            audio_filters = [f"volume={audio['volume']}", "apad", f"atrim=duration={total}"]
            if fade_in:
                audio_filters.append(f"afade=t=in:d={fade_in}")
            if fade_out:
                audio_filters.append(f"afade=t=out:st={total - fade_out}:d={fade_out}")
            execute(
                [
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    "joined.mp4",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-threads",
                    "2",
                    "-i",
                    staged[audio["media_id"]][0],
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-af",
                    ",".join(audio_filters),
                    "-c:a",
                    "aac",
                    "-threads",
                    "2",
                    "-t",
                    str(total),
                    "-movflags",
                    "+faststart",
                    "result.mp4",
                ],
                temp,
                90,
                9,
                total,
                "áudio",
            )
            intermediate = temp / "result.mp4"
        if not active():
            raise InterruptedError("Renderização cancelada")
        size = intermediate.stat().st_size if intermediate.is_file() else 0
        if not 100 <= size <= 100 * 1024 * 1024:
            raise RuntimeError("Artefato MP4 inválido ou excede 100MB")
        intermediate.replace(output)
        report(100, "concluído")
