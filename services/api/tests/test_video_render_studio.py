"""Real offline renderer checks: dimensions, media, fades, audio and cancellation."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from ai_team.video_render import executable_path, font_path, render, renderer_status

pytestmark = pytest.mark.skipif(
    not renderer_status()["available"], reason="local FFmpeg/font required"
)


def ffmpeg(*args):
    subprocess.run(
        [executable_path(), "-hide_banner", "-loglevel", "error", "-y", *args],
        check=True,
        timeout=30,
    )


def probe(path):
    binary = Path(executable_path()).with_name(
        "ffprobe.exe" if Path(executable_path()).suffix == ".exe" else "ffprobe"
    )
    result = subprocess.run(
        [str(binary), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        timeout=15,
    )
    return json.loads(result.stdout)


@pytest.fixture
def media(tmp_path):
    image, video, audio = tmp_path / "image.png", tmp_path / "clip.mp4", tmp_path / "audio.wav"
    ffmpeg("-f", "lavfi", "-i", "testsrc=s=320x240:r=24", "-frames:v", "1", str(image))
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=s=320x240:r=24",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880",
        "-t",
        "1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(video),
    )
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(audio))
    return {str(uuid4()): image, str(uuid4()): video, str(uuid4()): audio}


@pytest.mark.parametrize(
    "aspect,size", [("vertical", (720, 1280)), ("square", (720, 720)), ("horizontal", (1280, 720))]
)
def test_media_scene_dimensions_and_only_explicit_audio(tmp_path, media, aspect, size):
    ids = list(media)
    output = tmp_path / "result.mp4"
    progress = []
    render(
        {
            "format": aspect,
            "scenes": [{"text": "Olá 100% %{n}: [x]", "duration": 1, "media_id": ids[1]}],
        },
        output,
        lambda: True,
        assets=media,
        progress=lambda n, p: progress.append((n, p)),
    )
    data = probe(output)
    assert (data["streams"][0]["width"], data["streams"][0]["height"]) == size
    assert not [s for s in data["streams"] if s["codec_type"] == "audio"]
    assert 0.95 <= float(data["format"]["duration"]) <= 1.1
    assert progress[-1][0] == 100
    assert [n for n, _ in progress] == sorted(n for n, _ in progress)


def test_image_animation_text_transition_and_padded_audio(tmp_path, media):
    image, _, audio = list(media)
    scenes = [
        {
            "text": "Texto á ç %{n}",
            "duration": 1,
            "media_id": image,
            "animation": animation,
            "text_animation": text,
            "transition": "fade",
            "font": font,
            "x": 0,
            "y": 100,
        }
        for animation, text, font in [
            ("fade", "fade", "sans"),
            ("zoom", "slide", "serif"),
            ("pan", "none", "mono"),
        ]
    ]
    output = tmp_path / "mixed.mp4"
    render(
        {
            "format": "square",
            "scenes": scenes,
            "audio": {"media_id": audio, "volume": 0.2, "fade_in": 0.4, "fade_out": 0.4},
        },
        output,
        lambda: True,
        assets=media,
    )
    data = probe(output)
    assert {s["codec_type"] for s in data["streams"]} == {"video", "audio"}
    assert 2.95 <= float(data["format"]["duration"]) <= 3.15

    # Fade through black at the beginning; an interior frame retains image detail.
    def frame(t):
        result = subprocess.run(
            [
                executable_path(),
                "-v",
                "error",
                "-ss",
                str(t),
                "-i",
                str(output),
                "-frames:v",
                "1",
                "-vf",
                "scale=1:1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        return sum(result.stdout)

    assert frame(0) < 15
    assert frame(0.5) > 60
    assert all(font_path(f).is_file() for f in ("sans", "serif", "mono"))


def test_missing_assets_fail_closed_and_cancel_does_not_publish(tmp_path, media):
    job = {"format": "square", "scenes": [{"text": "", "duration": 1, "media_id": str(uuid4())}]}
    output = tmp_path / "result.mp4"
    with pytest.raises(ValueError):
        render(job, output, lambda: True, assets=media)
    assert not output.exists()
    with pytest.raises(InterruptedError):
        render(
            {"format": "square", "scenes": [{"text": "", "duration": 1}]},
            output,
            lambda: False,
            assets={},
        )
    assert not output.exists()


def test_1080_square_and_cancellation_after_real_progress(tmp_path):
    output = tmp_path / "hd.mp4"
    render(
        {"format": "square", "resolution": "1080p", "scenes": [{"text": "1080", "duration": 1}]},
        output,
        lambda: True,
    )
    stream = probe(output)["streams"][0]
    assert (stream["width"], stream["height"]) == (1080, 1080)
    output.unlink()
    running = [True]

    def progress(value, phase):
        if value > 0:
            running[0] = False

    with pytest.raises(InterruptedError):
        render(
            {
                "format": "square",
                "scenes": [{"text": "cancel", "duration": 3}, {"text": "second", "duration": 1}],
            },
            output,
            lambda: running[0],
            progress=progress,
        )
    assert not output.exists()
    assert not list(tmp_path.iterdir())


def test_text_slide_moves_vertically_on_entrance_and_exit(tmp_path):
    output = tmp_path / "slide.mp4"
    render(
        {
            "format": "square",
            "scenes": [
                {
                    "text": "TEST",
                    "duration": 2,
                    "text_animation": "slide",
                    "background": "#000000",
                    "font_size": 60,
                }
            ],
        },
        output,
        lambda: True,
    )

    def bounds(t):
        result = subprocess.run(
            [
                executable_path(),
                "-v",
                "error",
                "-ss",
                str(t),
                "-i",
                str(output),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        pixels = [i for i, value in enumerate(result.stdout) if value > 70]
        return min(i % 720 for i in pixels), min(i // 720 for i in pixels)

    entry, middle, exit = bounds(0.125), bounds(1), bounds(1.875)
    assert abs(entry[0] - middle[0]) <= 2
    assert abs(exit[0] - middle[0]) <= 2
    assert entry[1] > middle[1] + 5
    assert exit[1] < middle[1] - 5


def test_renderer_status_advertises_only_operator_enabled_hd(monkeypatch):
    monkeypatch.delenv("AI_TEAM_VIDEO_1080P", raising=False)
    assert renderer_status().get("supports_1080p") is False
    monkeypatch.setenv("AI_TEAM_VIDEO_1080P", "1")
    assert renderer_status().get("supports_1080p") is True
    monkeypatch.setenv("AI_TEAM_VIDEO_1080P", "true")
    assert renderer_status().get("supports_1080p") is False
