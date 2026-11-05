# V0.6.1 — auditoria inicial (histórico)

Data: 05/11/2026. Branch `codex/ai-team/v06-agentes-executores`, PR #10.
Base preservada: `fb6407b4370dab98983d5bd0a60f9149bd8c3b6b`, com 23 commits
V0.6 sobre `1f02d09bd61b7f9f13ce7fa4efe2c8cbacee016a`.

Ao término desta fase ainda faltavam Hermes completo e validação multifile.
O resultado posterior está em [homologação final](v061-final-homologation.md):
seis etapas reais aprovadas e pré-publicação validada dentro do novo limite
autorizado. A falha abaixo permanece preservada. Nenhum merge, deploy ou
ampliação de permissões foi realizado.

## Revisão e correções

Revisão do diff dos 49 arquivos originais, código relacionado, testes e contratos.
Um segundo revisor somente leitura examinou backend e correções. Isso não é
uma certificação de segurança nem substitui revisão humana dos arquivos gerados.

| Problema confirmado | Correção e evidência |
|---|---|
| Histórico limitava antes de ordenar, ocultando tarefas recentes | Ordenação SQL por data/id antes do LIMIT; regressão com 101 execuções |
| Snapshot e alterações excediam juntos 48 KiB após a aprovação | Validação agregada em ExecutionBundle, também na fronteira do sandbox |
| Resposta inválida perdia tokens já consumidos | Registro transacional, idempotente por lease/etapa, antes da validação do conteúdo; cancelamento continua revogado |
| Reserva aceitava lease vencida | Admissão exige lease vigente no mesmo UPDATE condicional |
| Redação Hermes podia corromper código sem detecção antecipada | Parse AST dos arquivos propostos, sem execução no host; snapshot quebrado continua legível para reparo |
| HTTP 429 virava erro genérico | Diagnóstico fixo de cota, sem copiar resposta privada e sem retry |
| Escrita remota verificava principalmente ref/PR | Readback do pai, árvore, diff e SHA Git de cada conteúdo UTF-8 antes de criar ref; caminhos extras e bytes divergentes bloqueados |
| Testes Docker assumiam inicialização em dois segundos | Prazo de dez segundos para casos finitos; loop infinito mantém dois, produção mantém trinta |

Regressões adicionais: QA reprovado impede aprovação final/publicação; entrega
`started` recupera como `uncertain`, sem readmissão; arquivo proposto sem mudança
também é relido pelo SHA imutável. Concorrência de consumo é testada no PostgreSQL
real, incluindo manutenção do cancelamento e um único evento de consumo.

### Inventário dos 49 arquivos originais

Segurança e executor: `services/api/ai_team/agents.py`, `execution_limits.py`,
`hermes_journal.py`, `main.py`, `models.py`, `office.py`, `orchestration.py`,
`python_sandbox.py`, `repository_delivery.py`, `repository_policy.py`,
`repository_routes.py`, `repository_runs.py`, `repository_snapshot.py`,
`repository_workspace.py`, `schemas.py`, `worker.py`, `workflow.py`.

Testes Python: `services/api/tests/test_execution_limits.py`, `test_office.py`,
`test_postgres_integration.py`, `test_python_sandbox.py`,
`test_repository_delivery.py`, `test_repository_flow.py`, `test_repository_policy.py`,
`test_repository_routes.py`, `test_repository_snapshot.py`, `test_repository_workspace.py`.

Web: `apps/web/app/api/control/[...path]/route.ts`,
`apps/web/components/creation-dialog.tsx`, `dashboard.tsx`, `pixel-office.tsx`,
`repository-panel.tsx`, `run-panel.tsx`, `apps/web/lib/api.ts`,
`apps/web/e2e/repository.spec.ts`, `workspace.spec.ts`.

Configuração e documentação: `.gitignore`, `README.md`, `docs/skills.md`,
`docs/v06-executors.md`, `package.json`, `package-lock.json`,
`apps/web/eslint.config.mjs`, `next.config.ts`, `package.json`,
`playwright.config.ts`, `tsconfig.json`, `services/api/pyproject.toml`,
`tools/smoke_repository.py`.

Foram conferidos: autenticação de proprietário e Origin/CSRF no backend/BFF,
allowlist do ai-team e caminhos/SHA, ausência de shell vindo de modelos,
aprovações e replay, credenciais próprias, isolamento Git/Docker, journal,
estados do escritório e preservação dos fluxos anteriores. Nenhuma permissão
da App foi ampliada. Conteúdo de modelos, skills e repositórios permanece dado
não confiável; a autorização é aplicada novamente no executor.

## Hermes real: falha preservada

Execução `17de7796-2232-4059-971d-6c4d433a8af8`, snapshot real no commit
`4f48590`, GitHub App própria, workspace Git isolado e Docker real.

