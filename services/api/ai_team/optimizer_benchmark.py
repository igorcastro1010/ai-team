"""Reproducible paired context benchmark; explicitly no provider token claims."""

import json

from .token_optimizer import optimize_context


def encoded_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def run_benchmark():
    scenarios = []
    for name, request, text in (
        ("python", "Python filas", "Python filas: biblioteca padrão e workers privados. "),
        ("interface", "interface acessível", "interface acessível: foco, contraste e teclado. "),
    ):
        mandatory = {
            "request": request,
            "security": "Sem segredos, comandos livres, merge ou publicação.",
            "approvals": {"digest": "a" * 64, "approved": False},
            "previous_steps": [{"summary": "Requisitos preservados", "deliverable": "Código QA"}],
        }
        context = {
            **mandatory,
            "optional_sections": [
                {"content": text * 15},
                {"content": text * 15},
                {"content": "Documento sobre viagens sem relação com esta solicitação. " * 20},
            ],
        }
        result = optimize_context(context, [], 50000)
        baseline, optimized = encoded_bytes(context), encoded_bytes(result["context"])
        scenarios.append(
            {
                "name": name,
                "baseline_bytes": baseline,
                "optimized_bytes": optimized,
                "byte_reduction": baseline - optimized,
                "byte_reduction_percent": round((baseline - optimized) / baseline * 100, 2),
                "discarded_optional": result["discarded_optional"],
                "mandatory_preserved": all(
                    result["context"][key] == value for key, value in mandatory.items()
                ),
            }
        )
    return {
        "method": "serialized_utf8_bytes",
        "synthetic_inputs": True,
        "inference_calls": 0,
        "measured_token_savings": None,
        "scenarios": scenarios,
    }
