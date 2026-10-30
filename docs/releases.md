# Entregas e evidências

## Monitor Hermes e jobs nativos — 30/10/2026

Processo independente de reconciliação por GET com leases e backoff persistentes,
heartbeat distinto de atividade dos agentes e integração Windows/Compose.
Painel autenticado com inventário nativo, pausa confirmada por job e evidências
imutáveis resistentes a respostas atrasadas e consultas concorrentes.

Validação: 202 testes Python, 20 E2E, Ruff, ESLint, TypeScript e build aprovados.
Runtime oficial real aprovado em CI, incluindo canário pausado após recriação,
sem disparo de modelo; sete testes PostgreSQL reais aprovados. Evidências em
[validação](hermes-validation.md), [operação](hermes-operations.md) e
[jobs](hermes-jobs.md). Inferência, bots/delegação nativa e Telegram reais
continuam aguardando configuração e homologação. Sem merge ou deploy.

## Integração Hermes e escritório — 29/10/2026

Continuação: journal persistente de admissões/IDs remotos, consulta de estado,
interrupção supervisionada com confirmação, consumo reportado e histórico
paginado. 168 testes Python locais e 18 E2E aprovados. Runtime oficial em CI
homologado sem inferência; cinco testes com PostgreSQL real aprovados em CI.
Veja [operação](hermes-operations.md), [runtime](hermes-runtime-ci.md) e
[PostgreSQL](postgres-ci.md). Modelos, Bot Mode, subagentes e Telegram reais
continuam dependentes de configuração própria.

Entrega incremental em `codex/hermes-integration`: auditoria oficial, cliente
Runs privado, consentimento persistente por executor, Compose com imagem oficial
fixada, diagnóstico autenticado, política textual sem ferramentas, sete perfis
nativos preparados e escritório pixel art com dados persistidos. Codex, banco,
GitHub e agendas preservados. Sem merge ou publicação em produção.

Validação local: suíte Python ampliada, 16 E2E, lint, TypeScript e build aprovados.
Veja [evidências e pendências](hermes-validation.md),
[configuração](hermes-setup.md) e [próximas fases](hermes-next-phases.md).
Hermes/Telegram/delegação reais aguardam runtime e credenciais próprios;
nenhuma fase operacional foi considerada homologada somente por mocks.

## V0.1 — base local funcional
- API FastAPI, autenticação de proprietário único, projetos, tarefas, transições manuais e eventos persistentes.
- Painel Next.js com visão geral, projetos, tarefas, papéis dos agentes, histórico, relatório JSON e estado das integrações.
- SQLite local; caminho PostgreSQL privado configurável, ainda sem homologação Supabase.
- Skills locais revisadas, AGENTS.md, arquitetura, instalação Windows, lockfiles e CI.

### Verificação local
- Python 3.12.15 / Node 24.16.0.
- `pytest services/api/tests/test_api.py -q`: 16 testes aprovados.
- `ruff check services/api`: aprovado após formatação, incluindo imports.
- `npm run lint`, `npm run typecheck`, `npm run build`: aprovados.
- `npm run test:e2e`: 5 testes aprovados; autenticação, CSRF, projeto/tarefa, persistência após reload, logout, 9 rotas móveis a 360px, checagem de overflow e varredura axe WCAG A/AA no login/visão geral.
- Captura de tela inspecionada localmente; conteúdo de E2E não foi semeado no banco de uso real.
- Graphify code-only: extração bem-sucedida, uso opcional e local.
- Revisão independente: corrigido desempate de eventos pelo UUID, substituído por sequenciador persistente. Teste observou falha antes e aprovação depois.

### Limitações
Agentes ainda não executam IA; papéis e modos são preparatórios. Não há gateway Codex, ferramentas GitHub, deploy Vercel, scheduler ou worker nesta versão. Não há EXE Windows. PostgreSQL e instalação em outro PC não foram testados.

