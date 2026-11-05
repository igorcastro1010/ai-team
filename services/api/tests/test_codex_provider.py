import sys

import pytest

from ai_team.codex_provider import CodexProvider, execution_command
from ai_team.orchestration import DraftContent


def test_output_schema_is_strict_including_nested_delegations():
    schema = DraftContent.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["Delegation"]["additionalProperties"] is False


def test_command_disables_shell_tools_plugins_network_and_broad_file_reads(tmp_path):
    command = execution_command(["codex.exe"], tmp_path)
    assert "--ignore-user-config" in command and "--ignore-rules" in command
    assert "--strict-config" in command and "--ephemeral" in command
    assert "features.shell_tool=false" in command
    assert "features.plugins=false" in command and "features.apps=false" in command
    assert "permissions.ai-team.network.enabled=false" in command
    assert '":root"="deny"' in " ".join(command)
    assert "danger-full-access" not in " ".join(command)


def test_process_uses_stdin_filtered_environment_and_validates_output(tmp_path, monkeypatch):
    script = tmp_path / "fake.py"
    script.write_text(
        """import json, os, sys
assert 'GITHUB_TOKEN' not in os.environ
assert 'request' in sys.stdin.read()
out = sys.argv[sys.argv.index('-o') + 1]
with open(out, 'w', encoding='utf-8') as f:
    json.dump({'summary':'Teste','deliverable':'Proposta válida','tasks':[]},f)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':23,'output_tokens':8}}))
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_TOKEN", "never-pass-to-child")
    provider = CodexProvider(command=[sys.executable, str(script)], home=tmp_path / "home")
    draft = provider.generate("CEO", "Instruções", {"request": "teste"}, lambda: None)
    assert draft.input_tokens == 23 and draft.output_tokens == 8
    assert draft.deliverable == "Proposta válida"


def test_timeout_stops_child_and_does_not_return_fake_result(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(30)", encoding="utf-8")
    provider = CodexProvider(
        command=[sys.executable, str(script)], home=tmp_path / "home", time_limit=0.15
    )
    with pytest.raises(TimeoutError):
        provider.generate("CEO", "teste", {"request": "teste"}, lambda: None)


def test_cancellation_stops_child(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(30)", encoding="utf-8")
    provider = CodexProvider(command=[sys.executable, str(script)], home=tmp_path / "home")

    def cancelled():
        raise InterruptedError("Cancelado")

    with pytest.raises(InterruptedError):
        provider.generate("CEO", "teste", {"request": "teste"}, cancelled)


def test_windows_sharing_violation_cleanup_does_not_mask_cancellation(tmp_path, monkeypatch):
    import tempfile

    script = tmp_path / "cancel.py"
    script.write_text("import time; time.sleep(30)", encoding="utf-8")
    provider = CodexProvider(command=[sys.executable, str(script)], home=tmp_path / "home")
    original = tempfile.TemporaryDirectory.cleanup
    attempts = []

    def cleanup(directory):
        attempts.append(directory.name)
        if len(attempts) < 3:
            error = PermissionError("Synthetic Windows sharing violation")
            error.winerror = 32
            raise error
        return original(directory)

    monkeypatch.setattr(tempfile.TemporaryDirectory, "cleanup", cleanup)

    def cancelled():
        raise InterruptedError("Cancelado")

    with pytest.raises(InterruptedError):
        provider.generate("CEO", "teste", {"request": "teste"}, cancelled)
    assert len(attempts) == 3
    assert not list((tmp_path / "jobs").glob("draft-*"))


def test_timeout_also_applies_when_child_never_reads_large_stdin(tmp_path):
    script = tmp_path / "unread.py"
    script.write_text("import time; time.sleep(3)", encoding="utf-8")
    provider = CodexProvider(
        command=[sys.executable, str(script)], home=tmp_path / "home", time_limit=0.15
    )
    with pytest.raises(TimeoutError):
        provider.generate("CEO", "teste", {"request": "x" * 200000}, lambda: None)


def test_raw_errors_and_invalid_json_are_not_returned_as_success(tmp_path):
    script = tmp_path / "bad.py"
    script.write_text(
        """import sys
print('SECRET=must-not-propagate', file=sys.stderr)
raise SystemExit(7)
""",
        encoding="utf-8",
    )
    provider = CodexProvider(command=[sys.executable, str(script)], home=tmp_path / "home")
    with pytest.raises(RuntimeError) as error:
        provider.generate("CEO", "teste", {"request": "teste"}, lambda: None)
    assert "SECRET" not in str(error.value)
