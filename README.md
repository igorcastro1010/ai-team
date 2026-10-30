# AI TEAM

Sala de operações em português para projetos, tarefas e agentes de IA. Plataforma independente para navegador no Windows e futura hospedagem Web. **V0.5: Codex próprio, propostas GitHub, consultas Vercel, recorrências e relatórios paginados.** A App própria cria branches, commits de documentos, issues e PRs somente no ai-team. Sem merge ou deploy.

## Hermes e escritório virtual

Integração adicional com o **Hermes Agent oficial**, serviço independente via
Docker Compose, API privada autenticada e executor escolhido por solicitação.
Codex continua padrão; tarefas antigas e agendas não mudam de provedor.
O escritório em `/escritorio` usa pixel art original, sete mesas e detalhes de
histórico/resultados. Só anima execução persistida com lease e worker válidos;
papéis ainda não provisionados são identificados.

| Fase | Entrega e limite atual |
|---|---|
| 1 · Hermes | Adaptador Runs, journal, diagnóstico e Compose; contêiner oficial, autenticação e persistência homologados em CI; inferência real aguarda provedor |
| 2 · Equipe | Sete perfis provisionados e reconhecidos pelo runtime oficial em CI; Bot Mode e subagentes reais ainda não homologados |
| 3 · Escritório | Interface responsiva ligada ao workflow existente, atualização a cada 5s, estados e resultados; não representa bots nativos sem configuração |
| 4 · Telegram | Guia do gateway oficial, allowlist e pairing; token/usuário e mensagens reais pendentes |
| 5 · Desenvolvimento | Codex e GitHub existentes preservados; execução de código/testes arbitrários continua bloqueada |
| 6 · Automações | Agendas existentes preservadas; monitor separado com leases/backoff, consumo reportado e interrupção com confirmação; inventário e pausa de jobs nativos, sem criação/retomada pelo painel |
| 7 · Produção | Compatibilidade PostgreSQL real validada em CI; arquitetura e critérios documentados; nenhum deploy ou infraestrutura paga contratada |

Comece por [configuração Hermes](docs/hermes-setup.md), [auditoria](docs/hermes-audit.md)
e [configuração das próximas fases](docs/hermes-next-phases.md). Segredos ficam no
servidor; não envie tokens pelo chat. O Compose usa volumes próprios, sem importar
automaticamente o banco Windows. O modo Hermes inicial é **textual, sem ferramentas**;
shell, delegação nativa, merge e produção exigem revisão e homologação próprias.

Veja também [histórico e cancelamento remoto](docs/hermes-operations.md) e
[homologação do runtime oficial em CI](docs/hermes-runtime-ci.md).
Agendamentos Hermes: [inventário e pausa confirmada](docs/hermes-jobs.md).
Compatibilidade de banco: [PostgreSQL real no CI](docs/postgres-ci.md).

## O que funciona
- Proprietário único, senha Argon2, sessão HTTP-only expirada em 12h, logout revogável e limite de login persistente.
- Cadastro de projetos, preferência de autonomia e tarefas por agente.
- Quadro com transições validadas, armazenamento persistente e histórico de auditoria.
- Visão geral, papéis dos quatro agentes, status das integrações e relatório JSON.
- Interface responsiva, formulários acessíveis e bloqueio de acesso sem login.
- Conversa por solicitações com o CEO: planejamento, delegação de tarefas locais, DEV, DESIGNER, QA e consolidação.
- Worker separado, checkpoints SQL por etapa, status, cancelamento e artefatos textuais persistentes.
- Agendamentos textuais com consentimento, até cinco ocorrências, validade de 30 dias e scheduler separado.
- Relatórios com totais completos do banco, histórico paginado e exportação JSON da página.
- Modos manual, supervisionado e automático restrito ao escopo textual consentido. Decisões vinculadas à etapa, protegidas contra replay.

