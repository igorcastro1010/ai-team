"""Offline A/B preparation and analysis of supplied receipts; never dispatches inference."""

import json
import math
from copy import deepcopy

from .memory_safety import validate_text
from .token_optimizer import digest, estimate, optimize_context


def _safe(value):
    validate_text(json.dumps(value, ensure_ascii=False, allow_nan=False), maximum=500000)
    if isinstance(value, str):
        validate_text(value, maximum=500000)
    elif isinstance(value, dict):
        for key, item in value.items():
            _safe(key)
            _safe(item)
    elif isinstance(value, list):
        for item in value:
            _safe(item)


def prepare_pair(*, context, instructions, memories, budget, provider, model, params):
    """Prepare identical provider settings and immutable initial inputs in both arms."""
    if not isinstance(context, dict) or not isinstance(memories, list):
        raise ValueError("Contexto e memórias inválidos")
    if not all(isinstance(v, str) and v.strip() for v in (instructions, provider, model)):
        raise ValueError("Instruções, provider e modelo explícitos são obrigatórios")
    if not isinstance(params, dict) or type(budget) is not int or budget < 1:
        raise ValueError("Parâmetros ou limite inválidos")
    initial = deepcopy({"context": context, "memories": memories, "budget": budget})
    identity = deepcopy({"provider": provider, "model": model, "params": params})
    _safe([initial, identity, instructions])
    selected = optimize_context(context, memories, budget)
    arms = {}
    for name, chosen in (("baseline", context), ("optimized", selected["context"])):
        payload = deepcopy({"instructions": instructions, "context": chosen, **identity})
        arms[name] = {"input": payload, "input_digest": digest(payload),
                      "serialized_utf8_bytes": estimate(payload)}
    prepared = {
        "schema": "optimizer-ab-v1", "identity": identity, "initial": initial,
        "identity_digest": digest(identity),
        "initial_digest": digest(initial), "arms": arms,
        "retrieval": {"selected_memories": selected["selected_memories"],
                      "candidate_memories": len(memories), "cache": "not_used_offline"},
        "inference_calls": 0, "measured_token_savings": None,
        "byte_method": "serialized_utf8_bytes_not_tokens",
    }
    return {**prepared, "pair_digest": digest(prepared)}


def analyze_receipts(pair, receipts):
    """Validate binding, never infer usage/quality or independently authenticate receipts."""
    result = {"measured_token_savings": None, "fixture_token_difference": None,
              "usage": {}, "quality": {}, "quality_equivalence": None,
              "quality_comparison": None, "reported_token_comparison": None,
              "fixture_token_comparison": None,
              "errors": [], "inference_calls": 0,
              "evidence": "supplied_receipts_not_independently_verified"}
    errors = result["errors"]
    try:
        _safe([pair, receipts])
        unsigned = {k: v for k, v in pair.items() if k != "pair_digest"}
        if digest(unsigned) != pair["pair_digest"]:
            raise ValueError("Digest do par inválido")
        identity = pair["identity"]
        for arm in ("baseline", "optimized"):
            payload = pair["arms"][arm]["input"]
            if digest(payload) != pair["arms"][arm]["input_digest"]:
                raise ValueError("Digest de entrada inválido")
        if not isinstance(receipts, list) or len(receipts) != 2:
            raise ValueError("Dois recibos completos são obrigatórios")
        kinds = []
        for receipt in receipts:
            arm = receipt.get("arm")
            if arm not in pair["arms"] or arm in result["usage"]:
                raise ValueError("Braço ausente, duplicado ou inválido")
            if receipt.get("pair_digest") != pair["pair_digest"] or receipt.get(
                "input_digest"
            ) != pair["arms"][arm]["input_digest"]:
                raise ValueError("Recibo não corresponde às entradas")
            if any(digest(receipt.get(key)) != digest(identity[key])
                   for key in ("provider", "model", "params")):
                raise ValueError("Provider, modelo ou parâmetros diferentes")
            if receipt.get("provenance") != "provider_reported":
                raise ValueError("Consumo não reportado pelo provider")
            kind = receipt.get("evidence_kind")
            if kind not in {"provider_receipt", "fixture"} or receipt.get("status") != "completed":
                raise ValueError("Evidência incompleta ou sem origem explícita")
            kinds.append(kind)
            usage = {key: receipt.get(key) for key in (
                "input_tokens", "output_tokens", "total_tokens", "duration_ms",
                "cached_input_tokens",
            )}
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                if type(usage[key]) is not int or usage[key] < 0:
                    raise ValueError("Contagem de tokens inválida ou ausente")
            if usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
                raise ValueError("Total de tokens inconsistente")
            duration = usage["duration_ms"]
            if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
                raise ValueError("Duração inválida ou ausente")
            cached = usage["cached_input_tokens"]
            if cached is not None and (type(cached) is not int or not 0 <= cached <= usage[
                "input_tokens"
            ]):
                raise ValueError("Uso de cache inválido")
            quality = receipt.get("quality")
            if quality is not None and (
                not isinstance(quality, dict) or quality.get("method") != "manual_rubric"
                or not isinstance(quality.get("rubric"), str) or not quality["rubric"].strip()
                or type(quality.get("score")) not in (int, float)
                or not math.isfinite(quality["score"])
            ):
                raise ValueError("Qualidade exige avaliação manual com rubrica e score")
            result["usage"][arm] = usage
            result["quality"][arm] = quality
        result["retrieval"] = deepcopy(pair["retrieval"])
        if any(result["usage"][arm]["cached_input_tokens"] is None or result["quality"][arm]
               is None for arm in ("baseline", "optimized")):
            raise ValueError("Cache ou avaliação manual ausente; comparação incompleta")
        difference = result["usage"]["baseline"]["total_tokens"] - result["usage"][
            "optimized"
        ]["total_tokens"]
        comparisons = {}
        for metric in ("input_tokens", "output_tokens", "total_tokens"):
            baseline = result["usage"]["baseline"][metric]
            optimized = result["usage"]["optimized"][metric]
            comparisons[metric] = {
                "baseline": baseline, "optimized": optimized,
                "difference": baseline - optimized,
                "reduction_percent": (baseline - optimized) / baseline * 100
                if baseline > 0 else None,
            }
        baseline_quality, optimized_quality = (result["quality"][arm]
                                                for arm in ("baseline", "optimized"))
        matching = baseline_quality["rubric"] == optimized_quality["rubric"]
        result["quality_comparison"] = {
            "rubric_matching": matching,
            "score_difference": optimized_quality["score"] - baseline_quality["score"]
            if matching else None,
            "evidence_kind": "fixture" if "fixture" in kinds else "supplied_manual_rubric",
        }
        if kinds == ["provider_receipt", "provider_receipt"]:
            result["measured_token_savings"] = difference
            result["reported_token_comparison"] = comparisons
        elif kinds == ["fixture", "fixture"]:
            result["fixture_token_difference"] = difference
            result["fixture_token_comparison"] = comparisons
        else:
            raise ValueError("Não misture fixtures com recibos de provider")
    except (ValueError, TypeError, KeyError, AttributeError):
        errors.append("Par ou recibos inválidos/incompletos; economia não estabelecida")
    return result