- CEO, PESQUISADOR, DEV, DESIGNER e QA concluíram inferências oficiais.
- Consumo informado dessas cinco etapas: 16.180 entrada + 5.714 saída = **21.894 tokens**.
- A sexta admissão terminou `failed`: o provedor reportou HTTP 429 e limite da
  assinatura. Não houve repetição automática pelo AI TEAM. A resposta mencionou
  três tentativas internas do provedor; seis admissões não significam seis
  requisições HTTP internas. O consumo dessa falha não foi confirmado além dos
  zeros retornados pelo Hermes; não é apresentado como custo comprovadamente zero.
- Os testes gerados rodaram no Docker e **falharam**: a constante `MAX_TOKENS`
  foi alterada para `***` no conteúdo recebido, causando SyntaxError. Isso foi
  encontrado na evidência, não tratado como sucesso.
- A compatibilidade de constantes anotadas foi verificada contra o redator
  oficial do contêiner, usando JSON aninhado sintético e nenhuma inferência.
  O novo pedido usa constantes tipadas; isso **ainda não homologa** outra execução.
- Evidência privada: `artifacts/v06-repository-hermes-smoke.json` e banco
  `.data/v06-hermes-smoke-*.db`. Permanecem ignorados pelo Git.

Não houve publicação do resultado inválido. O histórico não foi apagado nem
reclassificado. A execução Codex anterior aprovada é documentada separadamente
em [V0.6](v06-executors.md); não conta como Hermes homologado.

## Reprodução e limites

```powershell
# Sem inferência paga:
.venv/Scripts/python.exe -m pytest services/api/tests -q
.venv/Scripts/python.exe -m ruff check services/api tools/smoke_repository.py
$env:AI_TEAM_SANDBOX_TESTS='1'
.venv/Scripts/python.exe -m pytest services/api/tests/test_python_sandbox.py -q
Remove-Item Env:AI_TEAM_SANDBOX_TESTS
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

Nova homologação requer consentimento adicional às seis admissões já usadas,
cota disponível e HEAD enviado ao GitHub. Um teto de 78.000 para a nova tarefa
deixa o total informado abaixo de 100 mil, incluindo a tentativa anterior:

```powershell
# Somente após a nova autorização; não publica:
.venv/Scripts/python.exe tools/smoke_repository.py --real --executor hermes --max-tokens 78000
```

O orçamento limita admissão, não interrompe tokens de uma resposta em andamento.
Essa resposta pode ultrapassar o teto. Não há API paga contratada, fallback
de provedor automático ou preço financeiro inventado.

Docker: imagem por digest, sem rede/mounts/credenciais, usuário não privilegiado,
capabilities removidas, raiz read-only, 1 CPU, 256 MiB, 64 processos, tmpfs 16 MiB,
watchdog e limpeza por nome/label. Testes gerados não são uma atestação inviolável
contra código malicioso: revisão humana continua obrigatória. A proteção Hermes
de segredos permanece ligada; não foi feita modificação no runtime oficial.

## Verificações e próximos bloqueios

- pytest completo final: **333 passed, 24 skipped** em 85,88 s. Opt-ins de Docker
  e PostgreSQL são executados separadamente e não são contabilizados como passes
  nessa rodada padrão.
- 27 testes Docker reais aprovados, incluindo timeout, cancelamento, isolamento,
  limite de saída, suíte vazia, saída prematura e morte do controlador.
- 27 E2E aprovados, incluindo escritório ligado a checkpoints persistidos,
  `/ceo`, criação/cancelamento de tarefa de repositório mobile, login e CSRF.
  Fixtures de provedor em E2E são testes de interface, não homologação de inferência.
- Ruff, ESLint, typecheck e build de produção aprovados localmente.
- Smoke Windows nativo: API `/health` 200, painel `/login` 200 e
  `/repository-runs` sem sessão 401. Serviços existentes preservados.
- PostgreSQL real: 9 testes aprovados no CI, incluindo concorrência de consumo:
  [run 42009758321](https://github.com/igorcastro1010/ai-team/actions/runs/42009758321).
- Runtime Hermes oficial e startup Windows têm verificações CI próprias; boot,
  perfis e autenticação de transporte não substituem inferência de seis etapas.

Pendente: nova execução Hermes aprovada; revisão do novo diff e digest; autorização
explícita para publicar aquele conteúdo; commit/ref/PR reais multifile e verificação
remota. A branch de origem deve continuar no SHA aprovado até a publicação.
Se avançar, o executor recusa a entrega e exige nova revisão. Nunca merge/deploy.

Os commits novos e seus SHAs podem ser reproduzidos com:
`git log fb6407b..HEAD --format='%H %s'`. Os 23 originais foram preservados.
Esta etapa registra **18 novos commits, 41 acumulados** desde a base da V0.6.
O registro completo de SHAs também é exportado para
`artifacts/v061-commits.json` (evidência local, ignorada pelo Git).
