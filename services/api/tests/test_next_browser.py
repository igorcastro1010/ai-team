import json
import os
import subprocess

import pytest
from pydantic import ValidationError
from test_next_sandbox import steps

from ai_team.next_artifacts import Acceptance, project_for_steps


def criteria(expected="Olá, Igor"):
    return {
        "checks": [{"name": "titulo", "contains": "AI TEAM"}],
        "browser_checks": [
            {
                "name": "formulario",
                "actions": [
                    {"action": "fill", "label": "Nome", "value": "Igor"},
                    {"action": "click", "role": "button", "name": "Salvar"},
                ],
                "expect_text": expected,
            }
        ],
    }


def test_browser_contract_preserves_html_checks_and_changes_approval_hash():
    data = criteria()
    assert Acceptance.model_validate(data).browser_checks[0].actions[0].value == "Igor"
    source = steps()
    before = project_for_steps(source)
    source[2]["deliverable"] = json.dumps(
        {
            "files": [
                {
                    "path": "tests/acceptance.json",
                    "content": json.dumps(data),
                }
            ]
        }
    )
    assert project_for_steps(source).digest != before.digest


@pytest.mark.parametrize(
    "change",
    [
        {"url": "https://evil.test"},
        {"script": "process.exit(0)"},
        {"actions": []},
        {"actions": [{"action": "evaluate", "value": "alert(1)"}]},
        {"actions": [{"action": "click", "role": "button", "name": "X", "selector": "body"}]},
        {"actions": [{"action": "click", "role": "application", "name": "X"}]},
        {"actions": [{"action": "fill", "label": "Nome", "value": "x" * 501}]},
        {"expect_text": ""},
    ],
)
def test_browser_contract_rejects_commands_destinations_and_unbounded_input(change):
    data = criteria()
    data["browser_checks"][0].update(change)
    with pytest.raises(ValidationError):
        Acceptance.model_validate(data)


def test_browser_contract_limits_scenarios_and_actions():
    data = criteria()
    data["browser_checks"] *= 7
    with pytest.raises(ValidationError):
        Acceptance.model_validate(data)
    data = criteria()
    data["browser_checks"][0]["actions"] *= 4
    with pytest.raises(ValidationError):
        Acceptance.model_validate(data)


def test_trusted_browser_interpreter_rejects_unreviewed_instructions():
    from ai_team.next_artifacts import RUNTIME

    script = """
import assert from 'node:assert/strict';
import {validateBrowserChecks} from './browser-checks.mjs';
assert.throws(()=>validateBrowserChecks([{name:'x',expect_text:'x',
 actions:[{action:'evaluate',value:'process.exit(0)'}]}]));
assert.throws(()=>validateBrowserChecks([{name:'x',expect_text:'x',url:'https://example.com',
 actions:[{action:'click',role:'button',name:'X'}]}]));
assert.deepEqual(validateBrowserChecks([]), []);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=RUNTIME, check=True, timeout=10
    )


@pytest.mark.skipif(os.getenv("AI_TEAM_NEXT_SANDBOX_TESTS") != "1", reason="Next Docker opt-in")
@pytest.mark.parametrize(
    ("expected", "status"), [("Olá, Igor", "passed"), ("Nunca aparece", "failed")]
)
def test_real_chromium_fills_clicks_and_checks_visible_result(expected, status):
    from ai_team.next_sandbox import NextSandbox

    source = steps()
    page = """"use client";
import {useState} from "react";
export default function Page(){
  const [name,setName]=useState("Visitante"); const [saved,setSaved]=useState("");
  return <main><h1>AI TEAM</h1><label>Nome<input value={name}
    onChange={e=>setName(e.target.value)}/></label>
    <button onClick={()=>setSaved("Olá, "+name)}>Salvar</button>
    <p>{saved || "Aguardando"}</p></main>;
}"""
    source[0]["deliverable"] = json.dumps({"files": [{"path": "app/page.tsx", "content": page}]})
    data = criteria(expected)
    if status == "passed":
        data["browser_checks"].append(
            {
                "name": "contexto independente",
                "actions": [{"action": "click", "role": "button", "name": "Salvar"}],
                "expect_text": "Olá, Visitante",
            }
        )
    source[2]["deliverable"] = json.dumps(
        {
            "files": [
                {
                    "path": "tests/acceptance.json",
                    "content": json.dumps(data),
                }
            ]
        }
    )
    result = NextSandbox().run(project_for_steps(source), lambda: None)
    assert result["status"] == status, result["output"]
    assert f'"browser_checks":{len(data["browser_checks"])}' in result["output"]


@pytest.mark.skipif(os.getenv("AI_TEAM_NEXT_SANDBOX_TESTS") != "1", reason="Next Docker opt-in")
def test_real_browser_blocks_foreign_destinations():
    from ai_team.next_sandbox import NextSandbox

    source = steps()
    source[0]["deliverable"] = json.dumps(
        {
            "files": [
                {
                    "path": "app/page.tsx",
                    "content": "export default function Page(){return <main><h1>AI TEAM</h1>"
                    '<a href="http://127.0.0.1:3001/">Abrir</a></main>}',
                }
            ]
        }
    )
    data = criteria("Destino externo")
    data["browser_checks"][0]["actions"] = [{"action": "click", "role": "link", "name": "Abrir"}]
    source[2]["deliverable"] = json.dumps(
        {
            "files": [
                {
                    "path": "tests/acceptance.json",
                    "content": json.dumps(data),
                }
            ]
        }
    )
    result = NextSandbox().run(project_for_steps(source), lambda: None)
    assert result["status"] == "failed", result["output"]
    summaries = [
        json.loads(line) for line in result["output"].splitlines() if line.startswith('{"build":')
    ]
    assert summaries[-1]["blocked_requests"] >= 1
