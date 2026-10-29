# Entregas e evidências

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
