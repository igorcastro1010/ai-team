import json
import os
import time

import pytest
from pydantic import ValidationError

from ai_team.code_artifacts import CodeBundle, bundle_for_steps
from ai_team.python_sandbox import IMAGE, sandbox_command


def bundle():
    return CodeBundle(
        files=[
            {"path": "main.py", "content": "def add(a, b): return a + b\n"},
            {"path": "test_main.py", "content": "import unittest\n"},
        ]
    )


@pytest.mark.parametrize(
    "path",
    [
        "../x.py",
        "/x.py",
        "C:/x.py",
        "a\\x.py",
        "x.py/../y.py",
        ".env",
        "README.md",
        "a//x.py",
        "con.py",
        "sitecustomize.py",
        "__init__.py",
        "unittest.py",
        "a.py\n",
    ],
)
def test_paths_are_strict_relative_python_files(path):
    with pytest.raises(ValidationError):
        CodeBundle(files=[{"path": path, "content": "pass"}])


def test_bundle_bounds_and_unique_paths():
    for files in [
        [],
        [{"path": "main.py", "content": "x" * 49000}],
        [{"path": "main.py", "content": "pass"}] * 2,
    ]:
        with pytest.raises(ValidationError):
            CodeBundle(files=files)


def test_digest_covers_exact_content_independent_of_order():
    original = bundle()
    assert original.digest == CodeBundle(files=list(reversed(original.files))).digest
    modified = original.model_dump()
    modified["files"][0]["content"] += "\n"
    assert original.digest != CodeBundle(**modified).digest


def test_qa_cannot_replace_dev_files_and_bundle_requires_tests():
    steps = [
        {
            "agent": "DEV",
            "deliverable": json.dumps({"files": [{"path": "main.py", "content": "pass"}]}),
        },
        {
            "agent": "QA",
            "deliverable": json.dumps({"files": [{"path": "test_main.py", "content": "pass"}]}),
        },
    ]
    assert len(bundle_for_steps(steps).files) == 2
    steps[1]["deliverable"] = steps[0]["deliverable"]
    with pytest.raises(ValueError):
        bundle_for_steps(steps)


def test_command_is_fixed_no_mounts_no_network_or_credentials():
    argv = sandbox_command("ai-team-test-123")
    assert IMAGE.startswith("python@sha256:")
    assert argv[:2] == ["docker", "run"]
    for flag, value in [
        ("--network", "none"),
        ("--user", "65532:65532"),
        ("--cap-drop", "ALL"),
        ("--memory", "256m"),
        ("--memory-swap", "256m"),
        ("--pids-limit", "64"),
        ("--cpus", "1"),
        ("--pull", "never"),
    ]:
        assert argv[argv.index(flag) + 1] == value
    assert "--read-only" in argv
    assert not {"-v", "--volume", "--mount", "--privileged", "-e", "--env-file"} & set(argv)


def test_cleanup_accepts_concurrent_auto_removal_but_not_unknown_scope(monkeypatch):
    from types import SimpleNamespace

    from ai_team.python_sandbox import PythonSandbox

    name = "ai-team-test-" + "a" * 32
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout=b"abcdef123456|next-test\n"),
            SimpleNamespace(returncode=1, stdout=b""),
            SimpleNamespace(returncode=0, stdout=b""),
        ]
    )
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: next(responses))
    PythonSandbox.cleanup(name)
    calls = []

    def other(argv, **kw):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=b"abcdef123456|other-scope\n")

    monkeypatch.setattr("subprocess.run", other)
    with pytest.raises(RuntimeError):
        PythonSandbox.cleanup(name)
    assert not any("rm" in argv for argv in calls)


