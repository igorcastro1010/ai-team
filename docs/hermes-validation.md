# Evidências e limites — 29/10/2026

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

Docker não encontrado no PATH. Runtime Hermes, provedor e Telegram não foram
configurados nesta instalação. Tentativa opt-in de `smoke_hermes.py --real`
encerrou com diagnóstico de executor indisponível, antes de inferência. Não houve
envio de mensagens, delegação nativa, gastos de modelo, merge ou deploy.

Ainda é necessário comprovar gateway e imagem em execução, inferência/modelo,
consumo reportado, cancelamento remoto, reinicialização e volumes, Bot Mode,
subagentes, autorização/pairing e mensagens Telegram reais. PostgreSQL privado,
sandbox de código e produção também não foram homologados nesta entrega.

O mecanismo de stop é best effort: erro de rede pode deixar execução remota
incerta. Nenhuma readmissão automática é feita. Limiares locais de tokens e tempo
não substituem teto financeiro do provedor.
