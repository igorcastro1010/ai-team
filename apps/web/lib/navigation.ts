export const views = {
  overview: { label: "Visão geral", title: "Sua sala de operações.", description: "Um lugar para pensar, coordenar e fazer acontecer." },
  ceo: { label: "Conversa com CEO", title: "Toda entrega começa com uma conversa.", description: "Dê contexto, defina a direção e acompanhe o plano." },
  projetos: { label: "Projetos", title: "Ideias com endereço.", description: "Cada projeto reúne uma direção, um time e o próximo passo." },
  tarefas: { label: "Tarefas", title: "Do plano à entrega.", description: "O trabalho do time, etapa por etapa. Atualizações manuais nesta versão." },
  agentes: { label: "Agentes", title: "Papéis claros. Trabalho em equipe.", description: "Conheça as responsabilidades e os limites de cada especialista." },
  execucoes: { label: "Execuções", title: "Cada execução, à vista.", description: "Acompanhe a fila, o andamento e os resultados dos agentes." },
  aprovacoes: { label: "Aprovações", title: "As decisões continuam suas.", description: "Revise ações que precisam de autorização antes da execução." },
  historico: { label: "Histórico", title: "Nada se perde no caminho.", description: "Projetos, tarefas e decisões em uma trilha de auditoria." },
  relatorios: { label: "Relatórios", title: "Clareza para o próximo passo.", description: "Uma leitura objetiva do trabalho e do uso da plataforma." },
  integracoes: { label: "Integrações", title: "Conexões com propósito.", description: "Saiba o que está disponível e o que ainda precisa ser validado." },
} as const;
export type View = keyof typeof views;
