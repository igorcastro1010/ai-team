# Verificação da interface integrada

Base: V0.8.1 `c22b22e`, sem V0.9 disponível nas referências verificadas. Branch `codex/ai-team/pixel-interface`; PR empilhado [#15](https://github.com/igorcastro1010/ai-team/pull/15), base `codex/ai-team/v081-video-studio`.

## Evidências locais

- `office-navigation.spec.ts`: login abre mapa; identidade do nó e zoom persistem ao abrir/fechar vídeos e CEO; Escape; link direto móvel; Axe A/AA; inércia explícita do fundo.
- `office.spec.ts` e `office-map.spec.ts`: dez cenários de estado real, checkpoints, perda de sinal, animação reduzida, zoom, pausa e responsividade passaram.
- `video.spec.ts`: revisão por digest, cancelamento e isolamento por projeto passaram.
- `video-studio.spec.ts`: edição de cenas, autosave, persistência após recarga, template, upload e limites passaram. Uma rodada com Fast Refresh durante edição de componentes invalidou o rascunho do teste; reexecução sem alterações simultâneas passou.
- Workspace e executores: criação, quadro, persistência, CSRF, logout, aprovações GitHub/CEO, relatórios, navegação móvel e resultados Python/Next.js passaram na rodada direcionada. Confirmações foram distinguidas da janela contenedora nos seletores existentes, sem remover testes.
- Hermes: dois testes de contrato passaram após mover Atualizar workspace para dentro da janela; o controle anterior ficava bloqueado pelo modal. Isso valida interface/contrato, sem homologação de inferência externa.
- Lint, typecheck e build locais retornaram código zero.

Logs completos em `.data/pixel-*.log`; screenshots em `artifacts/pixel-integrated-desktop.png` e `artifacts/pixel-integrated-mobile.png`. Dados e mídias de teste não foram incluídos no Git. Nenhuma inferência externa, deploy ou merge foi executado.

## Regressões corrigidas

Navegação escondida no desktop por regra CSS legada; camada da barra superior bloqueando o botão do menu móvel; links ambíguos entre mapa e janela; confirmações aninhadas nos testes; atualização manual do workspace inacessível dentro do modal. Mapa e sidebar recebem inércia explícita quando uma ferramenta está aberta.

O teste adicional de Escape reproduziu propagação do cancelamento de uma confirmação para a janela contenedora. O handler agora responde somente ao próprio diálogo. A regressão passou com a ferramenta aberta e a execução ainda aguardando aprovação; cancelar a confirmação não autoriza a ação nem fecha o módulo.

## Gate de entrega

A suíte completa Python/PostgreSQL/Docker/E2E permanece no CI existente. O estado definitivo deve ser consultado nos checks do último SHA do PR #15. Não considerar runs de commits anteriores como aprovação do HEAD. O PR só deve sair de rascunho após os checks relevantes ficarem verdes.

Limites: uma ferramenta por vez; estado transitório da ferramenta pode reiniciar ao trocar; aguardar autosave. Recarregar página reinicia mapa. Auditoria Axe é automatizada, não revisão humana. API, autenticação, banco e execução dos agentes não foram redesenhados.
