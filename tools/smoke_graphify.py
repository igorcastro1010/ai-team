"""Offline Graphify compatibility smoke: synthetic graph, query and Obsidian export.

No extraction, semantic processing, providers, repository hooks or remote writes.
Only an operator-selected installed executable and fixed argument lists are used.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", default=shutil.which("graphify"))
    args = parser.parse_args()
    if not args.binary or not Path(args.binary).is_file():
        print(
            json.dumps(
                {"status": "unavailable", "reason": "Graphify CLI not installed"}
            )
        )
        return 2
    binary = str(Path(args.binary).resolve())
    with tempfile.TemporaryDirectory(prefix="ai-team-graphify-") as folder:
        root = Path(folder)
        home = root / "private-home"
        home.mkdir()
        # Allowlist OS bootstrap variables; no ambient tokens, CLI sessions, proxies or keys.
        environment = {
            name: os.environ[name]
            for name in ("SYSTEMROOT", "WINDIR", "COMSPEC")
            if name in os.environ
        }
        environment.update(
            {
                "PATH": os.defpath,
                "HOME": str(home),
                "USERPROFILE": str(home),
                "APPDATA": str(home),
                "LOCALAPPDATA": str(home),
                "TEMP": str(root),
                "TMP": str(root),
                "PYTHONUTF8": "1",
                "NO_PROXY": "*",
                "DO_NOT_TRACK": "1",
            }
        )
        graph = root / "graph.json"
        graph.write_text(
            json.dumps(
                {
                    "directed": True,
                    "multigraph": False,
                    "graph": {"project_id": "offline-smoke", "schema_version": 1},
                    "nodes": [
                        {
                            "id": "memory:planning",
                            "label": "Planning",
                            "kind": "memory",
                            "provenance": "memory_entries:planning",
                        },
                        {
                            "id": "task:scheduler",
                            "label": "Scheduler",
                            "kind": "task",
                            "provenance": "tasks:scheduler",
                        },
                    ],
                    "links": [
                        {
                            "source": "memory:planning",
                            "target": "task:scheduler",
                            "relation": "documents",
                            "provenance": "fixture:explicit",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        vault = root / "obsidian"
        commands = [
            ("version", ["--version"]),
            (
                "query",
                [
                    "query",
                    "Planning",
                    "--seed",
                    "memory:planning",
                    "--budget",
                    "100",
                    "--graph",
                    str(graph),
                ],
            ),
            (
                "obsidian",
                ["export", "obsidian", "--graph", str(graph), "--dir", str(vault)],
            ),
        ]
        checks = {}
        for name, command in commands:
            try:
                # Output goes to a private temporary file and is never echoed verbatim.
                with (root / f"{name}.log").open("wb") as log:
                    result = subprocess.run(
                        [binary, *command],
                        cwd=root,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=30,
                        check=False,
                    )
                output = (
                    (root / f"{name}.log")
                    .read_bytes()[:65536]
                    .decode("utf-8", "replace")
                )
                checks[name] = {"exit_code": result.returncode}
                if name == "version":
                    import re

                    version = re.search(r"graphify ([0-9]+\.[0-9]+\.[0-9]+)", output)
                    checks[name]["version"] = version.group(1) if version else "unknown"
                if result.returncode:
                    print(json.dumps({"status": "failed", "checks": checks}))
                    return 1
                if name == "query" and not all(
                    word in output for word in ("Planning", "Scheduler")
                ):
                    print(
                        json.dumps(
                            {"status": "failed", "reason": "missing query nodes"}
                        )
                    )
                    return 1
            except (OSError, subprocess.TimeoutExpired):
                print(
                    json.dumps(
                        {"status": "failed", "reason": "CLI unavailable or timed out"}
                    )
                )
                return 1
        notes, canvases = list(vault.rglob("*.md")), list(vault.rglob("*.canvas"))
        if len(notes) < 2 or not canvases:
            print(
                json.dumps({"status": "failed", "reason": "missing Obsidian artifacts"})
            )
            return 1
        markdown = "\n".join(note.read_text(encoding="utf-8") for note in notes)
        if "[[Scheduler]]" not in markdown or "documents" not in markdown:
            print(
                json.dumps({"status": "failed", "reason": "missing explicit wikilink"})
            )
            return 1
        canvas = json.loads(canvases[0].read_text(encoding="utf-8"))
        if len(canvas.get("nodes", [])) < 2 or not canvas.get("edges"):
            print(
                json.dumps(
                    {"status": "failed", "reason": "missing canvas relationship"}
                )
            )
            return 1
        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": checks,
                    "notes": len(notes),
                    "canvases": len(canvases),
                    "synthetic_only": True,
                    "inference_calls": 0,
                    "hooks_installed": False,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
