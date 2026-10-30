# Jobs nativos: inventário e pausa

O painel pode consultar os jobs existentes no gateway e pausar um agendamento
específico com confirmação do proprietário. Não oferece criação, edição,
retomada, disparo manual ou exclusão de jobs. Consultar o inventário não envia
inferência. **Pausar impede novos disparos; não interrompe uma execução que já
começou**, que pode continuar consumindo uso.

## Interfaces para integração

- `ai_team.hermes_job_routes.router`: incluir em `create_app()` sem prefixo
  adicional. O router já usa `/hermes/jobs` e `require_owner`; a proteção de
  Origin permanece no middleware existente da aplicação.
- `ai_team.hermes_jobs.jobs_snapshot(database)`: leitura exclusivamente local
  do último inventário; anexar ao snapshot do workspace em `hermes.jobs`.
- `apps/web/components/hermes-jobs.tsx`: exporta `HermesJobs`; os tipos ficam em
  `apps/web/lib/api.ts`. Props:
  `first?: HermesJobsSnapshot`, `reload: () => Promise<void>`.
- O BFF deve permitir somente os três caminhos abaixo, sem proxy genérico para
  a API de jobs do Hermes.

| Endpoint AI TEAM | Efeito |
| --- | --- |
| `GET /hermes/jobs` | Lê cache persistido; não consulta o gateway |
| `POST /hermes/jobs/inspect` | Consulta `GET /api/jobs?include_disabled=true` |
| `POST /hermes/jobs/{job_id}/pause` | Exige `{ "confirm": true }`, sem campos extras; confere o job, solicita pausa e verifica o estado |

Inventário persistido em `ProviderObservation`, ID `hermes-jobs`, sem migração.
Evidências de pausa são eventos imutáveis: a confirmação aponta para o ID da
solicitação que verificou. `last_pause` é derivado da solicitação mais recente,
então uma leitura atrasada ou confirmação antiga não apaga uma pausa incerta.
Inspeções usam a sequência de eventos para ordenar observações e atualização
atômica do cache; uma resposta antiga não substitui uma consulta mais recente.
Uma nova consulta pode mostrar uma retomada feita diretamente no Hermes.
O snapshot público mantém o formato:

```text
status: not_configured | unavailable | reachable
checked_at: epoch ou null
items: até 100 JobView
truncated: boolean
last_pause: {job_id, status: confirmed | uncertain, checked_at} ou null
```

Cada `JobView` contém somente `id`, `name` (até 200 caracteres imprimíveis),
`enabled`, estado reconhecido, tipo de agenda, timestamps normalizados e
contadores de repetição. Prompts, scripts, skills, destinos de entrega, origem,
credenciais, provider/base URL, saídas, erros e recibos de execução não entram no
browser nem na observação persistida. O cliente HTTP já limita bytes e prazo;
o inventário limita também o número de registros. `truncated` sinaliza o corte.

Falha de inspeção preserva dados anteriores com status `unavailable`; eles podem
estar desatualizados. ID inválido, duplicado ou contrato malformado não amplia
permissões. IDs aceitos têm exatamente 12 caracteres hexadecimais minúsculos,
conforme o runtime fixado.

A pausa usa somente um ID já presente no cache. Faz GET fresco e valida a
identidade antes de qualquer POST. Registra incerteza antes da mutação, então
executa exclusivamente `POST /api/jobs/{id}/pause` e GET do mesmo recurso.
Somente `enabled=false` e `state=paused` observados nessa leitura permitem
responder `confirmed`. Resposta perdida ou estado contraditório retornam erro
genérico e mantêm `last_pause.status=uncertain`; não há repetição automática.
Job já pausado pode ser confirmado pelo GET sem outro POST. Eventos de pausa
registram o ID validado e ator, sem payload remoto.
Uma inspeção posterior que observe o mesmo job desabilitado e pausado pode
reconciliar a incerteza sem mutação. As três chamadas da pausa compartilham
deadline total de oito segundos, deixando margem para persistência e resposta
HTTP antes do limite do BFF. No componente, uma nova prop de snapshot substitui
o feedback local por identidade; timestamps com resolução de segundos não
impedem a atualização de estados observados em outro browser.

