import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from ai_team.optimizer_ab_benchmark import analyze_receipts, prepare_pair


def pair():
    return prepare_pair(
        context={"request": "Python", "optional_sections": [{"content": "praia"}]},
        instructions="Preserve requisitos", memories=[], budget=50000,
        provider="codex", model="explicit-model", params={"temperature": 0},
    )


def receipts(prepared, kind="provider_receipt"):
    return [
        {
            "arm": arm, "pair_digest": prepared["pair_digest"],
            "input_digest": prepared["arms"][arm]["input_digest"],
            "provider": "codex", "model": "explicit-model", "params": {"temperature": 0},
            "provenance": "provider_reported", "evidence_kind": kind, "status": "completed",
            "input_tokens": 100 if arm == "baseline" else 70, "output_tokens": 20,
            "total_tokens": 120 if arm == "baseline" else 90, "duration_ms": 400,
            "cached_input_tokens": 0,
            "quality": {"method": "manual_rubric", "rubric": "Requisitos", "score": 1},
        } for arm in ("baseline", "optimized")
    ]


def test_pair_is_deterministic_preserves_baseline_and_has_no_usage_claim():
    prepared = pair()
    assert prepared == pair()
    assert prepared["arms"]["baseline"]["input"]["context"]["optional_sections"]
    assert prepared["arms"]["optimized"]["input"]["context"]["optional_sections"] == []
    assert prepared["arms"]["baseline"]["serialized_utf8_bytes"] > 0
    assert prepared["measured_token_savings"] is None
    assert prepared["inference_calls"] == 0
    assert len(prepared["identity_digest"]) == 64


def test_complete_receipts_report_tokens_duration_cache_and_manual_quality():
    prepared = pair()
    result = analyze_receipts(prepared, receipts(prepared))
    assert result["measured_token_savings"] == 30
    assert result["usage"]["baseline"]["total_tokens"] == 120
    assert result["usage"]["optimized"]["duration_ms"] == 400
    assert result["usage"]["baseline"]["cached_input_tokens"] == 0
    assert result["quality"]["baseline"]["rubric"] == "Requisitos"
    assert result["quality_equivalence"] is None
    assert result["quality_comparison"]["rubric_matching"] is True
    assert result["quality_comparison"]["score_difference"] == 0
    assert result["reported_token_comparison"]["input_tokens"]["reduction_percent"] == 30
    assert result["reported_token_comparison"]["output_tokens"]["reduction_percent"] == 0
    assert result["reported_token_comparison"]["total_tokens"]["reduction_percent"] == 25


@pytest.mark.parametrize("field,value", [
    ("pair_digest", "wrong"), ("input_digest", "wrong"), ("model", "other"),
    ("provider", "other"), ("params", {}), ("provenance", "estimated"),
    ("input_tokens", True), ("output_tokens", -1), ("total_tokens", 999),
    ("duration_ms", -1), ("status", "running"), ("cached_input_tokens", 999),
])
def test_unbound_or_invalid_receipts_cannot_claim_savings(field, value):
    prepared = pair()
    evidence = receipts(prepared)
    evidence[0][field] = value
    result = analyze_receipts(prepared, evidence)
    assert result["measured_token_savings"] is None
    assert result["errors"]


def test_missing_duplicate_or_fixture_evidence_never_claims_real_savings():
    prepared = pair()
    evidence = receipts(prepared)
    for incomplete in ([], evidence[:1], [evidence[0], evidence[0]]):
        assert analyze_receipts(prepared, incomplete)["measured_token_savings"] is None
    fixture = analyze_receipts(prepared, receipts(prepared, "fixture"))
    assert fixture["measured_token_savings"] is None
    assert fixture["fixture_token_difference"] == 30
    assert fixture["reported_token_comparison"] is None
    assert fixture["fixture_token_comparison"]["total_tokens"]["reduction_percent"] == 25


def test_pair_tampering_and_secrets_are_rejected():
    prepared = pair()
    tampered = deepcopy(prepared)
    tampered["arms"]["optimized"]["input"]["instructions"] = "changed"
    assert analyze_receipts(tampered, receipts(prepared))["measured_token_savings"] is None
    with pytest.raises(ValueError):
        prepare_pair(context={"request": "ghp_" + "A" * 36}, instructions="safe",
                     memories=[], budget=50000, provider="codex", model="explicit", params={})


def test_missing_quality_or_cache_remains_unknown_without_inventing_values():
    prepared = pair()
    evidence = receipts(prepared)
    del evidence[0]["quality"]
    del evidence[0]["cached_input_tokens"]
    result = analyze_receipts(prepared, evidence)
    assert result["quality"]["baseline"] is None
    assert result["usage"]["baseline"]["cached_input_tokens"] is None
    assert result["measured_token_savings"] is None


def test_parameter_types_are_part_of_identity():
    prepared = pair()
    evidence = receipts(prepared)
    evidence[0]["params"] = {"temperature": False}
    assert analyze_receipts(prepared, evidence)["measured_token_savings"] is None


def test_zero_baseline_and_different_rubrics_have_no_percentage_or_quality_comparison():
    prepared = pair()
    evidence = receipts(prepared)
    evidence[0].update(input_tokens=0, output_tokens=0, total_tokens=0)
    evidence[1]["quality"]["rubric"] = "Other rubric"
    result = analyze_receipts(prepared, evidence)
    assert result["reported_token_comparison"]["total_tokens"]["reduction_percent"] is None
    assert result["quality_comparison"]["rubric_matching"] is False
    assert result["quality_comparison"]["score_difference"] is None


@pytest.mark.parametrize("content", ["x" * 500001, '{"secret": "ghp_' + "A" * 36 + '"}'])
def test_offline_cli_rejects_invalid_input_without_echoing_content(tmp_path, content):
    source = tmp_path / "input.json"
    source.write_text(content, encoding="utf-8")
    script = Path(__file__).resolve().parents[3] / "tools" / "prepare_optimizer_ab.py"
    command = subprocess.run([sys.executable, str(script), str(source)], capture_output=True,
                             text=True, timeout=15, check=False)
    assert command.returncode == 2
    assert command.stdout == ""
    assert "ghp_" not in command.stderr


def test_offline_cli_has_no_live_option():
    script = Path(__file__).resolve().parents[3] / "tools" / "prepare_optimizer_ab.py"
    command = subprocess.run([sys.executable, str(script), "unused.json", "--live"],
                             capture_output=True, text=True, timeout=15, check=False)
    assert command.returncode == 2
    assert "unrecognized arguments: --live" in command.stderr
