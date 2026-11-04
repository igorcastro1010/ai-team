# Escritório pixel 2D com circulação

Pedido: aproximar a interface da referência enviada, com agentes se movimentando.
Reutilizar o escritório real, sem mexer em executores, credenciais ou permissões.

Escolha de implementação: React + SVG original para o mapa e personagens;
CSS para trajetos e sprites, sem engine ou bibliotecas novas. Canvas dificultaria
teclado/semântica; imagens externas adicionariam dependências e dificultariam
ajustar posições. Referência guia composição, sem copiar arte/marca de terceiros.

Mapa dominante com recepção, copa, desenvolvimento, criação, convivência e QA;
jardim, árvores, iluminação e corredores. Barra de métricas reais, equipe lateral,
projetos e atividade recente; detalhes/histórico e aprovações permanecem acessíveis.
Controles de zoom e pausa, navegação por teclado, versão mobile com mapa rolável
dentro da região e lista acessível. Sem overflow da página.

Agentes habilitados ociosos podem circular em trajetos ortogonais pelos corredores.
Isso é animação ambiental, nunca prova de execução. Agentes com atividade
confirmada permanecem na mesa com animação de trabalho; aprovação/erro/preparados
ficam parados. Sem dados recentes/conexão, página oculta, pausa ou reduced-motion,
não animar. Status e contagem de trabalho continuam derivados do backend.

Aceite: aparência top-down próxima à referência, personagens andando sem cruzar
paredes, estados reais preservados, seleção de todos os agentes, pausa/zoom,
foco, reduced-motion, visibilidade, responsividade e ausência de violações axe.
Testes usam dados sintéticos, nunca tarefas reais/pagas para decorar a interface.
