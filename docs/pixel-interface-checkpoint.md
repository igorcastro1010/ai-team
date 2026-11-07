# Interface Pixel Art integrada — plano e retomada

Base verificada: `c22b22e`, V0.8.1, PR #14. Não havia V0.9 local/remota nem alterações pendentes no início. Branch: `codex/ai-team/pixel-interface`. Não fazer merge, deploy ou inferências externas.

## Desenho

Reutilizar PixelOffice e OfficeMap, mantendo o Dashboard em um layout compartilhado das rotas autenticadas. Login permanece separado. A URL continua identificando a ferramenta, mas seu conteúdo aparece em janela modal sobre o mesmo escritório, sem reiniciar zoom, seleção, polling ou animação. Menus, salas e personagens dão acesso às ferramentas existentes; os dados e autorizações continuam nas APIs atuais.

Janelas usam diálogo nativo, Escape, botão fechar, voltar e links diretos. Navegação por teclado e alvos de toque complementam o mapa. Atividades continuam derivadas do backend; circulação ambiental não representa inferência.

## Entregas e verificações

1. Teste direcionado de login, escritório persistente, navegação e links diretos.
2. Layout compartilhado, janela acessível e navegação recolhível.
3. Atalhos de agentes, salas e estações; adaptação móvel.
4. Testes direcionados de escritório e vídeo, lint, typecheck e build; suíte completa no CI.
5. Documentação, pushes e PR empilhado sobre V0.8.1. Registrar evidências e limitações.

## Estado

Planejamento registrado. Implementação e homologação ainda pendentes. Agendamento solicitado para retomar neste chat às 03:46; consultar git status e os commits antes de continuar.