## Windows: instalar e abrir
Requisitos: Git, Node.js 22 ou 24 LTS e [uv](https://docs.astral.sh/uv/). Python 3.12 será localizado/instalado pelo uv.

```powershell
git clone https://github.com/igorcastro1010/ai-team.git
cd ai-team
.\tools\setup.ps1
.\tools\start.ps1
```

O instalador solicita uma senha com pelo menos 12 caracteres, sem exibí-la ou gravá-la em claro. Depois abra [localhost:3000](http://localhost:3000), usuário `admin`. Para outro nome: `ai-team create-owner --username NOME` no ambiente virtual, antes do cadastro inicial. Não existe senha padrão nem registro público.

API escuta apenas em 127.0.0.1:8000; painel em 127.0.0.1:3000. O script mantém API, worker e scheduler ocultos e encerra os processos que iniciou ao fechar o painel. O modo de desenvolvimento não é uma instalação de produção. Não há EXE ou serviço Windows instalado.

### Instalação manual / Linux
```sh
uv venv --python 3.12 .venv
uv pip sync --python .venv/Scripts/python.exe services/api/requirements.lock
uv pip install --python .venv/Scripts/python.exe --no-deps -e services/api
npm ci
.venv/Scripts/python.exe -m ai_team.cli create-owner --username admin
.venv/Scripts/python.exe -m uvicorn ai_team.main:app --host 127.0.0.1 --port 8000
# Em outro terminal:
npm run dev
# Em um terceiro terminal, após login próprio do Codex:
.venv/Scripts/python.exe -m ai_team.worker
# Em um quarto terminal:
.venv/Scripts/python.exe -m ai_team.scheduler
```
No Linux substitua `.venv/Scripts/python.exe` por `.venv/bin/python`. Se houver restrição local a scripts PowerShell, execute os comandos manualmente; não é necessário alterar a política do sistema.

## Configuração
Copie `.env.example` para `.env` na raiz somente se precisar mudar os padrões. Arquivos `.env` são ignorados. O painel usa `AI_TEAM_API_URL` somente no servidor; em hospedagem configure-a no ambiente da Vercel. A API lê `AI_TEAM_PUBLIC_ORIGIN`, `AI_TEAM_ENVIRONMENT`, `AI_TEAM_DATABASE_URL` e `AI_TEAM_SESSION_TTL_SECONDS`.

SQLite local: `.data/ai-team.db`. Não apague este arquivo para atualizar. Backup com o serviço parado; manter também eventuais arquivos WAL até o fechamento das conexões. Nunca versionar o banco ou logs locais.

## PostgreSQL / Supabase
Use `AI_TEAM_DATABASE_URL=postgresql+psycopg://.../postgres?sslmode=require` no servidor privado. Inicialize explicitamente com `ai-team init-db`, depois cadastre o proprietário. As tabelas ficam no schema `ai_team`, sem permissão de PUBLIC. Não adicione esse schema aos expostos pelo PostgREST/Supabase Data API. O painel conversa exclusivamente com FastAPI; não recebe service_role ou senha do banco.

V0.2 adiciona `runs` e `worker_heartbeats`; V0.3 adiciona `github_actions` e `github_verification`; V0.4 adiciona `provider_observations`; V0.5 adiciona `schedules` e `schedule_occurrences`, sem remover dados existentes. No desenvolvimento, a API/worker cria as tabelas ausentes ao iniciar. Em produção execute `ai-team init-db` explicitamente antes dos serviços. Ainda não há migrações gerais de alteração de colunas. PostgreSQL/Supabase precisa de homologação real antes de hospedagem. Mudar DATABASE_URL não copia o SQLite: faça migração de dados revisada. Não presumir RLS multiusuário; a instalação é de proprietário único.

## Verificação
```powershell
.\tools\check.ps1
```
Os E2E criam banco e usuário exclusivos de teste, sob `.data/`; não usam o banco real. Chromium pode precisar de `npx playwright install chromium`. Resultados e capturas ficam ignorados pelo Git. O comando de build é separado do servidor dev; não rode os dois simultaneamente sobre a mesma pasta `.next`.

## Estrutura
```text
apps/web/           painel Next.js e E2E
services/api/       API, autenticação, banco e testes
.agents/skills/     skills locais de desenvolvimento
tools/              instalação, execução e verificação Windows
docs/               arquitetura, pesquisa, marcos e evidências
```

## Evolução e limites
- V0.1: base local funcional.
- V0.2: entregue — CEO, especialistas, LangGraph, fila, propostas e revisão textual por worker.
- V0.3: entregue — GitHub App própria e propostas revisadas de branch/documento/issue/PR, somente no ai-team.
- V0.4: entregue — Codex oficial preservado e consulta Vercel própria ao projeto autorizado, sem publicação.
- V0.5: entregue — recorrências textuais limitadas, scheduler separado e relatórios paginados.
- V1.0: homologação, segurança de produção e publicação autorizada.

Nenhum deploy é feito pela plataforma nesta versão. A autorização automática vale somente para elaboração textual dentro da solicitação consentida. Não há leitura de outros projetos, execução de shell pelo agente, exclusões, pagamentos ou acesso à sessão local do Codex. Integrações futuras aparecem como planejadas. Veja [desenho](docs/superpowers/specs/2026-10-27-ai-team-design.md), [skills](docs/skills.md) e [releases](docs/releases.md).

### Preparação do executor Codex
O usuário escolheu login próprio do Codex. `tools/login-codex.ps1` inicia o fluxo oficial por código de dispositivo em contexto separado (`%LOCALAPPDATA%/AI-Team/codex`). As credenciais usam obrigatoriamente o cofre do sistema, sem fallback para arquivo de tokens. A sessão e o diretório do Desktop não são lidos ou copiados. É necessário um executável nativo oficial `codex` no PATH; a versão encontrada e os parâmetros devem ser homologados antes de executar agentes. No ambiente de desenvolvimento atual, o binário oficial foi detectado.

```powershell
.\tools\login-codex.ps1
.venv\Scripts\python.exe -m ai_team.codex_access status
```

Após login, inicie o worker com `tools/start.ps1` (junto do painel) ou `tools/worker.ps1` (isolado). O painel indica quando o worker está online; pedidos ficam persistidos na fila enquanto ele está desligado. Não envie códigos de acesso, tokens ou arquivos de autenticação a outras pessoas.

## Como executar uma solicitação
1. Crie um projeto e selecione o modo de autonomia.
2. Em **Conversa com CEO**, escolha o projeto, descreva o objetivo e marque o consentimento de envio ao Codex. Não inclua dados sensíveis.
3. O CEO gera o plano e propõe tarefas. Em modo supervisionado, revise o artefato e autorize a continuação em **Aprovações**. Em modo manual, cada próxima etapa depende de sua decisão.
4. DEV e DESIGNER produzem propostas, QA faz revisão documental, CEO consolida. Os resultados ficam em **Execuções** e na conversa. Tarefas propostas não são marcadas como concluídas automaticamente.

Limites por solicitação: 5 chamadas, 120 segundos por chamada, contexto de pedido até 5.000 caracteres e artefatos limitados. Antes de iniciar outra chamada, o worker verifica o consumo acumulado de 50.000 tokens. Uma chamada em andamento pode ultrapassar esse limiar; não é teto financeiro rígido. Custo monetário permanece indisponível; os tokens exibidos vêm do CLI. Chamadas malsucedidas também podem consumir os limites da conta, mesmo sem relatório de tokens.

Não há repetição automática de chamadas falhas. Queda de worker durante uma etapa deixa a execução incerta; após a lease de 180s, o próximo worker a marca como falha. Cancelamento preserva histórico e interrompe o processo local; uma requisição já enviada ao provedor pode consumir uso até ser encerrada. Somente pedidos bloqueados por falta de configuração podem ser retomados; uma falha exige nova solicitação consentida.

A interface mostra as últimas 200 execuções/eventos. Aprovações são consultadas separadamente, das mais antigas às mais recentes, para não desaparecerem atrás do histórico concluído.

### Homologação real opt-in
```powershell
.venv\Scripts\python.exe tools/smoke_codex.py --real
```
Esse comando consome até cinco chamadas reais, usa um banco temporário exclusivo e um projeto sintético, testa API autenticada + worker em cinco processos separados + decisão de teste e grava evidência em `artifacts/codex-smoke.json` (ignorado no Git). Os testes comuns e o CI usam provedores de teste e não fazem inferência paga. Validado no Windows com o CLI oficial disponível; compatibilidade de outro binário deve ser verificada sem flexibilizar as permissões.

### GitHub App e propostas
O registro está em `tools/setup-github-app.ps1`. Veja [permissões e instalação](docs/github-app-setup.md). A instalação própria foi homologada somente no `ai-team`. No painel **Integrações**, verifique a App, escolha um projeto e registre uma proposta. Revise todo o conteúdo e autorize separadamente; o worker executará uma vez e registrará o resultado.

Branches devem usar `codex/ai-team/<nome>`. Commits desta versão publicam um documento Markdown completo em `docs/agent-output/<nome>.md`, com mensagem convencional e SHA da branch revisada. Para PR, informe também o SHA revisado da branch; a base é main. Não existe merge, exclusão, shell, publicação em produção ou edição de workflows. Os agentes continuam elaborando texto; transferir uma proposta para o formulário GitHub é uma ação manual do proprietário. Código arbitrário e execução de testes de projetos não estão habilitados.

Resultado incerto nunca é repetido automaticamente: confira o recurso no GitHub antes de criar outra proposta. Troca de SHA ou ampliação da instalação bloqueia a execução. Tokens de escrita são temporários, restritos ao ID do ai-team e à permissão da operação. Os resultados preservam links para conferência.

Homologação real opt-in: `.venv\Scripts\python.exe tools/smoke_github.py --real`. Cria branch, documento, issue e PR reais no ai-team, usando API autenticada, banco sintético e quatro workers separados; não faz merge, deploy nem limpeza destrutiva. Evidência fica em `artifacts/github-smoke.json` (ignorado). O CI não faz chamadas reais à App. Não envie chaves no chat.

### V0.4: Vercel própria, somente consultas
Configuração segura: `powershell -NoProfile -File .\tools\setup-vercel.ps1`. Consulte [escopo, cofre e limites](docs/vercel-setup.md). Credencial própria validada e projeto vazio criado com autorização; nenhum deploy realizado. No painel Integrações, use **Consultar Vercel** para registrar o estado e os últimos deploys do ai-team. O cliente só implementa GET e verifica o ID do projeto vinculado.

### Recorrências e relatórios V0.5

Abra **Agendamentos** para autorizar projeto, solicitação, modo, início e frequência. A instalação não cria agendas automaticamente. Veja [limites e execução Windows](docs/schedules.md) e [revisão de segurança](docs/v05-security-review.md). Em **Relatórios**, os totais abrangem todo o banco; o histórico e a exportação JSON representam uma página de até 50 execuções por vez. Prompts e credenciais não são exportados. Não há inferência paga nos testes desta versão.

### Diagnóstico Windows e Hermes

Antes de iniciar, execute `powershell -NoProfile -File .\tools\doctor.ps1`. Para exigir também os pré-requisitos Hermes, acrescente `-RequireHermes`; `-Json` produz um relatório sem segredos. O inicializador verifica portas, versão e prontidão da API antes de abrir o painel. Veja [ativação local e reinício](docs/hermes-local-onboarding.md).
