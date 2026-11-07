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
