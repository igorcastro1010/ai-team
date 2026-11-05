"""Live harness configuration must not silently select a different executor."""

import runpy

import pytest

from ai_team.config import ROOT, Settings
from ai_team.hermes import HermesProvider


@pytest.fixture
def harness():
    return runpy.run_path(str(ROOT / "tools" / "smoke_repository.py"))


def test_live_smoke_defaults_preserve_codex_and_require_consent(harness):
    with pytest.raises(SystemExit):
        harness["parse_args"]([])
    args = harness["parse_args"](["--real"])
    assert args.executor == "codex" and args.max_tokens == 50000


def test_live_smoke_selects_hermes_and_bounded_budget(harness):
    args = harness["parse_args"](["--real", "--executor", "hermes", "--max-tokens", "100000"])
    assert args.executor == "hermes" and args.max_tokens == 100000
    assert isinstance(harness["provider_for"]("hermes", Settings()), HermesProvider)


@pytest.mark.parametrize("budget", ["15999", "100001"])
def test_invalid_budget_rejected_before_any_provider_call(harness, budget):
    with pytest.raises(SystemExit):
        harness["parse_args"](["--real", "--max-tokens", budget])
