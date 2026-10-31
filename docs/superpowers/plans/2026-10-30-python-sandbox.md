# Python sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** DEV gera arquivos Python, QA gera testes e o executor roda unittest em Docker após aprovação exata dos artefatos.

**Architecture:** Reutilizar Run, etapas LangGraph, worker, sessões e escritório existentes. Novo escopo `python_code` com artefatos e decisão persistidos no JSON das etapas, sem alterar tabelas. Runner em módulo separado, sem credenciais nem mounts no contêiner.

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph, Pydantic, Docker Linux, Python 3.12 stdlib, Next.js.

**Spec:** docs/superpowers/specs/2026-10-30-code-execution-draft.md

## Global Constraints

- Preservar pedidos `draft_only`, banco e usuário Windows.
- Aprovação por projeto/run, etapa 4 e hash SHA-256 de todos os arquivos.
- Sem ferramentas Hermes, comandos do modelo, instalação de dependências, shell, mount do host, GitHub ou deploy.
- Docker Linux: imagem oficial fixada por digest, uid 65532, rede none, raiz read-only, cap-drop ALL, no-new-privileges, 1 CPU, 256 MiB, 64 PIDs, 30 s e saída 32 KiB.
- Workspace em tmpfs de 16 MiB; no máximo 12 arquivos e 48 KiB UTF-8, caminhos Python restritos sem traversal/links.

## Review Focus

- Aprovação antiga ou hash divergente deve bloquear antes de qualquer processo.
- Cancelamento e perda de lease devem encerrar somente o contêiner desta tarefa.
- Saída ilimitada, timeout, Docker ausente e zero testes nunca equivalem a sucesso.
- Artefatos inválidos e testes que substituem arquivos DEV devem ser recusados.
- Tela mostra saída como texto e diferencia testes falhos de entrega bem-sucedida.

### Task 1: Contrato e runner

**Files:** Create `services/api/ai_team/code_artifacts.py`, `services/api/ai_team/python_sandbox.py`, tests `test_python_sandbox.py`.
**Interfaces:** `bundle_for_steps(steps) -> CodeBundle`; `bundle.digest`; `PythonSandbox.run(bundle, on_tick) -> dict`.
- [x] Testar validação de nomes/tamanhos/duplicatas, hash canônico, comando fixo e limites.
- [x] Implementar runner sem mounts, stdin JSON, cleanup em finally e saída limitada.
- [x] Validar em Docker real: sucesso, falha, rede/host bloqueados, timeout e excesso de saída.
- [x] Commit convencional dos arquivos explícitos.

### Task 2: Workflow e autorização

**Files:** Modify `orchestration.py`, `workflow.py`, `worker.py`, `run_routes.py`; create `test_code_workflow.py`.
**Interfaces:** `RunInput.scope`; `Decision.artifact_digest`; `WorkflowStore.create(..., scope=...)`; `Worker(..., sandbox=...)`.
- [x] Testar legado, geração DEV/QA, pausa obrigatória em etapa 4 mesmo automática, autorização exata, rejeição/replay/cancelamento e persistência.
- [x] Adaptar instruções por escopo; arquivos em JSON dentro do deliverable; ferramentas continuam bloqueadas.
- [x] Revalidar bundle aprovado no worker, persistir resultado da suíte antes do relatório CEO e não repetir execução incerta após perda do worker.
- [x] Expor download autenticado de arquivos revisados como ZIP gerado em memória.
- [x] Commit após testes direcionados.

### Task 3: Painel e evidência

**Files:** Modify `apps/web/components/run-panel.tsx`, `apps/web/lib/api.ts`; add E2E na suíte existente; docs instalação e limites.
- [x] Ler guia Next local e skills UI/React/Playwright.
- [x] Oferecer escopo Python com explicação curta, artefatos revisáveis, aprovação por hash, download e relatório de testes.
- [x] Aproveitar estados reais existentes do escritório; representar QA durante a suíte e CEO no relatório.
- [x] Rodar pytest, lint, typecheck, build, E2E e smoke real limitado; revisão independente final.
- [x] Commit/push somente etapas validadas; sem deploy ou merge em main nesta entrega.

## Ledger

- Escolha: execução inline para economia; revisão independente somente ao final.
- Decisão: arquivos e resultado no JSON de etapas existente, evitando migração e mantendo compatibilidade.
- Decisão: fonte e testes entram por stdin e são gravados dentro de tmpfs; nenhum bind mount é necessário.

- Concluído: 248 pytest passaram (Docker opt-in), 7 PostgreSQL omitidos; 21 E2E, lint, typecheck e build passaram.
- Revisão: corrigidos término prematuro, watchdog/reconciliação e continuidade textual com Docker offline; sem bloqueio restante na releitura.
- Smoke final: cinco chamadas Hermes próprias, seis unittest aprovados, 9.427 tokens de entrada e 1.990 de saída.
- Limites: somente módulos Python novos, sem dependências externas, edição de checkouts ou ampliação GitHub; nenhum merge/deploy.
