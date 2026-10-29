# Vercel — credencial própria, sem publicação

Preparação da V0.4 autorizada pelo proprietário: configurar a credencial no cofre do executor e consultar, sem publicar. O conector do Codex foi usado apenas para pesquisar documentação e consultar metadados; sua sessão não é transferida para a plataforma.

1. Abra https://vercel.com/account/settings/tokens na sua conta. Crie um token identificado como `AI TEAM`, com prazo curto e o menor escopo disponível. Prefira o projeto ai-team se ele já existir; caso contrário, escolha a equipe adequada. Evite Full Account. A credencial do provedor pode permitir leitura e escrita nesse escopo; o adaptador AI TEAM implementa exclusivamente GET.
2. Execute `powershell -NoProfile -File .\tools\setup-vercel.ps1`. Cole o token somente na entrada oculta do terminal e pressione Enter. Não envie tokens ao chat, não use argumento de linha de comando nem grave em .env.
3. O comando verifica o cofre nativo, consulta a API oficial e só então armazena a credencial em `AI TEAM / Vercel`. Não sobrescreve configuração existente nem usa fallback em arquivo. Se a consulta falhar, não salva a nova credencial.
4. Para revalidar, execute `.venv\Scripts\python.exe -m ai_team.vercel_access status`. A saída contém apenas IDs, estados e timestamps permitidos, sem token, e-mail, variáveis de ambiente ou respostas brutas.

Tokens recentes com escopo de equipe/projeto permitem à Vercel inferir a equipe; não precisam de Team ID. Para um token de conta integral que precise de equipe explícita, o módulo aceita `configure --team-id team_...`. Isso não é necessário no fluxo recomendado.

O cliente usa apenas GET `https://api.vercel.com/v10/projects?search=ai-team` e, quando encontra exatamente o projeto esperado, GET `/v7/deployments?projectId=...`. Não acompanha redirects, não acessa variáveis de ambiente, não cria projetos, não emite tokens nem publica. Projetos de nome semelhante são descartados e respostas só retornam campos permitidos. Uma credencial válida sem projeto ai-team é reportada como tal, sem inventar deploys ou criar recursos automaticamente.

Na consulta inicial do conector, nenhum projeto ai-team foi encontrado no escopo conectado. Isso não prova ausência em todas as equipes da conta. A credencial própria e as consultas reais ainda dependem do token informado pelo proprietário. Não declarar V0.4 homologada com base somente nos testes simulados.

Fontes oficiais: [access tokens e escopos](https://vercel.com/docs/accounts/access-tokens), [projetos](https://vercel.com/docs/rest-api/projects/retrieve-a-list-of-projects), [deploys](https://vercel.com/docs/rest-api/deployments/list-deployments). Skills Vercel de ambiente/CLI consultadas; segredos em arquivo e publicação não foram habilitados.
