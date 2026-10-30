# Evidências e limites — 30/10/2026

## Continuação: monitor e jobs nativos

- Suíte final local: **202 testes Python e 20 E2E aprovados**, Ruff,
  ESLint, TypeScript e build aprovados. Sete testes PostgreSQL ficam opt-in
  localmente e foram executados no serviço descartável de CI.
- Monitor separado com lease persistente, recuperação após queda e backoff;
  apenas GET por ID conhecido, sem readmissão nem interrupção automática.
- Inventário de jobs nativos e pausa vinculada ao recurso, com confirmação e
  leitura posterior. Sem criação, disparo, retomada ou exclusão pelo produto.
- [Runtime oficial](https://github.com/igorcastro1010/ai-team/actions/runs/41041265083):
  políticas API/cron, autenticação, perfis, adaptador privado, SessionDB e
  canário nativo pausado preservados após recriação; nenhuma tarefa disparada.
- [PostgreSQL real](https://github.com/igorcastro1010/ai-team/actions/runs/41042021402):
  sete testes aprovados, incluindo leases concorrentes e inventário/evidência
  de pausa persistida com atualização atômica do cache.
- Painel: confirmação por job, aviso de execução em andamento, sinal do monitor
  separado de trabalho dos agentes, BFF restrito e proteção de origem.
- Regressões determinísticas: consulta atrasada preserva pausa incerta;
  confirmação antiga não encobre nova solicitação ou retomada externa;
  pausar um segundo job preserva o estado do primeiro. Provas são ordenadas
  pelo início da leitura e projetadas por recurso.
- Inicialização Windows prepara o banco antes dos processos concorrentes;
  parser PowerShell aprovado e `init-db` executado duas vezes em banco isolado.

Inferência, Bot Mode/delegação nativa e mensagens Telegram continuam pendentes
de configuração e homologação próprias. Esses testes não demonstram modelos
ou bots executando tarefas.

## Continuação: journal e operação supervisionada

- Suíte local: **168 testes Python e 18 E2E aprovados**; Ruff, ESLint,
  TypeScript e build aprovados. Os cinco testes PostgreSQL são opt-in e ficam
  ignorados localmente sem banco de CI explícito.
- [Runtime Hermes oficial](https://github.com/igorcastro1010/ai-team/actions/runs/40922239576):
  gateway, autenticação, política sem ferramentas, sete perfis reconhecidos e
  persistência de SessionDB após recriação aprovados, sem inferência.
- [PostgreSQL real](https://github.com/igorcastro1010/ai-team/actions/runs/40924442533):
  cinco testes aprovados com login de aplicação restrito, schema privado,
  preservação de dados, autenticação/consentimento e concorrência do journal.
- [Adaptador AI TEAM em rede privada](https://github.com/igorcastro1010/ai-team/actions/runs/40925289265):
  imagem da API construída e cliente real consultando o gateway Hermes real
  pela rede do Compose, sem chamada de modelo.
- Novas regressões: admissão incerta, unicidade de estágio entre workers,
  cancelamento sem confirmação, respostas tardias, consumo monotônico e
  histórico paginado estável durante atualizações. Revisão independente aplicada.

Esses testes não enviaram mensagens Telegram nem comprovaram inferência ou
delegação nativa. A validação PostgreSQL descartável não instala ou migra Supabase.

## Verificação local

- Base anterior: 107 testes Python aprovados antes da implementação.
- Suíte Python final ampliada: **144 testes aprovados**, incluindo redação de
  entradas de configuração nos erros de validação.
- Ruff da API, scripts Hermes e health check: aprovado.
- ESLint, TypeScript e build Next.js: aprovados.
- Playwright completo: 16 testes aprovados, incluindo os dez fluxos anteriores.
- Escritório: 360, 390, 430 e 1440 px, sem overflow horizontal; varreduras axe
  WCAG A/AA sem violações detectadas nesses fluxos.
- Teste integrado de checkpoints: API autenticada, SQLite descartável, worker
  com provedor sintético, plano/resultado persistido e aprovação visível no
  escritório via atualização automática. **Não é inferência Hermes real.**
- Provisionador: sete homes nativos, rerun sem sobrescrever persona/credenciais,
  rejeição de manifesto inválido e diretório de destino vinculado.
- Compose analisado como YAML e verificado para porta Hermes ausente, rede
  privada e health check de política. **Não executado por Docker nesta máquina.**

Capturas locais ignoradas pelo Git: `artifacts/office-360.png`, `office-390.png`,
`office-430.png`, `office-1440.png`. Mostram workspace de testes com dados
sintéticos, não produção. Capturas móvel e desktop inspecionadas visualmente.

## Revisão independente

Corrigidos e cobertos por regressão:

1. Inventário oficial usa envelope `{object, platform, data}`; exemplos resumidos
   de documentação não substituem o contrato do código auditado.
2. Requisições têm timeout total assíncrono, incluindo resposta entregue lentamente;
   o deadline da chamada acompanha admissão e polling.
3. Execução ativa tem prioridade sobre solicitação mais nova na fila no escritório.
4. Data de cada resultado vem do checkpoint, não do início da solicitação.
5. Inventário REST omite MCP padrão; health check resolve toolsets efetivos no
   runtime, além de configuração montada somente leitura sem MCP.
6. Erros de configuração ocultam entradas, protegendo segredos em erros de validação.

## Homologação externa pendente

Atualização da continuação: o [runtime oficial em CI](https://github.com/igorcastro1010/ai-team/actions/runs/40922239576)
passou em gateway, autenticação HTTP, política efetiva, sete perfis reconhecidos
pelo Hermes e SessionDB preservado após recriação. A ausência de Docker local
não impediu essa homologação em runner Linux descartável. Isso não comprova
inferência, delegação nativa, Telegram ou operação de produção.

Na verificação anterior, Docker não foi encontrado no PATH. Runtime Hermes,
provedor e Telegram não estavam configurados nesta instalação. A tentativa
opt-in de `smoke_hermes.py --real`
encerrou com diagnóstico de executor indisponível, antes de inferência. Não houve
envio de mensagens, delegação nativa, gastos de modelo, merge ou deploy.

Ainda é necessário comprovar cancelamento de inferência real, Bot Mode,
subagentes, autorização/pairing e mensagens Telegram reais. O ambiente PostgreSQL
hospedado, sandbox de código e produção também não foram homologados nesta entrega.

O mecanismo de stop é best effort: erro de rede pode deixar execução remota
incerta. Nenhuma readmissão automática é feita. Limiares locais de tokens e tempo
não substituem teto financeiro do provedor.

## Homologação local após login próprio — 30/10/2026

Após o reinício autorizado, WSL e engine Docker Linux ficaram operacionais.
O gateway usa a imagem fixada no Compose e publica somente `127.0.0.1:8642`,
com chave privada. Health check e política efetiva passaram; sem chave, a API
retornou HTTP 401. O adaptador Windows confirmou `reachable`.

O usuário concluiu login próprio `openai-codex` no volume Hermes e selecionou
`gpt-6.1-sol`. A adoção de logins externos continua desativada, assim como
ferramentas API/cron/Telegram/CLI e MCP. Nenhuma sessão Desktop foi importada.

`python tools/smoke_hermes.py --real` passou: cinco chamadas reais nas etapas
CEO → DEV → DESIGNER → QA → CEO, aprovação supervisionada e persistência entre
cinco instâncias de worker, usando projeto fictício e banco temporário.
Uso reportado pelo gateway: 7.896 tokens de entrada e 924 de saída; não há
valor monetário confirmado. Evidência local ignorada: `artifacts/hermes-smoke.json`.
O banco Windows e o usuário existente foram preservados.

Isso homologa o fluxo textual pelo adaptador. Telegram, delegação nativa,
sandbox de desenvolvimento, cancelamento real e produção seguem pendentes.
