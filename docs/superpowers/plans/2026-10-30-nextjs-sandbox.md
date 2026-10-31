# Next.js sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, with one final independent review.

**Goal:** Gerar projeto Next.js baixável, validar build e HTML em Docker após aprovação por hash.
**Architecture:** Estender o contrato e controlador Docker existentes; runtime Node separado, scaffold confiável, QA declarativo e turno independente para relatório.
**Tech Stack:** Next 16.4.3, React 19.3.1, TS 5.9.3, Node 24, Docker Linux, API/worker existentes.
**Spec:** docs/superpowers/specs/2026-10-30-nextjs-sandbox.md

## Global Constraints

- Nenhuma mudança nos projetos existentes, credenciais, ferramentas Hermes, GitHub ou produção.
- Modelos somente fornecem TSX/CSS/JSON permitidos; scaffold e comandos são do servidor.
- Imagem preparada por lockfile e digest; tasks offline, uid 65532, sem mounts.
- 2 CPUs, 1 GiB, 128 PIDs, 120 s, tmpfs 256 MiB e saída 32 KiB.

## Review Focus

- SHA cobre scaffold e fontes; adulteração nunca chega ao executor.
- Build/servidor terminados antecipadamente não contam como sucesso.
- Modelo não altera teste QA depois do build: critérios vêm do stdin original.
- Lease expirada/cancelamento não repete suite nem deixa contêiner órfão.
- Docker/imagem ausentes não comprometem o fluxo Python/textual.

### Task 1 — Runtime e contrato
Files: `infra/next-sandbox/*`, `tools/setup_next_sandbox.py`, `services/api/ai_team/next_artifacts.py`, `next_sandbox.py`, `tests/test_next_sandbox.py`; adaptar `python_sandbox.py` minimamente para perfis fixos.
- [x] RED: caminhos, scaffold, checks, identidade imutável e recursos.
- [x] Implementar imagem revisada, supervisor e contrato com aprovação de todo o projeto.
- [x] GREEN: Docker real com build/HTML positivo e negativo, isolamento e falhas.
- [x] Commit/push dos arquivos explícitos.

### Task 2 — Workflow
Files: `orchestration.py`, `workflow.py`, `worker.py`, `run_routes.py`, `office.py`, `hermes_journal.py`, `code_artifacts.py`, `tests/test_next_workflow.py`.
- [x] RED: papéis, pausa por hash e dois turnos sem repetição da suite.
- [x] Implementar escopo Next.js, exportação scaffold e políticas compartilhadas.
- [x] GREEN: regressões Python/texto, auth/CSRF/replay e cancelamento.
- [x] Commit/push validado.

### Task 3 — Painel, homologação e revisão
Files: `apps/web/components/run-panel.tsx`, `code-artifacts.tsx`, proxy, E2E, `tools/smoke_hermes.py`, `docs/nextjs-code.md`, README.
- [x] RED/GREEN de seleção, revisão, SHA, ZIP e resultados Next.js.
- [x] Rodar pytest, lint, typecheck, build, E2E e smoke real com cinco chamadas.
- [x] Revisão independente, registrar evidências/limitações e reiniciar painel.
- [x] Commits/push e PR rascunho; sem merge/deploy.

## Ledger
- Continuação autorizada da sequência Python → Next.js; teste manual do proprietário permanece opcional.
- Critérios QA declarativos permitem conferir HTML sem executar comandos escritos pelo modelo.
- Build e relatório usam leases separadas; cinco chamadas de IA em seis ciclos de worker.
- Revisão independente: snapshot persistido cobre runtime e scaffold; histórico permanece
  estável após atualização. TextDecoder incremental preserva acentos entre chunks.
  Os dois achados foram reproduzidos e corrigidos; revisão final sem bloqueio concreto.
- Verificação: Docker real 270 passed/7 skipped; final sem opt-in 260 passed/18 skipped;
  22 E2E, lint, typecheck e build aprovados. Smoke Hermes real passou com cinco chamadas.
- Painel reiniciado: API health ok, OpenAPI inclui nextjs_code, login HTTP 200.
  PR rascunho #7 sobre codex/python-sandbox; main e produção preservados.
