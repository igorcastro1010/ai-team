# Browser QA Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; one final independent read-only review.

**Goal:** Validar interações reais em projetos Next.js gerados após aprovação.
**Architecture:** Contrato QA declarativo opcional, executor Playwright confiável,
Chromium offline no runtime Docker existente. Sem nova tabela ou endpoint.
**Tech Stack:** Playwright 1.64.1, Chromium, Node 24, Next 16.4.3, Pydantic/FastAPI.
**Spec:** docs/superpowers/specs/2026-10-31-browser-qa-design.md

## Global Constraints
- Até 6 cenários × 6 ações, somente role/name para click e label/value para fill.
- 390x844; 30 s navegador dentro de 120 s totais; recursos Docker preservados.
- Não expor host/portas/segredos, não adicionar capacidades ou IPC host.
- Dependências fixas/lock revisado, instaladas apenas ao preparar imagem.

## Review Focus
- Dados malformados nunca viram scripts, selectors, comandos ou URLs.
- Mudança de critérios/runtime muda hash; históricos mantêm artefatos antigos.
- Contextos não compartilham estado; falhas/timeout não geram sucesso.
- Conteúdo externo é bloqueado; browser fecha em todos os caminhos.
- Fluxos Python, Next HTML e painel preservados.

### Task 1 — Contrato e runtime
Files: `next_artifacts.py`, `infra/next-sandbox/browser/*`, `browser-checks.mjs`,
`Dockerfile`, `run.mjs`, `tests/test_next_browser.py`.
- [ ] RED: aceitar contrato limitado e rejeitar scripts/URLs/limites excedidos.
- [ ] Implementar tipos BrowserCheck/ações, executor fixo e lock Playwright.
- [ ] GREEN: contratos, Docker clique/formulário, falha e rede bloqueada.
- [ ] Commit/push dos arquivos explícitos validados.

### Task 2 — Instruções, homologação e documentação
Files: `orchestration.py`, `tools/smoke_hermes.py`, `test_next_workflow.py`,
`docs/nextjs-code.md`, `docs/skills.md`.
- [ ] Ajustar instruções QA/CEO, preservando compatibilidade HTML existente.
- [ ] Smoke Hermes opt-in; pytest, lint, typecheck, build e E2E.
- [ ] Revisão independente, corrigir bloqueios e registrar evidências.
- [ ] Commit/push, PR rascunho sobre Next.js anterior e painel reiniciado.

## Ledger
- Reutilizar checkout limpo e branch própria: preserva instalações/cofre locais.
- Escolha técnica do agente: browser sem sandbox próprio dentro do contêiner já
  restrito; somente cenários locais sintéticos, sem ampliar privilégios Docker.
- CI de 8c45c88 aprovado em Windows, Linux, PostgreSQL e runtime Hermes.
