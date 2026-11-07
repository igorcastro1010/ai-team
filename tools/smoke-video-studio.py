"""Reproduce offline Studio renderer evidence using only synthetic local media.

Run: .venv/Scripts/python.exe tools/smoke-video-studio.py --output artifacts/studio.mp4
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from ai_team.video_render import executable_path, render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--format", choices=("vertical", "square", "horizontal"), default="square"
    )
    parser.add_argument("--resolution", choices=("720p", "1080p"), default="720p")
    args = parser.parse_args()
    binary = executable_path()
    if not binary:
        raise SystemExit("FFmpeg local necessário")
    with tempfile.TemporaryDirectory(prefix="ai-team-studio-smoke-") as directory:
        root = Path(directory)
        image, video, audio = root / "image.png", root / "video.mp4", root / "audio.wav"

        def generate(*command):
            subprocess.run(
                [binary, "-v", "error", "-y", *command],
                check=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
                shell=False,
            )

        generate(
            "-f", "lavfi", "-i", "testsrc=s=320x240:r=24", "-frames:v", "1", str(image)
        )
        generate(
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=320x240:r=24",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            str(video),
        )
        generate("-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(audio))
        image_id, video_id, audio_id = (str(uuid4()) for _ in range(3))
        document = {
            "title": "Prova local do Estúdio de Vídeos",
            "format": args.format,
            "resolution": args.resolution,
            "scenes": [
                {
                    "text": "AI TEAM • imagem local",
                    "duration": 2,
                    "media_id": image_id,
                    "animation": "zoom",
                    "text_animation": "slide",
                    "transition": "fade",
                },
                {
                    "text": "Vídeo local • sem inferência",
                    "duration": 2,
                    "media_id": video_id,
                    "animation": "pan",
                    "text_animation": "fade",
                    "transition": "fade",
                    "font": "serif",
                },
                {
                    "text": "Áudio explícito • render offline",
                    "duration": 2,
                    "background": "#174535",
                    "font": "mono",
                    "animation": "fade",
                },
            ],
            "audio": {
                "media_id": audio_id,
                "volume": 0.3,
                "fade_in": 0.4,
                "fade_out": 0.8,
            },
        }
        output = args.output.resolve()
        progress = []
        render(
            document,
            output,
            lambda: True,
            assets={image_id: image, video_id: video, audio_id: audio},
            progress=lambda value, phase: progress.append(
                {"value": value, "phase": phase}
            ),
        )
        probe = Path(binary).with_name(
            "ffprobe.exe" if Path(binary).suffix == ".exe" else "ffprobe"
        )
        result = subprocess.run(
            [
                str(probe),
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type,width,height:format=duration,size",
                "-of",
                "json",
                str(output),
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        evidence = {
            "test_data_only": True,
            "inference_calls": 0,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "document": document,
            "progress": progress,
            "ffprobe": json.loads(result.stdout),
        }
        output.with_suffix(".json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
