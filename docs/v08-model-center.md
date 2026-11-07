# V0.8 — Central de IA com bloqueio de custo

## Uso

Abra `/modelos`, selecione o projeto e revise as preferências de cada agente.
A configuração inicia desabilitada. Criar um pedido exige consentimento e apenas
coloca uma execução textual na fila; a API não chama modelos. O worker separado
revalida autorização, elegibilidade e orçamento antes de admitir cada etapa.
O fluxo textual existente é CEO → DEV → DESIGNER → QA → CEO, mantendo as
aprovações do modo do projeto. O executor de repositório com PESQUISADOR permanece
no fluxo próprio anterior; configurar a preferência não cria etapas fictícias.
Acompanhe resultados em `/ceo` e `/execucoes`; esperas ficam em `/modelos`.

O modo automático usa Gemini para texto simples e encaminha programação ao Codex
supervisionado. O modo manual respeita a preferência explícita. Não existe fallback
pago. Hermes e Codex próprios anteriores, agendas e permissões permanecem separados;
as autorizações antigas não são ampliadas pela central.

## Gemini e elegibilidade

A implementação REST usa somente APIs oficiais do Google. Configure no ambiente
privado do servidor/worker, nunca no frontend ou em notas:

- `AI_TEAM_GEMINI_API_KEY`
- `AI_TEAM_GOOGLE_READ_TOKEN` (OAuth temporário de leitura das APIs administrativas)
- `AI_TEAM_GEMINI_PROJECT_ID`
- `AI_TEAM_GEMINI_PROJECT_NUMBER`

A conta de leitura precisa poder consultar identidade da chave, projeto e billing.
Não há fluxo OAuth Google interativo nesta versão. Token expirado, APIs indisponíveis
ou permissões insuficientes bloqueiam o uso, sem ampliar permissões automaticamente.
O botão Verificar sem inferência enfileira consultas GET para o worker. Não consome
inferência, mas exige acesso às APIs administrativas; configurar não prova conexão.

A prova exige: `keys:lookupKey` vinculado ao número configurado, Resource Manager
v3 confirmando número/ID, Cloud Billing `billingEnabled == false`, modelo disponível
com `generateContent`, e preço gratuito na tabela Standard oficial. A única opção
permitida nesta revisão é `gemini-2.5-flash-lite`, texto/JSON, uma resposta, sem
ferramentas, grounding, batch, cache pago ou geração de mídia. O catálogo foi
revisado em 06/11/2026 e expira em 14/11/2026 UTC; expiração exige revisão de código
com testes, nunca migração automática. A prova de conexão dura cinco minutos e é
revalidada antes de gerar. O proprietário deve manter billing desativado e conferir
as cotas reais no AI Studio. Dados no Free Tier podem ser usados para melhorar os
produtos Google; não envie informações sensíveis.

Referências oficiais: [preços](https://aistudio.google.com/docs/pricing),
[limites](https://ai.google.dev/gemini-api/docs/rate-limits),
[lookupKey](https://cloud.google.com/api-keys/docs/reference/rest/v2/keys/lookupKey),
[billingInfo](https://cloud.google.com/billing/docs/reference/rest/v1/projects/getBillingInfo).
Nenhum faturamento, projeto Google ou chave foi criado nesta entrega. Nenhuma
inferência Gemini foi autorizada ou executada; testes de transporte usam respostas
HTTP controladas, sem representar homologação externa.

## Admissão, consumo e recuperação

O operador confirma cotas e autoriza chamadas por até 24 horas. Limites locais:
até 2 chamadas/minuto, 10/24 horas e 40 mil tokens/minuto; podem ser reduzidos.
As admissões são serializadas no banco e compartilhadas por projeto Google entre
projetos AI TEAM; o limite diário do projeto AI TEAM também é aplicado. Não detectam
consumo de outros clientes Google. A reserva conservadora considera contexto JSON,
instruções, schema e margem de saída; bytes estimados não são tokens medidos.
Uso de entrada/saída só aparece quando reportado pelo provedor. Tokens desconhecidos
mantêm a reserva. A central reutiliza o Token Optimizer e seus orçamentos por
agente/tarefa/projeto; não apresenta economia real sem benchmark autorizado.

HTTP 429 de geração grava espera e Retry-After numérico ou data HTTP, sem encurtar
a espera. Retomada exige consentimento e revalida limites; não repete etapas já
admitidas com resultado iniciado/incerto/concluído. No máximo três admissões por
etapa. Timeout/resposta perdida após POST é incerto: revisão necessária, sem retry
silencioso. Cancelamento e revogação são verificados antes do POST e nos checkpoints.
Chamadas em andamento podem consumir tokens até o provedor responder; limites de
admissão não são um medidor remoto capaz de interromper faturamento em outro cliente.

## Codex supervisionado

A central não herda a sessão do Desktop. O CLI oficial suporta login próprio
ChatGPT, mas status local não prova cota restante nem custo incremental zero.
Por isso a central não dispara inferência Codex automaticamente. Os executores
anteriores continuam disponíveis sob suas próprias autorizações e limites.
Referência oficial: [autenticação Codex](https://learn.chatgpt.com/docs/auth).

Em `awaiting_codex`, Ver contexto para Codex mostra instruções, contexto, schema e
digest. O proprietário revisa e executa o trabalho em ambiente próprio autorizado.
A API aceita resultado manual via `POST /model-center/PROJETO/handoff/RUN` com
`{consent: true, digest: DIGEST, draft: {summary, deliverable, tasks}}`.
Use sessão autenticada/proxy com origem válida. O retorno é vinculado ao projeto,
etapa e digest; repetição/resultado antigo é recusado. Não aceita tokens reportados
manualmente como medição, nem afirma que esse resultado foi produzido pelo Codex.
Nesta versão o painel exibe o pacote; importação do resultado é pela API autenticada.

## Persistência e fronteiras

Tabelas aditivas privadas guardam políticas, idempotência, admissões, verificações
e auditoria. Nenhuma chave, token ou URL privada é persistida. SQLite serve apenas
para desenvolvimento; PostgreSQL usa o schema privado existente. Inicialize com
`python -m ai_team.cli init-db` antes de iniciar serviços em paralelo. Não há acesso
arbitrário a shell, arquivos ou rede por respostas de modelos. O sistema permanece
de proprietário único; isolamento por projeto não equivale a multiusuário.

Vídeos locais: [estúdio e limites](v08-video.md). Preparação Linux/ARM64:
[operação e volumes](v08-production.md). Evidências da release: [relatório](v08-validation.md).