## Contrato oficial e política de cron

Referências oficiais consultadas em 30/10/2026:

- [Jobs API](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server#jobs-api-background-scheduled-work).
- [Agendamentos nativos](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron).
- [`api_server.py` auditado](https://github.com/NousResearch/hermes-agent/blob/e298669b44ce032a995c8a67ceae025801b0f4bf/gateway/platforms/api_server.py),
  [armazenamento](https://github.com/NousResearch/hermes-agent/blob/e298669b44ce032a995c8a67ceae025801b0f4bf/cron/jobs.py)
  e [scheduler](https://github.com/NousResearch/hermes-agent/blob/e298669b44ce032a995c8a67ceae025801b0f4bf/cron/scheduler.py).

O código foi também conferido diretamente na camada SHA-256
`fcf720a342af7b5020f7a08992d0fd6437bd319f66b1cd3a76ad735c06a04899` da imagem
Hermes fixada no Compose. O main consultado,
`2f5a5a7615decaced1ea557f6cbcfe01b0d6e392`, mantém os contratos relevantes.

O inventário oficial retorna `{jobs: [...]}`; consulta padrão omite desabilitados.
Pausa/retomada retornam `{job: ...}`. A criação aceita `paused: true` de forma
atômica e não registra o primeiro trigger enquanto desabilitado. `repeat` é
armazenado como `{times, completed}`; ausência de limite significa recorrência
indefinida. Retomar um job atrasado pode executar catch-up imediatamente.

O resolver `_resolve_cron_enabled_toolsets` usa primeiro o campo por job
`enabled_toolsets`; `[]` explícito significa nenhuma ferramenta, inclusive MCP.
Sem override, usa `_get_platform_tools(config, 'cron')`, que inclui MCP padrão.
Portanto o controle de plataforma é `platform_toolsets.cron: []`, acompanhado de
`mcp_servers: {}`; `cron.toolsets` não é lido por esse resolver. Overrides por job
podem ser mais amplos que a plataforma, e scripts/no-agent usam outro caminho.
O health check confere as políticas efetivas API e cron, incluindo MCP; isso
comprova o padrão da configuração, não certifica a segurança de cada job existente.
Homes nativos novos recebem cron vazio. Homes existentes preservam suas
configurações e exigem revisão própria; o provisionador não sobrescreve estado.

Embora a documentação geral descreva mais opções, o handler REST fixado ignora
`no_agent`, `script`, `enabled_toolsets`, `model` e `provider` na criação. Enviar
`no_agent: true` por essa API não garante ausência de inferência. A whitelist de
PATCH também é estreita. Por isso o produto não expõe esses endpoints, e o
limite de Runs API não é apresentado como limite de cron.

## Teste real em CI sem disparo

O smoke oficial agora exige `AI_TEAM_RUNTIME_CI=true` dentro do container para
qualquer mutação de job. O workflow fornece o marcador somente nas duas fases
do smoke. Exige volume exclusivo e inventário inicialmente vazio, então cria
um canário `every 365d`, `repeat=1`, `deliver=local`, sem skills, inicialmente
pausado. Confere o registro persistido antes da ativação.

Somente nesse CI descartável, retoma o canário, exige próximo disparo a mais de
300 dias e pausa novamente. Confere por GET `enabled=false`, `state=paused`,
`repeat.completed=0`, ausência de execução/recibo e persistência após recriar o
container. A rede é interna, não há credenciais de modelo e nenhum endpoint
`/run` é chamado. O volume inteiro pertence ao job de CI; não se excluem jobs
de instalações do proprietário.

A extensão de jobs foi aprovada no
[runtime oficial em CI](https://github.com/igorcastro1010/ai-team/actions/runs/41041265083),
commit `5985fe49fc6cb80bcf64417aed974e15f094840a`, em 30/10/2026.
As duas fases passaram, incluindo pausa e preservação após recriação.
Não houve criação de job nativo fora do CI, disparo de tarefa, execução de
modelos ou Telegram nesta implementação.