Commit `600931d` publicado em `origin/main`. [CI remoto](https://github.com/igorcastro1010/ai-team/actions/runs/40622338992) concluído com sucesso no Ubuntu, incluindo pytest, lint, typecheck, build e E2E. Repositório confirmado privado.

### Próximo marco
V0.2: LangGraph, fila persistente, executor Codex com autenticação própria e limites. A escolha do usuário foi Codex oficial com login próprio. Nenhuma sessão ou credencial do Desktop pode ser copiada.

### Preparação de credenciais
Adicionado comando próprio de login e status. Dois testes adicionais verificam ambiente filtrado, contexto separado e armazenamento obrigatório em keyring (18 testes no total). Probe real `login status` retornou `Not logged in` no contexto AI TEAM, confirmando ausência de herança automática do Desktop. Fluxo de dispositivo iniciado para interação do proprietário; autenticação e inferência não declaradas funcionais antes de sua conclusão.

## V0.2 — execução textual supervisionada
- Login próprio concluído pelo proprietário e confirmado por probe, com armazenamento no keyring.
- CEO, DEV, DESIGNER e QA orquestrados por LangGraph; planejamento, delegação local, propostas, revisão e consolidação reais pelo CLI oficial.
- Solicitações, fila, etapas, artefatos, aprovações e consumo persistentes no banco. Worker separado, cancelamento, leases e proteção contra execução duplicada.
- Modos manual, supervisionado e automático limitado ao escopo textual consentido; decisões vinculadas à etapa e auditadas.
- Painel CEO, execuções e aprovações funcionais; scripts Windows inicializam também o worker.
- Backend: 36 testes automatizados; E2E: 6 fluxos, incluindo solicitação, revisão, confirmação, aprovação e cancelamento; sem inferência real no CI.
- Inferência real: cenário sintético autenticado, cinco workers em processos separados, cinco etapas concluídas, 56.953 tokens reportados. Cenário real adicional verificou recusa de leitura de canário fora do workspace.
- Lint, build e typecheck verificados; revisão independente e correções descritas em [segurança V0.2](v02-security-review.md).

### Limites e próximos passos
V0.2 entrega planos e pareceres textuais; não modifica código em outros repositórios nem executa testes desses projetos. GitHub operacional (V0.3) será via GitHub App com instalação por repositório, escolhido pelo usuário; teste inicial restrito ao novo `ai-team`. App e instalação precisam ser provisionados e validados. Vercel, Supabase hospedado, agendamento e publicação permanecem para os marcos seguintes. Nenhum deploy realizado.

## Preparação V0.3 — registro de GitHub App
- Fluxo oficial de manifesto para App privada, confirmação no GitHub e instalação seletiva pelo proprietário.
- Callback loopback com estado aleatório, prazo, uso único, validação de Host e conta; sem logs de códigos ou segredos.
- Cofre nativo obrigatório, gravação em partes e descarte de segredos OAuth/webhook não utilizados.
- Revisão independente identificou URL obrigatória no manifesto de webhook, mesmo desativado; teste de regressão falhou antes da correção e passou depois.
- Verificação: 41 testes Python e lint aprovados. O teste de cofre real escreveu, leu e removeu apenas uma entrada temporária de preflight.
- GitHub App e instalação ainda pendentes de validação real. Esta preparação não habilita ferramentas nos agentes e não conclui a V0.3.

## V0.3 — GitHub App e propostas supervisionadas
- Autenticação própria por JWT/cofre, instalação seletiva e tokens temporários restritos ao ai-team. Nenhuma credencial do gh ou Desktop reutilizada.
- Propostas imutáveis de branch, commit de documento, issue e PR; revisão, confirmação e aprovação vinculadas ao conteúdo no painel Integrações.
- Execução em worker separado, fila persistente, CAS/leases, SHA revisado, commit sem force e proteção contra replay e repetição de resultados incertos.
- Homologação real: quatro processos worker concluíram branch, documento, issue e PR no ai-team. [PR sintético #4](https://github.com/igorcastro1010/ai-team/pull/4), [issue #3](https://github.com/igorcastro1010/ai-team/issues/3), commit `6f48aafb02d5aaceb493a6aac2ab1201b5faed5c`. Sem merge ou deploy.
- Testes: 78 Python, lint Python, lint Next.js, typecheck, build e 7 E2E; aprovação GitHub, cancelamento de confirmação e validação axe adicionados. Testes comuns/CI usam transporte simulado, sem rede autenticada ou inferência paga.
- Skills aplicadas: planejamento, TDD, revisão e verificação; Supabase Postgres para persistência/concorrência; UI/UX Pro Max, Vercel React e Playwright para o painel.
- Revisão independente e correções descritas em [segurança V0.3](v03-security-review.md).

### Limites e próximo marco
Commits limitados a `docs/agent-output/*.md`, branches `codex/ai-team/*`, um repositório privado. Transferência das propostas dos agentes para o formulário GitHub ainda é manual; não há execução de código arbitrário, merge ou publicação. Rascunhos de PR dependem do plano e não foram homologados. PostgreSQL hospedado continua sem teste real. O primeiro cadastro admin do workspace de uso real continua pendente; dados de teste não foram usados como credencial desse workspace.

V0.4: manter o mecanismo Codex oficial já homologado e configurar acesso Vercel próprio para consultas; qualquer publicação exige autorização específica. V0.5 segue com agendamento/relatórios e V1.0 com endurecimento e hospedagem autorizada. Não considerar essas versões entregues por haver a V0.3 local.


## V0.4 — Vercel própria, somente consultas
- Projeto vazio ai-team criado na equipe autorizada, sem conexão GitHub, variáveis, domínio ou deploy. Consulta vinculada aos IDs da equipe e do projeto, com token preservado no cofre nativo do executor.
- Cliente oficial REST com endpoints GET fixos, sem redirecionamentos; painel autenticado de projetos/deploys, observação sanitizada persistida e trilha de auditoria. Atualizações do workspace leem somente o banco.
- Consulta real validada pela API autenticada, com persistência e lista de deploys vazia. Evidência local ignorada: `artifacts/vercel-smoke.json`. Login próprio do Codex reconfirmado; sem nova inferência paga nesta etapa.
- Verificação: 92 testes Python, lint Python/Next.js, typecheck, build e 8 E2E aprovados. Testes cobrem ausência/falha de credencial, vínculo por ID, sanitização, autenticação, Origin, persistência, painel e acessibilidade. Revisão independente sem defeitos importantes identificados.
- Skills: Vercel env-vars/CLI e documentação oficial, Supabase Postgres para persistência, UI/UX Pro Max, React/Next.js, Playwright, TDD, revisão e verificação.

### Limites e próximo marco
Nenhuma publicação foi realizada. O cliente implementa somente consultas, embora a credencial possa conceder escrita no provedor. Estados de deploy não vazios são cobertos por simulação, sem homologação real. Credenciais não são entregues aos agentes. V0.5 (recorrência e relatórios), PostgreSQL hospedado e instalação em outro PC continuam pendentes. O primeiro cadastro admin do banco de uso real precisa ser concluído pelo proprietário no terminal seguro.


## V0.5 — recorrências e relatórios
- Agendas imutáveis com consentimento, modo próprio, até cinco ocorrências, intervalo de 1 hora a 7 dias, início nos próximos sete dias e validade de 30 dias. Cancelamento e auditoria preservam histórico.
- Scheduler separado do HTTP, com CAS/transação única e proteção contra duplicação, sobreposição e recuperação em lote após indisponibilidade. Script Windows inicia e encerra também esse processo.
- Relatórios SQL abrangem todo o banco; histórico paginado com cursor e exportação da página, sem prompts, respostas, leases ou sessões.
- Verificação local: 106 testes Python, lint Python/Next.js, typecheck, build e 10 E2E aprovados. Testes cobrem dois schedulers, cancelamento concorrente, rollback, expiração, atraso, modo congelado, encaminhamento para cinco etapas de worker sintético, 205 execuções paginadas e exportação JSON.
- Processo scheduler real testado em banco temporário; nenhuma agenda criada no workspace real, nenhuma chamada IA paga e nenhuma publicação nesta versão.
- Skills: planejamento/execução, TDD/revisão/verificação, Supabase Postgres, UI/UX Pro Max, Vercel React e Playwright. [Revisão e limites](v05-security-review.md).

### Próximos passos
V1.0 exige homologar PostgreSQL privado, instalação fora deste PC e hospedagem segura de API/worker/scheduler. Publicação continua dependente de autorização específica. O cadastro admin do workspace real ainda deve ser concluído pelo proprietário no terminal seguro. Os agentes continuam produzindo planos e pareceres textuais; não executam código arbitrário em outros projetos. Custos monetários e serviço permanente do Windows não são implementados.

### Correção do cadastro inicial
Uma tentativa de login antes do primeiro cadastro criava o registro de limitação de acesso. O cadastro tentava inserir a mesma chave e falhava. Agora reutiliza o registro existente, preservando tentativas e prazo de bloqueio. Regressão reproduzida antes da correção; 107 testes Python e lint aprovados. Login e workspace autenticados também verificados localmente, sem registrar senha ou sessão.


## Continuação Windows — 30/10/2026
- Base sincronizada por fast-forward com `811bebf`, preservando a integração Hermes e o escritório virtual incorporados no GitHub.
- WSL 3.0.3 e Docker Desktop 4.97.0 instalados com autorização do proprietário. Docker CLI 29.9.2 e Compose 5.6.1 respondem pelo caminho instalado. Nenhum reinício executado; Windows registra reinício pendente e hipervisor ainda inativo. Engine/Hermes, login próprio e inferência local aguardam essa etapa.
- Diagnóstico somente leitura via `tools/doctor.ps1`: Python/Node/dependências, WSL, reinício CBS/Windows Update, engine Linux e Compose. Não lê arquivos de credenciais/cofres; erros e saídas de subprocessos não são exibidos. Prontidão nativa é distinta de Hermes, e não equivale a integração homologada.
- Inicialização nativa agora rejeita portas ocupadas e aguarda API saudável na versão esperada antes de iniciar o painel. Revalida API e filhos durante o início; `finally` preserva a limpeza dos processos próprios.
- Validação local: 213 testes Python aprovados, 7 PostgreSQL ignorados; 20 E2E, lint, typecheck e build aprovados. Dez testes específicos exercitam subprocessos PowerShell reais, API temporária, processo encerrado, timeout e respostas sanitizadas. CI Windows adicional usa apenas dados sintéticos e não instala Docker/WSL.
- Revisão independente corrigiu duas lacunas: indicador exclusivo de reboot Windows Update e API encerrando na janela entre prontidão e abertura do frontend. Sem novos defeitos nesses ajustes.
- Skills: planejamento/execução, diagnóstico, TDD, revisão e verificação. Sem publicação, Telegram, inferência paga ou importação de sessão nesta etapa. Reiniciar quando conveniente e seguir [ativação local](hermes-local-onboarding.md).
