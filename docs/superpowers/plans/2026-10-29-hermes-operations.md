# Hermes — execuções rastreáveis e homologação do runtime

Continuação autorizada do projeto AI TEAM, sobre o PR #5. Preservar executor
Codex, consentimentos, autenticação e banco. Reutilizar Runs/stop oficiais;
nenhuma ferramenta, inferência, mensagem Telegram ou publicação é habilitada.

## Entregas

- [ ] Teste CI com imagem oficial fixada: gateway real, autenticação, política
  efetiva, perfis e persistência após recriação; sem provedor ou inferência.
- [ ] Journal adicional `hermes_attempts`: identidade de admissão persistida antes
  do envio, ID remoto, estágio, status, consumo reportado e cancelamento observado.
- [ ] Worker vincula cada tentativa à execução e à lease; tentativa existente
  jamais é readmitida automaticamente após queda ou resultado incerto.
- [ ] Rotas de proprietário para histórico paginado e reconciliação por consulta.
  Stop remoto exige confirmação e execução local já encerrada; não aceita IDs
  remotos ou URLs arbitrárias do navegador.
- [ ] Painel apresenta tentativa local/remota, consumo desconhecido como tal,
  cancelamento pendente/incerto e confirmação vinculada à tentativa selecionada.
- [ ] Testar persistência, disputa, contrato oficial, CSRF, redação, controle
  remoto e interface responsiva; commits/push por unidade validada.

## Arquitetura

Tabela nova, sem alterar/remover colunas existentes. Uma tentativa por
`(run_id, stage)`, chave idempotente única. Somente o servidor guarda essa chave.
Eventos de auditoria contêm códigos/status sanitizados, sem prompt, resultado
bruto, configuração ou erro remoto. Consultas e stop têm deadline HTTP limitado;
nenhum job longo executa no request do painel.

Preparação de runtime CI é independente do journal e delegada em arquivos
separados. Integração e validação final ficam com o agente principal.

## Casos obrigatórios

Resposta de admissão perdida; queda após admissão; stop sem confirmação; resposta
concluída após cancelamento local; regressão de status em consulta atrasada;
identificador remoto inválido; cursor inválido; campos de consumo ausentes;
tentativa de repetir estágio e recusa de controles sobre outro recurso.

## Limites

CI sem modelo não comprova inferência/delegação/Telegram. Runtime local continua
sem Docker. Credenciais próprias serão configuradas pelo proprietário no servidor;
não acessar cofre ou sessão Desktop. Merge e produção permanecem dependentes de
aprovação específica.
