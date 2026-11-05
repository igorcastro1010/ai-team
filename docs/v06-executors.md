# V0.6 — execução em repositório autorizado

Plano de implementação incremental na branch `codex/ai-team/v06-agentes-executores`.

## Decisões de escopo

- Reutilizar sessões, fila Run, leases, worker, provedores próprios e sandbox Python.
- Primeiro perfil: Python 3.12/biblioteca padrão e documentação Markdown, até 12 arquivos
  explicitamente autorizados de uma pasta de `igorcastro1010/ai-team`, congelados em SHA.
- CEO → PESQUISADOR → DEV → DESIGNER → QA → CEO. Pesquisa limitada aos arquivos
  autorizados; não representa navegação na internet. Nenhum modelo recebe shell ou tokens.
- Git local por tarefa, sem remotes, hooks, credenciais ou execução do código no host.
- Testes somente no Docker sem rede, 1 CPU, 256 MiB e 30 s. Aprovação do digest antes
  dos testes; resultado, diff e proposta de PR persistidos. Falhas não viram sucesso.
- Aprovação final vinculada a SHA, arquivos e resultado. Nunca merge ou deploy.
- Escritas remotas são uma etapa separada: não confundir proposta persistida com PR publicado.

## Entregas e validação

1. Contratos de caminhos, autorização e artefatos; testes negativos antes da implementação.
2. Snapshot GitHub somente leitura e workspace Git privado com diff verificável.
3. Persistência, seis agentes, checkpoints, aprovação e execução independente dos testes.
4. API autenticada, painel e escritório alimentados por estados persistidos.
5. Recuperação/cancelamento, testes de regressão, homologação com provedor e Docker reais.
6. Documentação e PR de desenvolvimento sem merge/deploy.

Cada entrega terá testes direcionados, commit convencional e push. A release depende de
pytest, lint, typecheck, build e E2E; mocks cobrem contratos, não homologação do provedor.

## Como usar

1. Execute `tools/start.ps1`, entre no painel e crie um projeto. Escolha manual,
   supervisionado ou automático ao cadastrar o projeto.
2. Em **Conversa com CEO → Executor de repositório**, informe a branch de origem e
   seu SHA de 40 caracteres, a pasta e os nomes permitidos para leitura e escrita.
   Um arquivo existente precisa estar na leitura antes de poder ser sobrescrito.
3. Autorize pelo menos uma fonte `.py`, um `test_*.py` e um `.md` para os três
   especialistas. Até 12 nomes simples na mesma pasta; não há exclusão de arquivos.
4. Escolha o orçamento de admissão (padrão 50 mil; até 100 mil tokens), o provedor
   próprio e o consentimento. O worker fará somente leitura na App durante a geração.
5. Revise o plano conforme o modo. Depois do QA gerar os testes, confira o diff,
   baixe o ZIP e autorize o digest exato para execução no Docker.
6. Confira a saída real e o relatório final. Testes com falha impedem aprovação da
   entrega. Aprovar a entrega **não publica**. A opção separada de publicação autoriza
   uma branch `codex/ai-team/task-<UUID>` e um PR rascunho na branch de origem.

### Persistência e atualização

Nova tabela `repository_jobs`: FK/PK `run_id` e checkpoint JSON. Os registros anteriores
continuam nas tabelas existentes. Desenvolvimento usa a inicialização idempotente da
API; para atualização de PostgreSQL privado execute `python -m ai_team.cli init-db`
como identidade de migração antes de iniciar API/worker novos. Faça backup privado
antes de atualizar. Não é uma migração de infraestrutura ou publicação em produção.

Workspaces ficam em `.data/task-workspaces/<UUID>`, com Git local sem remoto, identidade
do executor, configurações globais ignoradas e hooks desativados. Código nunca é
importado no host. Não existe clone completo: o workspace contém apenas o snapshot
explicitamente autorizado. Na entrega, a árvore GitHub parte da árvore completa do SHA
original e troca somente os arquivos permitidos, preservando os demais.

### Recuperação, limites e confiança

- Cada etapa tem lease persistente de 180 s. Provedores mantêm seu timeout próprio de
  até 120 s; Git local tem timeout de 10 s. Expiração/cancelamento impede novos checkpoints.
- No máximo seis chamadas. A margem de 16 mil tokens impede novas admissões quando
  o orçamento restante está baixo. **Não é um teto de faturamento do provedor**:
  contexto inicial e resposta em andamento podem ultrapassar a estimativa antes de o
  consumo chegar ao worker. Um excesso encerra a tarefa; não há aumento automático.
  O CLI oficial não expõe um `max_output_tokens` no schema de configuração consultado;
  não foi inventado um parâmetro para prometer um teto inexistente. Para um teto financeiro
  rígido, é necessário um provedor com limite de gastos efetivamente aplicado por ele.
