import pytest

from ai_team.memory_safety import validate_text


@pytest.mark.parametrize("secret", ["AIza" + "x" * 35, "ya29." + "x" * 40])
def test_google_credentials_are_rejected_as_bare_text(secret):
    with pytest.raises(ValueError, match="Credencial"):
        validate_text("Documento com credencial: " + secret)


def test_google_model_names_and_documentation_remain_valid():
    text = "Gemini gemini-2.5-flash-lite e documentação Google AI Studio."
    assert validate_text(text) == text
