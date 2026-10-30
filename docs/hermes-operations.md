# Histórico e controle das execuções Hermes

Em **Integrações → Hermes → Execuções remotas**, cada tentativa mostra etapa,
estado no AI TEAM, último estado observado no Hermes, ID remoto e consumo
reportado. Campos de tokens ausentes permanecem **não informados**, sem estimar
dinheiro ou declarar consumo zero.

## Por que existem dois estados

Cancelar no AI TEAM encerra a solicitação local. Uma chamada já admitida no
gateway pode continuar se houver falha de rede. O worker tenta interrompê-la,
mas somente uma resposta de estado terminal do próprio Hermes confirma o que
aconteceu remotamente.

- **Interrupção solicitada:** `/stop` foi solicitado; o estado remoto ainda não
  confirmou cancelamento.
- **Interrupção não confirmada:** houve erro de comunicação ou resposta inválida.
  A execução pode continuar e consumir uso.
- **Interrupção confirmada:** o Hermes reportou `cancelled` ou `interrupted`.
- **Já havia terminado:** o Hermes reportou `completed` ou `failed`; isso não é
  apresentado como cancelamento bem-sucedido.

Use **Consultar estado remoto** para reconciliar. Essa ação chama apenas GET
no ID já persistido e não inicia inferência. Se o pedido local estiver cancelado
ou falho e a execução remota continuar não terminal, **Interromper no Hermes**
abre uma confirmação vinculada à tentativa e etapa selecionadas. A ação usa o
`/stop` oficial e consulta o estado; não cria outra execução.

Se o pedido local ainda estiver ativo, cancele primeiro em **Execuções**. O
controle remoto recusa interrupção avulsa enquanto o workflow ainda pode avançar.
Resultados que chegam depois de cancelamento não são importados como novas
etapas, nem tornam o pedido local concluído.

## Admissão incerta e reinicialização

A tabela adicional `hermes_attempts` persiste uma identidade antes de enviar
`POST /v1/runs`. Um índice único impede duas admissões para o mesmo pedido/etapa,
inclusive com workers concorrentes. Após resposta válida, o ID nativo é gravado
antes do polling. A chave de admissão não é enviada ao navegador.

Uma queda entre envio e resposta deixa a tentativa sem ID remoto. Nenhuma nova
admissão é criada automaticamente, nem com outra chave. Inspecione o gateway e
a solicitação antes de autorizar novo trabalho. O histórico continua disponível
após reiniciar API/worker e não depende de logs de processo.

Mensagens brutas, prompts, resultados e erros do provedor não entram no journal.
Resultados textuais válidos continuam nos checkpoints existentes, acessíveis
somente ao proprietário. Eventos de auditoria registram estados sanitizados.

## Histórico e consumo

A API retorna páginas de até 50 tentativas com cursor por data/ID. Ao carregar
páginas anteriores, o painel mantém uma consulta estável para não perder registros
com a chegada de novas tentativas. **Voltar às tentativas mais recentes** reabre a
visão atual. Status de registros já presentes continuam sendo atualizados quando
observados; consultas manuais também atualizam registros de páginas antigas.

Respostas atrasadas não regridem execução ativa para fila/início, nem reduzem
contadores. Um status terminal não volta a ativo. Uma consulta posterior com o
mesmo status terminal pode preencher consumo que faltava. Em estado `unknown`,
aguarde resolução terminal no gateway; o painel não reconhece automaticamente
um retorno a execução ativa sem uma resolução verificada.

## Processo de reconciliação automática

O serviço separado `hermes-monitor` consulta somente IDs remotos já persistidos
quando a solicitação foi cancelada/falhou, mudou de etapa ou perdeu sua lease.
Não admite, retoma ou interrompe trabalho e não altera o resultado local.
Tentativas sem ID remoto continuam exigindo inspeção humana.

`tools/start.ps1` inicia o processo com janela oculta e logs próprios em
`.data/hermes-monitor.*.log`; o Compose oferece o serviço de mesmo nome.
Para diagnóstico sem loop, execute
`.venv/Scripts/python.exe -m ai_team.hermes_monitor --once`.
Cada iteração trata no máximo uma tentativa; o loop espera cinco segundos.
Uma consulta bem-sucedida agenda nova observação após 30 segundos; falhas
aplicam backoff de 60 segundos até 15 minutos. A lease exclusiva dura 90 segundos
e permite recuperação após queda, sem compartilhar a lease do worker.

A tabela adicional `hermes_polls` persiste lease, próxima consulta e falhas.
Execute `ai-team init-db` antes de atualizar processos em produção. Não remove
dados nem altera colunas existentes. O painel mostra o último sinal e indica
quando passou de 45 segundos. O sinal comprova atividade do monitor; não comprova
disponibilidade do gateway, inferência ou trabalho dos personagens.

Agendamentos nativos têm um controle separado de
[inventário e pausa confirmada](hermes-jobs.md).

## Migração e compatibilidade

Nova tabela e índices, sem remoção de dados ou alterações nas colunas antigas.
Em produção, execute `ai-team init-db` **antes** de iniciar a nova API/worker.
No desenvolvimento a inicialização continua automática. A compatibilidade com
PostgreSQL real foi [verificada em CI](postgres-ci.md); a migração e operação
no ambiente hospedado próprio ainda precisam de homologação específica.

## Limites da evidência

Os testes de journal/controle usam contrato oficial e provedores de teste. A
homologação real do contêiner, autenticação, política e persistência está em
`hermes-runtime-ci.md`. Inferência e cancelamento de uma chamada real ao modelo
ainda exigem runtime e credenciais próprios. Telegram, subagentes nativos e
execução de código não são habilitados por esses controles.
