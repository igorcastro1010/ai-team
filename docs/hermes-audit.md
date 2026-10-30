# Auditoria Hermes — 29/10/2026

## Base preservada

Revisão inicial: `e91f38e467bf763481767c77e4613b551e1f82e7` de
`igorcastro1010/ai-team`. Regras lidas: AGENTS.md da raiz e apps/web/AGENTS.md.
Next.js/React/TypeScript no painel; FastAPI, SQLAlchemy e LangGraph na API.
Worker e scheduler separados. SQLite local; PostgreSQL privado em produção.
Autenticação de proprietário único, CSRF por Origin, sessões revogáveis,
aprovações vinculadas à etapa e GitHub App restrita ao próprio repositório.
Codex oficial com login próprio e Vercel somente leitura já existem.

Não substituir banco, autenticação, fila, agendamentos ou executor Codex.
Não ampliar permissões da GitHub App nem habilitar merge/deploy.

## Fontes oficiais e compatibilidade

Código Hermes consultado no commit
`e298669b44ce032a995c8a67ceae025801b0f4bf` (main em 29/10/2026).
Imagem oficial: `nousresearch/hermes-agent`; estado em `/opt/data`.
O runtime Hermes usa Python 3.14 e deve ficar separado do Python 3.12 da API.

- [Docker](https://hermes-agent.nousresearch.com/docs/user-guide/docker)
- [API oficial](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server)
- [Bot Mode](https://hermes-agent.nousresearch.com/docs/user-guide/bot-mode)
- [Telegram](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram)
- [Código oficial](https://github.com/NousResearch/hermes-agent/tree/e298669b44ce032a995c8a67ceae025801b0f4bf)
- [Codex como plataforma](https://developers.openai.com/blog/codex-as-a-platform)

Reutilizar API Server, Runs, eventos, stop, approval, perfis, subagentes e cron
do Hermes. Bot Mode é a apresentação de perfis, não sete processos simulados.
A API pode executar ferramentas; instrução textual de segurança não é sandbox.
A integração básica deve recusar ferramentas habilitadas antes de inferência.

## Decisões de implementação

Integração adicional e opt-in. Gateway em Compose, sem porta Hermes publicada;
API e worker AI TEAM compartilham rede privada com ele. Volume independente,
logs rotacionados, health check e reinício. Nenhum socket Docker, checkout,
credencial Codex/GitHub ou banco AI TEAM é montado no Hermes.

Começar com inspeção autenticada de capacidades e execução textual restrita,
preservando supervisão existente. Habilitar ferramentas, Telegram, bots nativos
e código exige homologação específica; não declarar essas fases concluídas
com base em testes com doubles.

## Condições encontradas nesta máquina

Checkout local estava vazio; histórico existente recuperado do origin.
Docker não localizado no PATH. Não foi aberto ou copiado cofre de credenciais.
Nenhum provedor, bot Telegram ou infraestrutura paga foi provisionado.
Homologação real exige runtime Hermes disponível e configuração própria.
