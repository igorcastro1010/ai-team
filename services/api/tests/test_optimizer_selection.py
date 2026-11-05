from ai_team.token_optimizer import optimize_context


def test_unknown_optional_format_falls_back_without_removing_requirements():
    original = {"request": "Preservar requisitos", "optional_sections": "Requisito legado"}
    result = optimize_context(original, [], 50000)
    assert result["context"] == original
    assert result["fallback_reason"] == "unsupported_optional_format"


def test_context_selection_respects_accented_note_titles_and_reports_discarded():
    original = {
        "request": "decisao",
        "optional_sections": [
            {"content": "decisao documentada"},
            {"content": "decisao documentada"},
            {"content": "irrelevante"},
        ],
    }
    result = optimize_context(
        original,
        [{"id": "n", "title": "Decisão", "content": "Workers privados.", "version": 1}],
        50000,
    )
    assert len(result["context"]["untrusted_project_memory"]["notes"]) == 1
    assert result["discarded_optional"] == 2
    assert result["selected_memories"] == ["n"]
    assert result["measured_savings"] is None
