# V0.7 Memory and Token Optimizer Implementation Plan

> **For agentic workers:** use TDD and execute the tasks below with isolated file ownership; validate and commit each logical delivery.

**Goal:** project-scoped persistent knowledge, supervised Issues and measurable context optimization without real inference.

**Architecture:** reuse SQLAlchemy/private schema, FastAPI owner authentication/CSRF, separate workers and the existing GitHub approval queue. Notes are versioned in SQL; a configurable local Obsidian Markdown vault is an optional mirror/import source. Lexical retrieval and deterministic summaries require no inference. Provider context adapters preserve mandatory instructions, request, artifacts and approval data. Graphify is an optional local graph.json interchange, never an invented service.

**Tech Stack:** existing Next.js/React, Python/FastAPI, SQLAlchemy, LangGraph, pytest, Playwright.

**Spec:** user's V0.7 request in this chat; decisions below are reversible implementation choices under the authorized autonomy.

## Global constraints

- Work only on codex/ai-team/v07-memoria-optimizer, based on main 8686559; preserve all V0.6.1 history.
- No real model calls, new permissions, remote generated content publication, merge or deploy.
- All API operations authenticated; writes require existing same-origin protection.
- Project IDs are validated; vault paths never supplied by models, relative Markdown only, no links/junction escapes, credentials or executable Markdown.
- Estimates and lexical context reduction are explicitly distinct from provider-measured savings, which remain unavailable without authorized paired inference.
- Remote Issues use immutable digest approvals, deduplication and the existing selected-repository GitHub App; uncertain mutations are never replayed automatically.

## Design and alternatives

Use bounded SQL lexical retrieval with versioned Markdown instead of adding an embedding provider (new credentials/costs) or a global shared unscoped index (project isolation risk). Keep budgets and optimizer records in new tables, avoiding in-place changes to existing tables. Use a detached Graphify adapter with validated node/link imports/exports and local CLI verification; do not execute Graphify semantic extraction or hooks. Obsidian itself is optional: plain Markdown, frontmatter and wikilinks work without an app/plugin.

## Review focus

1. Windows drive/UNC/device paths, symlinks/junctions and concurrent vault edits cannot escape or silently overwrite.
2. Memory changes/removals and permissions changes invalidate retrieval cache across process restart.
3. Untrusted memories never replace requirements, role instructions, approvals or code required by QA.
4. Concurrent issue proposals and uncertain GitHub writes cannot produce automatic duplicate publication.
5. Budget admission is persistent and conservative; in-flight usage may exceed estimates and must remain visible.

## Tasks

### 1. Versioned memory and vault

Files: memory_models.py, memory_store.py, memory_vault.py, memory_routes.py; tests/test_memory*.py. Register tables/router and optional server vault setting.
Interfaces: MemoryStore(database).put(project_id, title, content, source, actor), search(project_id, query, limit), snapshot(project_id); Vault(root).read/write(project_id, relative_path, content).
- [ ] Tests first: revision/dedup, restart, scope, credentials, traversal/junction and size bounds.
- [ ] Implement bounded storage, deterministic chunks, version history, audit and incremental Markdown sync.
- [ ] Run focused pytest and Ruff, inspect exact staged files, commit and push.

### 2. Context optimizer and budgets

Files: token_optimizer.py, optimizer_models.py, optimizer_routes.py, context integration in orchestration.py/repository_runs.py/worker.py; tests/test_token_optimizer.py.
Interfaces: deterministic optimize_context(context, memories, budget); persistent optimizer service keyed by project/agent/run/stage/content/permission version. Never compact request, security instructions, approvals, snapshots or executable artifacts. Record estimated context sizes separately from measured provider input/output.
- [ ] Test irrelevant/duplicate removal, mandatory preservation, fallback, cache invalidation and per-agent/task/project admission.
- [ ] Implement without protocol changes; retrieve memory before all five specialist roles.
- [ ] Verify focused suites and commit/push independent increments.

### 3. Graph relationships and Graphify

Files: knowledge_graph.py and tests/test_knowledge_graph.py, local evidence tool.
- [ ] Test project-scoped nodes/edges, bounded validated Graphify node-link JSON and provenance.
- [ ] Implement native relations for notes/tasks/agents/decisions/issues/commits/PRs; optional Graphify interchange.
- [ ] Verify real installed CLI offline without inference; record limitations, commit/push.

### 4. Supervised Issues

Files: issue_store.py, issue_routes.py, existing GitHub client/queue, tests/test_issue*.py.
- [ ] Test persistent request dedup, task/subtask links, reviewed digest, remote status sync, no unauthorized writes and public authorized ai-team identity.
- [ ] Reuse queue approvals and fixed REST endpoints; read-only real validation when credentials exist; no live Issue mutation without content approval.
- [ ] Commit/push each validated logical delivery.

### 5. Integrated panel

Files: knowledge-panel.tsx, knowledge.css, navigation/dashboard additions, E2E.
- [ ] E2E first for memory create/search/history, scoped Issues and optimizer budget/preview; authentication, mobile overflow and keyboard navigation.
- [ ] Preserve office, use existing Portuguese/dark visual language, honest estimated/measured indicators.
- [ ] Lint/typecheck/E2E, commit/push.

### 6. Validation and release review

- [ ] Run full Python, real Docker opt-ins, PostgreSQL, Playwright, lint/typecheck/build and CI without inference.
- [ ] Add reproducible local paired-context benchmark (no provider savings claim), restart and external-read evidence.
- [ ] Update README/docs/skills/version, independent security review, fix verified issues with regressions.
- [ ] Push and create review PR; report exact SHAs, checks, external gaps and zero real inference admissions.

## Progress

- Base verified: V0.6.1 and PR #10 merged; clean checkout at start. Graphify installed; CLI supports query/export obsidian and graph.json. Find Skills located kepano/obsidian-skills@obsidian-markdown; source reviewed read-only, no installation.
- Tasks 1–5 implemented in independent commits: memory/revisions/chunks, protected vault, optimizer/budgets, Graphify interchange, Issues queue and responsive /memoria panel.
- Task 6: full Python 418 passed/28 skipped before final two restart/automatic retrieval tests (both green); Docker real 27 passed; E2E29 passed plus focused filter regressions; lint/typecheck/build green. Real PostgreSQL12 passed in CI; real own GitHub App read Issue1; real Graphify0.9.93 offline query/export passed.
- Review rulings: preserve all mandatory previous context; optimize explicitly optional sections and retrieved memory only. Byte reduction is not measured provider savings. Unknown provider usage retains reservations. Exported-note mirror conflicts require review. Remote Issue publication and real model comparison remain outside authorization; final independent review pending.
- All commits are on the V0.7 branch, PR11 draft until final checks. Main untouched, zero real inference admissions, no merge/deploy or permission changes.
