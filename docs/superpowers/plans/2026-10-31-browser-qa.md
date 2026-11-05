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
- [x] RED: aceitar contrato limitado e rejeitar scripts/URLs/limites excedidos.
- [x] Implementar tipos BrowserCheck/ações, executor fixo e lock Playwright.
- [x] GREEN: contratos, Docker clique/formulário, falha e rede bloqueada.
- [x] Commit/push dos arquivos explícitos validados.

### Task 2 — Instruções, homologação e documentação
Files: `orchestration.py`, `tools/smoke_hermes.py`, `test_next_workflow.py`,
`docs/nextjs-code.md`, `docs/skills.md`.
- [x] Ajustar instruções QA/CEO, preservando compatibilidade HTML existente.
- [x] Smoke Hermes opt-in; pytest, lint, typecheck, build e E2E.
- [x] Revisão independente, corrigir bloqueios e registrar evidências.
- [x] Commit/push, PR rascunho sobre Next.js anterior e painel reiniciado.

## Ledger
- Reutilizar checkout limpo e branch própria: preserva instalações/cofre locais.
- Escolha técnica do agente: browser sem sandbox próprio dentro do contêiner já
  restrito; somente cenários locais sintéticos, sem ampliar privilégios Docker.
- CI de 8c45c88 aprovado em Windows, Linux, PostgreSQL e runtime Hermes.
- RED: contrato anterior recusava browser_checks; primeiro Docker real fez build
  e HTML, mas falhou ao iniciar navegador. TMPDIR agora aponta ao tmpfs privado.
- Revisão: prazo único antes de import/launch, orçamento restante para abertura,
  expiração verificada entre cenários e antes de retornar, inclusive após close.
  Revisão final sem outros bloqueios concretos. Imagem final refeita por snapshot.
- Verificação: 285 pytest/7 skipped com Docker; após guarda final, 14 testes
  navegador repetidos/passaram; 22 E2E, lint, typecheck, build e smoke Hermes
  cinco chamadas aprovados. Smoke: 4 HTML, 1 browser, zero falhas.
- Commits 0a8a050 e 2cd1314 enviados; PR rascunho #8 sobre codex/nextjs-sandbox.
  Sem merge/deploy nem mudança de permissões. Documentação fecha esta etapa.