- Toda inferência custa a cota da conta própria, inclusive chamadas que depois falhem
  na validação. Custos em reais/dólares permanecem desconhecidos quando o provedor não
  os informa; a aplicação não inventa preços nem trata token como moeda.
- Docker usa imagem Python por digest, sem rede, sem mounts do host, sem credenciais,
  usuário não privilegiado, filesystem raiz read-only, 1 CPU, 256 MiB, 64 processos,
  tmpfs de 16 MiB e watchdog de 30 s. Somente o comando fixo unittest é executado.
- `passed` é o resultado da suíte gerada executada, **não uma prova de correção ou uma
  atestação inviolável de código malicioso**. Testes Python arbitrários podem mentir ou
  adulterar seu próprio processo. Revisão humana dos testes/diff é indispensável; o
  isolamento protege o host e as credenciais, não garante honestidade de uma suíte.
- Após interrupção, o worker verifica os containers por nome UUID e label. Sem confirmar
  a limpeza, não admite novos jobs de código. Uma chamada incerta não é repetida.
- Publicação grava `started` antes das escritas. Falha após possível mutação vira
  `uncertain`, inclusive na recuperação. Confira GitHub antes de criar outra tarefa;
  não há retry automático, force push, merge, deploy ou exclusão de branch.
- Retry de inferência exige nova tarefa/consentimento; não há retomada automática de
  uma chamada interrompida. Artefatos e logs anteriores ficam disponíveis para revisão.

## Homologação e estado da entrega

Comando reproduzível, somente após consentir consumo real:

```powershell
.venv/Scripts/python.exe tools/smoke_repository.py --real --max-tokens 100000
```

O script cria banco de teste exclusivo em `.data`, usa sessão autenticada e worker,
lê `execution_limits.py` da branch/SHA enviados ao GitHub, solicita uma melhoria real,
aprova os artefatos somente na tarefa descartável, executa Docker e exige proposta de
PR com evidência. Não publica nada. Evidência local em `artifacts/v06-repository-smoke.json`;
nenhum desses arquivos vai para Git.

Em 04/11/2026, a primeira execução real `eed98a94-436a-4dbb-811b-af87d7809b0e`
concluiu CEO, PESQUISADOR, DEV e DESIGNER. A etapa seguinte esgotou o orçamento de
50 mil e a tarefa encerrou com falha; não foi declarada homologação completa. A nova
execução aguarda autorização do proprietário para o orçamento de até 100 mil.
O journal registrou cinco chamadas e 63.840 tokens (60.262 de entrada e 3.578 de saída):
o excesso da resposta em andamento foi detectado depois de seu término. A margem de
admissão foi adicionada após essa evidência, sem apagar ou reclassificar a falha.

Publicação remota da nova árvore multifile tem testes de contrato; não foi homologada
ao vivo. A conexão/leitura da GitHub App foi verificada no repositório real. O fluxo
novo com Hermes reutiliza o adaptador e journal existentes, mas ainda não teve
homologação real específica de seis etapas. Next.js/Chromium anteriores são preservados;
edição de repositórios Next.js e DESIGNER de TSX ficam para extensão do perfil.

Verificação local final em 04/11/2026:

- pytest completo: **310 passed, 23 skipped** (opt-ins de sandbox/PostgreSQL).
- Sandbox Python com Docker real habilitado: **27 passed**, incluindo isolamento,
  timeout, cancelamento, watchdog e regressão do protocolo de resultado.
- Playwright completo: **27 passed**, incluindo autorização de repositório mobile e
  regressões do CEO, escritório, autenticação, GitHub e Next.js/Chromium.
- Ruff, ESLint, TypeScript e build de produção: aprovados.
- Novo teste de checkpoint/digest PostgreSQL incluído na suíte opt-in (oito testes);
  execução real específica da revisão depende do job PostgreSQL do PR.

Essas verificações não substituem a homologação real das seis inferências. A primeira
tentativa falhou e permanece registrada. Nenhum teste mockado é apresentado como
homologação de Codex, Hermes ou escrita remota.

### Referências oficiais consultadas

- [GitHub Git Trees](https://docs.github.com/en/rest/git/trees#create-a-tree),
  commits, refs e pull requests: árvore com `base_tree`, branch nova e PR rascunho.
- [Codex SDK](https://developers.openai.com/codex/sdk/) e
  [schema oficial de configuração](https://developers.openai.com/codex/config-schema.json).
- [Hermes](https://hermes-agent.nousresearch.com/docs/) e
  [skill oficial NousResearch](https://github.com/NousResearch/hermes-agent/tree/main/skills/autonomous-ai-agents/hermes-agent).
