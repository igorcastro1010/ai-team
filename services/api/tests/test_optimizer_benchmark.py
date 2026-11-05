def test_local_paired_benchmark_measures_bytes_without_claiming_model_savings():
    from ai_team.optimizer_benchmark import run_benchmark

    result = run_benchmark()
    assert result["inference_calls"] == 0
    assert result["measured_token_savings"] is None
    assert result["synthetic_inputs"] is True
    assert len(result["scenarios"]) == 2
    for scenario in result["scenarios"]:
        assert scenario["mandatory_preserved"]
        assert scenario["optimized_bytes"] < scenario["baseline_bytes"]
        assert scenario["discarded_optional"] > 0