@pytest.mark.skipif(os.getenv("AI_TEAM_SANDBOX_TESTS") != "1", reason="Docker real opt-in")
@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("self.assertEqual(add(2, 3), 5)", "passed"),
        ("self.assertEqual(add(2, 3), 9)", "failed"),
        ("while True: pass", "timeout"),
        ('print("x" * 100000)', "output_limit"),
        (
            "self.assertEqual(os.getuid(), 65532); "
            'self.assertFalse(os.path.exists("/var/run/docker.sock")); '
            'self.assertFalse(os.path.exists("/.env")); '
            'self.assertRaises(OSError, pathlib.Path("/blocked").write_text, "x"); '
            'self.assertRaises(OSError, socket.create_connection, ("1.1.1.1", 443), 0.2)',
            "passed",
        ),
    ],
)
def test_real_docker_limits(code, status):
    from ai_team.python_sandbox import PythonSandbox

    files = bundle().model_dump()["files"]
    files[1]["content"] = (
        "import unittest, os, socket, pathlib\nfrom main import add\n"
        "class TestGenerated(unittest.TestCase):\n    def test_generated(self):\n        "
        + code
        + "\n"
    )
    result = PythonSandbox(time_limit=2).run(CodeBundle(files=files), lambda: None)
    assert result["status"] == status, result
    assert len(result["output"].encode("utf-8")) <= 32768


@pytest.mark.skipif(os.getenv("AI_TEAM_SANDBOX_TESTS") != "1", reason="Docker real opt-in")
def test_real_cancel_cleans_container_and_empty_suite_fails():
    from ai_team.python_sandbox import PythonSandbox

    assert PythonSandbox().run(bundle(), lambda: None)["exit_code"] == 3
    deadline = time.monotonic() + 0.5

    def cancelled():
        if time.monotonic() > deadline:
            raise InterruptedError("Teste de cancelamento")

    data = bundle().model_dump()
    data["files"][1]["content"] = "while True: pass\n"
    with pytest.raises(InterruptedError):
        PythonSandbox().run(CodeBundle(**data), cancelled)


@pytest.mark.skipif(os.getenv("AI_TEAM_SANDBOX_TESTS") != "1", reason="Docker real opt-in")
def test_premature_exit_and_invalid_utf8_never_report_success_or_unbounded_output():
    from ai_team.python_sandbox import PythonSandbox

    data = bundle().model_dump()
    data["files"][1]["content"] = "import os\nos._exit(0)\n"
    assert PythonSandbox().run(CodeBundle(**data), lambda: None)["status"] == "failed"
    data["files"][1]["content"] = 'import os\nos.write(1, b"\\xff" * 40000)\n'
    result = PythonSandbox().run(CodeBundle(**data), lambda: None)
    assert len(result["output"].encode("utf-8")) <= 32768


@pytest.mark.skipif(os.getenv("AI_TEAM_SANDBOX_TESTS") != "1", reason="Docker real opt-in")
def test_container_watchdog_survives_host_controller_death():
    import subprocess
    import sys

    from ai_team.codex_provider import stop_process
    from ai_team.python_sandbox import PythonSandbox

    name = PythonSandbox.new_name()
    child = (
        "import sys; from ai_team.code_artifacts import CodeBundle; "
        "from ai_team.python_sandbox import PythonSandbox; "
        'b=CodeBundle(files=[{"path":"test_hang.py","content":"while True: pass"}]); '
        "PythonSandbox().run(b,lambda:None,name=sys.argv[1])"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", child, name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
    )
    try:

        def containers():
            return subprocess.run(
                ["docker", "ps", "-aq", "--filter", f"name=^{name}$"],
                capture_output=True,
                timeout=5,
                check=True,
            ).stdout.strip()

        started = time.monotonic() + 10
        while not containers():
            assert time.monotonic() < started, "Contêiner de teste não iniciou"
            time.sleep(0.2)
        stop_process(process)  # Forcefully kill the host tree; finally cannot rescue it.
        deadline = time.monotonic() + 35
        while containers() and time.monotonic() < deadline:
            time.sleep(0.5)
        assert not containers(), "Watchdog deixou contêiner órfão"
    finally:
        if process.poll() is None:
            stop_process(process)
        PythonSandbox.cleanup(name)
