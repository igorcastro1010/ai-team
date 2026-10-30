# Monitor independente de execuções remotas — 30/10/2026

Continuação autorizada do AI TEAM. A configuração local do Hermes foi verificada
sem exibir segredos: ausente. Checks do PR #5 aprovados no estado inicial.

## Objetivo

Reconciliar automaticamente tentativas remotas que ficaram sem worker após
cancelamento, falha ou expiração da lease local. Reutilizar exclusivamente GET
da API Runs oficial; não readmitir trabalho, iniciar modelos ou repetir stop.
Interrupção remota continua exigindo confirmação vinculada à tentativa.

## Entregas

- [x] Tabela adicional por tentativa com próxima consulta, lease, falhas e resultado
  sanitizado; índice de busca e aquisição atômica entre processos.
- [x] Processo próprio `ai_team.hermes_monitor`, lotes e deadlines limitados,
  backoff em falha, estado terminal preservado e consumo monotônico.
- [x] Integrar inicialização Windows e Compose; heartbeat separado do worker de
  inferência, sem marcar o escritório como trabalhando por causa do monitor.
- [x] Exibir atividade do monitor, última observação e falhas de consulta no
  painel autenticado; sem detalhes brutos, prompts ou credenciais.
- [x] Testes de processo, disputa, backoff, expiração/cancelamento local e sigilo;
  verificações gerais, commits convencionais e push por entrega validada.

## Restrições

Não alterar/remover colunas ou dados existentes. Produção precisa de init-db
antes da atualização. Sem shell de agente, merge, deploy ou contratação.
Tabela de monitor é independente do journal para preservar seu formato.
Uma tentativa sem ID remoto fica incerta para inspeção humana; nenhuma chamada
de admissão é feita para tentar recuperar seu ID.

## Pesquisa paralela

Verificar contratos oficiais de jobs/cron e sua política real de ferramentas,
sem implementar controles que possam iniciar inferência ou ampliar permissões.
O resultado dessa pesquisa não comprova agenda ou delegação executada.
