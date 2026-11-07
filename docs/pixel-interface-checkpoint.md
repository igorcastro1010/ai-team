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

Implementação, documentação e testes locais concluídos. Commits de implementação enviados: `36b5a16`, `11524cd`, `9e8a787`, `2f61abe`, `864a32b`. Ver também `docs/pixel-interface-validation.md`.

PR [#15](https://github.com/igorcastro1010/ai-team/pull/15), empilhado sobre V0.8.1. Testes direcionados de escritório/mapa, vídeo, workspace, Python, Next.js e Hermes passaram em rodadas; lint, typecheck e build passaram. A regressão de Escape em confirmação aninhada foi reproduzida e corrigida, preservando a ferramenta e a aprovação pendente.

Para retomar: ler git status, HEAD e os checks atuais do PR #15. Se o CI do HEAD estiver verde, marcar o PR pronto para revisão e encerrar a automação. Se falhar, corrigir somente regressões da interface e repetir checks relevantes. Não refazer commits, iniciar V0.9, fazer merge ou deploy. A retomada de 03:46 já disparou durante esta execução; não manter repetição diária após concluir.

Não editar componentes durante E2E: Fast Refresh invalida estado em testes. Sem nova inferência externa, API paga, alterações de banco ou permissões.
