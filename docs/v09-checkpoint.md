# V0.9 — Fábrica de Conteúdo

Branch `codex/ai-team/v09-content-factory`, base V0.8.1 `c22b22e` (PR #14). A interface integrada do PR #15 permanece preservada em branch separada; sem merge.

Plano: produção persistente por projeto e chave idempotente; worker de vídeo existente avança CEO, PESQUISADOR, DESIGNER, DEV, QA e CEO por checkpoints curtos. LangGraph despacha etapas determinísticas locais, sem inferência. Aprovação por digest antecede a criação/autorização do VideoJob existente. QA verifica o MP4 real antes da entrega. Cancelamento revoga leases; falhas retomáveis exigem ação explícita. UI automática principal, editor anterior em modo avançado. Corrigir fade que deixa a prévia preta no instante zero.

Testes direcionados por entrega; suíte completa no CI, commits explícitos e PR empilhado na V0.8.1. Nenhum deploy, merge, publicação ou inferência externa. Logo FORTALAKA ainda não fornecida nesta solicitação: não procurar em outros projetos nem fabricar uma logo; preparar o fluxo e registrar essa pendência na homologação do exemplo.

Estado inicial: planejamento; implementação pendente. A retomada de 08:49 deve ler este arquivo e git status sem refazer entregas.
