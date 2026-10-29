# Evidências e limites — 29/10/2026

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

Docker não encontrado no PATH. Runtime Hermes, provedor e Telegram não foram
configurados nesta instalação. Tentativa opt-in de `smoke_hermes.py --real`
encerrou com diagnóstico de executor indisponível, antes de inferência. Não houve
envio de mensagens, delegação nativa, gastos de modelo, merge ou deploy.

Ainda é necessário comprovar inferência/modelo,
consumo reportado e cancelamento de inferência real, Bot Mode,
subagentes, autorização/pairing e mensagens Telegram reais. O ambiente PostgreSQL
hospedado, sandbox de código e produção também não foram homologados nesta entrega.

O mecanismo de stop é best effort: erro de rede pode deixar execução remota
incerta. Nenhuma readmissão automática é feita. Limiares locais de tokens e tempo
não substituem teto financeiro do provedor.
