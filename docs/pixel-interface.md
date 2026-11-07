# Interface Pixel Art integrada

Após login, `/` abre o mapa existente. `/escritorio` continua disponível. O layout compartilhado `app/(workspace)` mantém Dashboard e PixelOffice montados durante navegação interna; autenticação, APIs, banco, workers e aprovações permanecem existentes.

## Operação

- CEO/mesa da recepção: conversa e planejamento.
- DEV/computador: execuções e Executor de Repositório; tarefas também no dock.
- DESIGNER/sala de criação: estúdio de vídeos existente, incluindo mídia, templates, rascunhos, revisão, renderização e download.
- QA/bancada: execuções e resultados. Agentes aguardando autorização abrem aprovações.
- PESQUISADOR/biblioteca: memória.
- Dock: projetos, tarefas, memória, modelos, histórico, integrações e aprovações. Menu recolhível: relatórios, agendamentos, agentes e saída da conta.
- `/resumo`: indicadores preservados da página inicial anterior.

Ferramentas abrem sobre o escritório. Fechar ferramenta e Escape retornam ao mapa; Voltar usa o histórico do navegador. A faixa Trocar ferramenta permite navegar sem recriar o escritório. Links diretos antigos continuam válidos.

Zoom, seleção e rolagem permanecem durante navegação interna. Recarregar a página ou sair da conta cria nova instância. Explore com rolagem, toque ou setas na região do mapa. Links e botões nativos complementam o acesso por teclado. Circulação ambiental não representa inferência. Estados reais e animações de trabalho continuam dependendo do backend e da atualidade do sinal; movimento reduzido permanece respeitado.

## Limites e segurança

Diálogo nativo mantém foco e torna o fundo inerte. Nenhum comando, permissão ou aprovação foi alterado. Progresso e revisão dos vídeos ficam no painel de produção do projeto. Há uma ferramenta aberta por vez; seu conteúdo é desmontado ao trocar, mas o escritório permanece. Aguarde “Rascunho salvo” antes de sair do editor. Não há múltiplas janelas arrastáveis nem persistência de zoom após recarregar.

## Verificação

`npm run test:e2e --workspace @ai-team/web -- office-navigation.spec.ts` verifica login, identidade do nó do escritório, zoom preservado, CEO, vídeos, Escape, link direto móvel e WCAG A/AA automatizado. Banco descartável, sem inferência externa. Screenshots locais: `artifacts/pixel-integrated-desktop.png` e `artifacts/pixel-integrated-mobile.png` (ignorados pelo Git).

Regressões: office, office-map, video-studio, video e workspace. Lint, typecheck e build complementam a suíte completa no CI. Resultados e pendências efetivos ficam no checkpoint e no PR.
