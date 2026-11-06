# Gemini V0.8: contrato privado e bloqueios

O adaptador `services/api/ai_team/gemini.py` usa REST oficial com httpx. Não
ativa faturamento, não usa fallback pago, não procura credenciais do Desktop e
não executa shell, arquivos, ferramentas, grounding, cache, batch, Veo ou mídia.
Somente texto e `gemini-2.5-flash-lite` estão admitidos. A revisão de elegibilidade
é de 06/11/2026 e expira ao fim de 13/11/2026 UTC; após isso, bloqueia até revisão
explícita do código. Outros modelos, inclusive aliases Flash, são bloqueados.

## Configuração e uso

Somente o servidor recebe `AI_TEAM_GEMINI_API_KEY`, `AI_TEAM_GOOGLE_READ_TOKEN`,
`AI_TEAM_GEMINI_PROJECT_ID` e `AI_TEAM_GEMINI_PROJECT_NUMBER`. O token Google é
OAuth separado, fornecido explicitamente com acesso de leitura necessário;
nenhuma sessão ou credencial do Codex é herdada. Não registre as variáveis.
O construtor aceita alternativamente dicionário privado com `api_key`,
`read_token`, `project_id`, `project_number`. `client` injetado é dependência
confiável do aplicativo/testes, nunca argumento vindo de modelos.

`check(model='gemini-2.5-flash-lite')` faz apenas GET:

1. `keys.lookupKey` vincula a chave ao número do projeto e exige recurso não vazio.
2. Resource Manager `projects.get` vincula o número ao projectId configurado.
3. `projects.getBillingInfo` exige projectId idêntico e billingEnabled literalmente false.
4. `models.get` exige o modelo exato com suporte a generateContent.
5. A página oficial de preços deve responder HTTP 200 e comprovar entrada e saída
   gratuitas na seção Standard do modelo. Mudança de formato ou redirecionamento bloqueia.

Retorna status `verified`, `project_key` como número do projeto, `model`,
`verified_at` e `expires_at` ISO UTC. A evidência vale no máximo cinco minutos,
sem substituir quotas, consentimento ou validação no executor. Cada geração
repete todos os GET imediatamente antes do POST, mesmo com check anterior.

`generate(role, instructions, context, on_tick, authorized=False)` exige o
argumento booleano `authorized=True`, reservado à integração que já validou
consentimento e reservou quota. Sem isso, não faz rede. A resposta JSON deve
validar DraftContent, sem campos extras ou ferramentas; o contexto não confiável
fica no conteúdo de usuário, separado das instruções de sistema.

O cliente padrão ignora proxies do ambiente, bloqueia redirects e não repete
inferência. Há limites de contexto, saída, bytes e tempo por request. Timeout,
falha de transporte ou 5xx após envio produzem `GeminiUncertain`: o executor deve
tratar como possível consumo, sem repetir automaticamente. 429 produz
`GeminiRateLimited(retry_after)`. Outros bloqueios usam `GeminiBlocked(reason)`
com razões fixas, sem corpo remoto, URL bruta, chave ou token nas mensagens.
Contagens ausentes de uso retornam zero como desconhecidas; não constituem
medição de consumo ou economia. Contagens reportadas de saída incluem thinking.
O callback de cancelamento é consultado antes e depois dos GETs de verificação.
O endpoint lookupKey exige a chave na query por contrato Google; não habilite
logs HTTP de requisições contendo credenciais.

## Fontes e limites da evidência

Consulta pública em 06/11/2026, sem autenticação ou inferência:

- [Preços oficiais](https://aistudio.google.com/docs/pricing): HTTP 200 Markdown,
  seção Gemini 2.5 Flash-Lite / Standard com entrada e saída grátis. O endereço
  antigo ai.google.dev/gemini-api/docs/pricing redirecionou para esse endereço;
  o adaptador usa diretamente a URL final, sem seguir redirects.
- [lookupKey](https://docs.cloud.google.com/api-keys/docs/reference/rest/v2/keys/lookupKey):
  requer apikeys.keys.lookup e escopo OAuth apropriado; retorna parent e name.
- [getBillingInfo](https://docs.cloud.google.com/billing/docs/reference/rest/v1/projects/getBillingInfo):
  requer resourcemanager.projects.get e escopo aceito de Cloud Billing/Cloud Platform.
- [Resource Manager projects.get](https://docs.cloud.google.com/resource-manager/reference/rest/v3/projects/get):
  leitura autenticada que vincula o número de projeto ao ID.
- [generateContent](https://ai.google.dev/api/generate-content) e
  [saída estruturada](https://ai.google.dev/gemini-api/docs/structured-output).

A camada gratuita pode usar conteúdo para melhorar os produtos Google, conforme
os [termos oficiais](https://aistudio.google.com/docs/terms). Não enviar dados
sensíveis. Modelo listado e configuração preenchida não comprovam gratuidade.
As verificações são conservadoras; indisponibilidade ou dúvida impedem geração.
Quotas e aprovação pertencem à central/executor e não são comprovadas por este
adaptador isolado. Não há evidência de conexão autenticada real ou inferência
real nesta entrega: todos os contratos autenticados foram exercitados com
httpx.MockTransport. Mudança remota de faturamento entre check e POST continua
sendo limite externo; não habilitar billing no projeto dedicado.
