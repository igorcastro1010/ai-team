# V0.9 — Fábrica de Conteúdo

Branch `codex/ai-team/v09-content-factory`, base V0.8.1 `c22b22e` (PR #14). A interface integrada do PR #15 permanece preservada em branch separada; sem merge.

Plano: produção persistente por projeto e chave idempotente; worker de vídeo existente avança CEO, PESQUISADOR, DESIGNER, DEV, QA e CEO por checkpoints curtos. LangGraph despacha etapas determinísticas locais, sem inferência. Aprovação por digest antecede a criação/autorização do VideoJob existente. QA verifica o MP4 real antes da entrega. Cancelamento revoga leases; falhas retomáveis exigem ação explícita. UI automática principal, editor anterior em modo avançado. Corrigir fade que deixa a prévia preta no instante zero.

Testes direcionados por entrega; suíte completa no CI, commits explícitos e PR empilhado na V0.8.1. Nenhum deploy, merge, publicação ou inferência externa. Logo FORTALAKA ainda não fornecida nesta solicitação: não procurar em outros projetos nem fabricar uma logo; preparar o fluxo e registrar essa pendência na homologação do exemplo.

## Estado de retomada

Implementados: tabela privada, LangGraph por etapa com checkpoints SQL, validação de requisitos e roteiro local persistido, mídias isoladas, revisão/CAS, aprovação por digest, fila FFmpeg, QA real, recuperação limitada, cancelamento e projeção no escritório. `/videos` oferece modo automático principal e avançado preservado; prévia pausada corrigida. Versão 0.9.0.

Commits enviados até aqui: `35fec1c`, `1dd2095`, `9f6bc84`, `ccf1f08`, `5622fd5`, `e887496`. Documentação em `docs/v09-content-factory.md`. Localmente: 33 testes Python direcionados passaram; oito testes do módulo da fábrica revalidados após persistir planos concretos. Playwright: fluxo real com escritório, imagem decodificada/prévia visível, revisão, recarga, aprovação e MP4, mais privacidade/CSRF passaram; dois testes avançados anteriores passaram. Lint, typecheck e build passaram; conferir novamente o HEAD no CI antes de concluir.

Próximos passos: publicar documentação, abrir PR empilhado na V0.8.1, conferir CI completo (incluindo teste PostgreSQL novo e runtime Docker existente), corrigir regressões de escopo e registrar evidências no PR. Reiniciar apenas os serviços locais próprios quando não houver renderização ativa, para carregar API/worker V0.9. Não iniciar inferência ou fazer merge/deploy. Logo real FORTALAKA e ARM64 físico continuam pendentes; fixture técnica não é a logo do usuário. Ao terminar, desativar a retomada de 08:49 e informar pendências reais.
