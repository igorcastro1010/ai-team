import pytest
from pydantic import ValidationError


def test_studio_document_accepts_media_styles_audio_and_three_aspects():
    from ai_team.video_schema import StudioDocument

    for aspect in ("vertical", "square", "horizontal"):
        value = StudioDocument(
            title="Produto",
            format=aspect,
            scenes=[
                {
                    "text": "Oferta",
                    "duration": 2,
                    "animation": "zoom",
                    "text_animation": "slide",
                    "transition": "fade",
                    "font": "serif",
                    "x": 20,
                    "color": "#22ff99",
                }
            ],
        )
        assert value.resolution == "720p" and value.scenes[0].x == 20


@pytest.mark.parametrize(
    "patch",
    [
        {"x": 101},
        {"color": "red;movie=http://evil"},
        {"font": "../../secret"},
        {"duration": True},
        {"animation": "shell"},
        {"media_id": "../../secret"},
    ],
)
def test_studio_rejects_unbounded_styles_and_paths(patch):
    from ai_team.video_schema import StudioDocument

    with pytest.raises(ValidationError):
        StudioDocument(title="Produto", scenes=[{"text": "Olá", "duration": 2, **patch}])


def test_render_input_accepts_studio_document_but_rejects_empty_scene():
    import uuid

    from ai_team.video_routes import VideoInput

    payload = dict(
        project_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        title="Vídeo",
        format="square",
        resolution="720p",
        consent=True,
        scenes=[{"text": "Olá", "animation": "pan", "duration": 2}],
    )
    assert VideoInput(**payload).scenes[0].animation == "pan"
    with pytest.raises(ValidationError):
        VideoInput(**(payload | {"scenes": [{"text": "", "duration": 2}]}))
