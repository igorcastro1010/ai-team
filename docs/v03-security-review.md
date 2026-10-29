# V0.3 — execução GitHub supervisionada

## Fronteiras
- A chave privada é lida do keyring nativo. Não se usa o token do gh, OAuth do Desktop ou credencial no navegador. JWT RS256 curto; tokens de instalação só em memória.
- Antes de cada escrita, o executor verifica a App e a instalação. Deve ser seletiva, ativa, sem permissões extras e conter exatamente o repositório privado `igorcastro1010/ai-team`. O token de escrita limita também `repository_ids` e a permissão da operação.
- Propostas são dados Pydantic estruturados, nunca comandos. Campo extra, operação não prevista, SHA inválido, main, path traversal, arquivo oculto e caminho fora de docs/agent-output são rejeitados. O modelo de IA não recebe token nem acesso direto à API GitHub.
- O conteúdo é imutável e possui digest; decisão só muda pending para approved/rejected por CAS. O worker revalida política e digest antes de instanciar o cliente. Modos automático e supervisionado não dispensam essa aprovação.
- Claim possui token e lease de cinco minutos. Expiração marca resultado incerto; não reexecuta. Persistência e chamadas externas usam transações separadas. Finalização e expiração têm condições contra concorrência.
- Commits usam blob/tree/commit com pai revisado e update de ref com force=false. Isso rejeita atualização concorrente sem sobrescrever trabalho. PR confere o SHA antes do POST e na resposta; corrida preserva URL e marca uncertain para revisão.
- Nenhum endpoint expõe merge, delete, permissões administrativas, pagamentos ou deploy. Request Origin, cookie opaco e rotas permitidas do proxy continuam exigidos.

## Revisão e regressões
Revisão independente encontrou head de PR mutável e starvation do worker textual. Testes reproduziram as falhas; agora SHA é obrigatório para PR, ambas as filas são atendidas em cada ciclo e chamadas GitHub atualizam heartbeat. E2E detectou a nova rota bloqueada no proxy; a allowlist foi atualizada sem proxy genérico. Propostas ativas são consultadas separadamente dos últimos 200 resultados, para não desaparecerem atrás do histórico.

## Evidência externa
Em 28/10/2026, a App própria validou a instalação 176042197 somente no ai-team. O fluxo real autenticado criou branch `codex/ai-team/smoke-d009c535f7`, commit `6f48aafb02d5aaceb493a6aac2ab1201b5faed5c`, issue #3 e PR #4, usando quatro processos worker e banco sintético. Nenhum merge ou deploy foi realizado. O cenário anterior deixou issue #1 e PR #2 após diagnóstico manual; são recursos sintéticos preservados, sem repetição automática do job incerto.

O diagnóstico real mostrou HTTP 422 ao criar PR privado com token somente pull_requests:write. Acrescentar contents:read ao token restrito permitiu ler a branch e abrir o PR. A regressão verifica esse escopo mínimo no cenário homologado. Não se afirma que o rascunho está homologado: o smoke usou PR normal, pois a disponibilidade de drafts depende do plano do GitHub.

## Limitações
Commits operacionais estão limitados a documentos Markdown em uma pasta específica. Não há checkout de projeto, execução de código proposto ou transferência automática do DEV para GitHub. Um PR aberto continua sujeito a alterações posteriores na branch; cabe à revisão no GitHub decidir qualquer merge, fora desta plataforma. Homologação Supabase/Postgres, credencial Vercel própria, hospedagem pública e empacotamento Windows permanecem pendentes. Testes não substituem isolamento de sistema operacional para executar código arbitrário; esse recurso não foi habilitado.
