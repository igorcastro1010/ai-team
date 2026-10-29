# Vercel — credencial própria, sem publicação

Preparação da V0.4 autorizada pelo proprietário: configurar a credencial no cofre do executor e consultar, sem publicar. O conector do Codex foi usado para documentação, metadados e criação do projeto vazio após autorização específica; sua sessão não é transferida para a plataforma. As consultas da plataforma usam a credencial própria do cofre.

1. Abra https://vercel.com/account/settings/tokens na sua conta. Crie um token identificado como `AI TEAM`, com prazo curto e o menor escopo disponível. Prefira o projeto ai-team se ele já existir; caso contrário, escolha a equipe adequada. Evite Full Account. A credencial do provedor pode permitir leitura e escrita nesse escopo; o adaptador AI TEAM implementa exclusivamente GET.
2. Execute `powershell -NoProfile -File .\tools\setup-vercel.ps1`. Cole o token somente na entrada oculta do terminal e pressione Enter. Não envie tokens ao chat, não use argumento de linha de comando nem grave em .env.
3. O comando verifica o cofre nativo, consulta a API oficial e só então armazena a credencial em `AI TEAM / Vercel`. Não sobrescreve configuração existente nem usa fallback em arquivo. Se a consulta falhar, não salva a nova credencial.
4. Para revalidar, execute `.venv\Scripts\python.exe -m ai_team.vercel_access status`. A saída contém apenas IDs, estados e timestamps permitidos, sem token, e-mail, variáveis de ambiente ou respostas brutas.

Tokens recentes com escopo de equipe/projeto permitem à Vercel inferir a equipe; não precisam de Team ID. Para um token de conta integral que precise de equipe explícita, o módulo aceita `configure --team-id team_...`. Isso não é necessário no fluxo recomendado.

O cliente usa apenas GET `https://api.vercel.com/v10/projects?search=ai-team` e, quando encontra exatamente o projeto esperado, GET `/v7/deployments?projectId=...`. Não acompanha redirects, não acessa variáveis de ambiente, não cria projetos, não emite tokens nem publica. Projetos de nome semelhante são descartados e respostas só retornam campos permitidos. Uma credencial válida sem projeto ai-team é reportada como tal, sem inventar deploys ou criar recursos automaticamente.

## Homologação e vínculo
Após a configuração da credencial, o proprietário autorizou criar o projeto vazio `ai-team` na equipe `igorcastro1010-8396's projects`. Projeto criado: `prj_TTusfK33t3xeYZsuozIzJytSdCXL`, equipe `team_cQVpAONaQOgTakETKfyhcUtC`. Sem Git conectado, variáveis, domínios ou deployment. O conector foi usado somente no provisionamento explicitamente autorizado; as consultas da plataforma usam a credencial própria.

O comando `.venv\Scripts\python.exe -m ai_team.vercel_access bind-team --team-id TEAM --project-id PROJECT` verifica o vínculo por GET e só depois atualiza esses metadados no cofre, preservando o token. Nas consultas futuras, um projeto de mesmo nome e ID diferente é bloqueado. Não se interpreta nome igual como autorização para outro recurso.

Em 28/10/2026, a consulta real via API autenticada do AI TEAM confirmou o ID autorizado e uma lista vazia de deploys. Persistência e leitura posterior pelo workspace foram verificadas em banco sintético; a observação sanitizada também foi salva no workspace local, sem criar usuário ou senha. Evidência em `artifacts/vercel-smoke.json` (ignorada no Git).

No painel Integrações, o botão **Consultar Vercel** exige sessão e origem autorizada. Atualiza a observação persistida e a trilha de auditoria; não executa publicação. O polling do workspace lê o banco, sem novas consultas ao provedor. A data exibida informa o instante da observação, não disponibilidade atual garantida.

A consulta de uma lista vazia está homologada; estados de deploy com itens foram testados com respostas simuladas. Não se afirma ter validado um deploy real ou hospedagem pública. Para produção ainda faltam API/worker acessíveis com segurança, Supabase/Postgres homologado e autorização específica para publicação.

Fontes oficiais: [access tokens e escopos](https://vercel.com/docs/accounts/access-tokens), [projetos](https://vercel.com/docs/rest-api/projects/retrieve-a-list-of-projects), [deploys](https://vercel.com/docs/rest-api/deployments/list-deployments). Skills Vercel de ambiente/CLI consultadas; segredos em arquivo e publicação não foram habilitados.
