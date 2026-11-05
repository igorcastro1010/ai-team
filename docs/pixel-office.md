# Escritório pixel 2D

Abra `/escritorio` após iniciar o painel/API com `tools/start.ps1`. O mapa
original usa SVG e CSS, sem imagens, fontes externas ou engine de jogos.
A referência enviada pelo proprietário orientou a composição; não foi copiada
arte de outro produto. As demais páginas e os executores foram preservados.

O campus contém recepção/CEO, copa, desenvolvimento, criação, convivência e QA,
com mobiliário, jardim e iluminação. A lista lateral permite buscar e selecionar
qualquer agente. Os mesmos detalhes de resultados e links de aprovação continuam
abaixo do mapa. Projetos e últimas cinco atividades usam dados do workspace.

- Personagens habilitados disponíveis/concluídos circulam por trajetos fixos
  ortogonais, pelas portas e corredores. Essa circulação é ambiental.
- Trabalho nas mesas e contagem em execução dependem da projeção existente:
  `animate`, observação recente e conexão. Não são criadas tarefas ou chamadas
  de modelo para animar a interface.
- Aprovação, erro e papéis preparados ficam parados. A indicação visual não
  provisiona agentes nem substitui a autorização das ações.
- **Pausar animações** congela a cena. Aba oculta, conexão perdida, observação
  acima de 15 segundos ou preferência de movimento reduzido também interrompem
  movimento. Atualização de dados continua no mecanismo existente de 5 s.
- Zoom de 100 a 145%, com incremento de 15%; clique no percentual para restaurar.
  No celular, o mapa aparece primeiro. Explore por gesto horizontal ou teclado
  dentro da região focável; a página não ganha rolagem horizontal.
- Seleção é possível por personagem ou pela lista acessível. O botão acompanha
  o personagem durante o trajeto; foco visível e nomes acessíveis preservados.

## Validação

Testes sem inferência paga, com banco descartável e dados sintéticos. Playwright
cobre deslocamento real, pausa, zoom com aumento de dimensão em 360px, seleção,
busca, movimento reduzido, conexão perdida, aba oculta e trabalho confirmado sem
circulação. O estado de execução do teste visual é fixture do navegador e não
representa um job real. O fluxo existente de checkpoints/aprovações é testado
separadamente com backend real e provedor de contrato.

Inspeção visual e axe WCAG A/AA em 360/390/430/1440px, além de regressões dos
fluxos do painel. Capturas ignoradas no Git: `artifacts/office-*.png` e
`artifacts/office-campus-1440.png`. A revisão independente encontrou zoom que
mudava o rótulo sem ampliar no mobile; reproduzido RED e corrigido com teste
da dimensão real. Rack QA foi reposicionado para manter o trajeto livre.

Limites: mapa e percursos são fixos, sem física ou edição de salas; não representam
subagentes nativos adicionais. Animações não certificam execução externa. Não há
áudio, multiplayer, publish ou deploy nesta entrega.

Em 04/11/2026: 271 pytest passaram; 21 testes opt-in Docker/PostgreSQL foram
omitidos nesta alteração exclusivamente visual. Lint, typecheck, build e 26 E2E
passaram. Os quatro tamanhos de tela foram inspecionados e não apresentaram
violações axe detectadas ou overflow horizontal da página. Revisão independente
final sem bloqueio restante. [PR #9](https://github.com/igorcastro1010/ai-team/pull/9)
em rascunho, sobre a entrega de QA no Chromium; CI deve ser consultado à parte.
