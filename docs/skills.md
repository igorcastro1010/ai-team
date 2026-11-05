# Skills e pesquisa — 27/10/2026

## Revisão V0.6 — 04/11/2026

Find Skills local foi relida e a descoberta `npx skills find hermes --owner nousresearch`
localizou `nousresearch/hermes-agent@hermes-agent`. A skill oficial MIT, versão 3.3.0,
foi lida na origem para revisar compatibilidade, sem instalação nem execução de conteúdo
remoto. Reutilizados os adaptadores oficiais existentes de Hermes/Codex, sem dar shell,
skills ou credenciais aos modelos.

Reutilizadas LangGraph fundamentals/referência Python (nós e checkpoints no banco do
executor), Supabase (nova tabela privada com FK), segurança de prompts, UI UX Pro Max,
React/Next.js e Playwright. Superpowers orientou TDD, investigação de regressão,
verificação e revisão independente de código. OpenAI Docs e referências GitHub REST
orientaram integração e limites reais, sem endpoints inventados. Nenhuma nova skill
foi instalada. Graphify continua opcional; não é necessário ao runtime ou à homologação.

Skills são ferramentas de desenvolvimento. Não são plugins executáveis pelos agentes da aplicação.

| Capacidade | Origem revisada | Descoberta | Uso / limite |
|---|---|---|---|
| Descoberta | `find-skills`, skill local | Lida antes de `npx skills find` | Consulta do skills.sh e busca; sem instalação global |
| LangGraph | `langchain-ai/langchain-skills` (MIT) | ~18 mil instalações por skill; 1.316 stars | fundamentals, persistence e HITL instaladas; instruções e referência Python lidas para preparar V0.2 |
| PostgreSQL | `supabase/agent-skills` (MIT) | ~462 mil instalações; 2.941 stars | SKILL.md lido; schema privado, índices e conexões limitadas |
| UI/UX | `nextlevelbuilder/ui-ux-pro-max-skill` (MIT) | ~418 mil instalações; 141.612 stars | Disponível; instalada localmente; busca de design system executada. Aplicadas hierarquia, contraste, foco e responsividade. Fontes locais para evitar dependências externas |
| React / Next.js | `vercel-labs/agent-skills` | 33.115 stars | vercel-react-best-practices e web-design-guidelines instaladas e lidas. Documentação oficial Next.js consultada |
| Testes | `currents-dev/playwright-best-practices-skill` (MIT) | ~99 mil instalações; 412 stars | SKILL.md e padrões de formulários lidos; testes por role/label e escopo do dialog |
| Segurança de prompts | `github/awesome-copilot` | ~10 mil instalações na busca | ai-prompt-engineering-safety-review lida; sem acesso de agente a credenciais e sem execução de instruções de skills em runtime |
| Processo | Superpowers: using-superpowers, brainstorming, writing-plans, executing-plans, TDD, debugging, verification | Skills disponíveis no ambiente | Desenho e plano documentados; autorização de autonomia local do usuário aplicada sem gates adicionais para escolhas rotineiras |
| Codex | OpenAI Docs | Documentação oficial consultada | SDK, CLI e app-server são mecanismos documentados; sem endpoints inventados ou herança de sessão |

Os números são um retrato da descoberta, não garantia de segurança. Revisar novas versões antes de atualizar `skills-lock.json`.

## Ocorrências
`vercel-labs/next-skills` não apresentou skills válidas; `next-best-practices` não estava disponível na revisão atual de `vercel-labs/agent-skills`. Adotamos a skill oficial React e a documentação Next.js, sem recomendar uma skill ausente.

## Graphify
Binário presente no Windows. Extração `graphify . --code-only` concluída em Python/TSX/TypeScript: 698 nós e 1.432 arestas na primeira execução. Parte dos nós pertence a scripts das skills. Algumas configurações não produzem símbolos, o que limita a completude do grafo. Integração opcional por `tools/graph.ps1`, sem hooks, sem LLM e artefatos ignorados no Git.

## Fontes primárias

Na atualização do escritório em 04/11/2026, UI UX Pro Max foi consultada com
`pixel art office agents --design-system` e `motion pause reduced motion --domain ux`.
Pixel Art corresponde à referência; o padrão comercial hero e a paleta vermelha
retornados não se aplicam a este painel e não foram adotados. Usados mapa/sprites
SVG originais, paleta própria, texto legível, pausa, reduced-motion e foco.
React/Next.js e documentação local use-client orientaram os componentes; Playwright
e axe verificaram comportamento e responsividade. Superpowers orientou plano,
testes e revisão independente. Nenhuma skill ou dependência nova instalada.

Na extensão Chromium de 31/10/2026, reutilizadas Playwright Best Practices
(locators acessíveis e assertions com espera), LangGraph fundamentals/Python
(instruções por papel) e Superpowers (plano, TDD, revisão e verificação).
Playwright 1.64.1 foi revisado como dependência oficial do executor, com lock
separado; nenhuma nova skill instalada ou habilitada nos agentes. Documentação
oficial consultada para Docker, versões do navegador e limites do sandbox.

Na extensão Next.js de 30/10/2026, reutilizadas LangGraph fundamentals/Python,
Supabase (persistência no JSON existente), UI UX Pro Max, React/Next.js,
Playwright e Superpowers (plano, testes, execução inline, revisão e verificação).
Nenhuma skill adicional instalada; nenhuma habilitada no executor. A revisão
independente foi somente de código, sem chamadas de modelo, e gerou regressões
para snapshots históricos e decodificação incremental de acentos no HTML.

Na entrega Python de 30/10/2026, foram reutilizadas as skills revisadas de
LangGraph (fundamentals e referência Python), UI UX Pro Max (confirmação de
ações), React/Next.js, Playwright e Superpowers (plano, TDD, execução inline,
revisão independente e verificação). Nenhuma skill nova foi instalada ou
habilitada no runtime dos agentes. A skill Supabase foi consultada antes da
persistência; o desenho preserva tabelas e usa o JSON existente das etapas.
- [LangChain Skills](https://www.langchain.com/blog/langchain-skills)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [Next.js instalação](https://nextjs.org/docs/app/getting-started/installation)
- [Supabase conexão PostgreSQL](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Codex SDK](https://developers.openai.com/codex/sdk)
- [Codex como plataforma](https://developers.openai.com/blog/codex-as-a-platform)

## Hermes e escritório — 29/10/2026

Find Skills aplicado novamente: leaderboard skills.sh e `npx skills find hermes`.
A descoberta retornou `nousresearch/hermes-agent@hermes-agent` (~1,2 mil
instalações) e `dogfood` (~6,4 mil), além de fontes terceiras. Repositório
oficial e skill `skills/autonomous-ai-agents/hermes-agent/SKILL.md` consultados
no commit `e298669b44ce032a995c8a67ceae025801b0f4bf`. O conteúdo orienta operação
de perfis/CLI, incluindo execução interativa; não concede permissões à aplicação.
Nenhuma skill nova instalada: UI/UX Pro Max e Playwright já estão presentes e
foram lidas. Evitada instalação redundante ou de terceiros sem necessidade.

UI/UX Pro Max: busca local `agent dashboard pixel office --design-system`
produziu direção retro/pixel compatível com o pedido. Aplicados pixel art SVG
original, paleta própria, sem fontes remotas, foco visível, botões por teclado,
reduced-motion, nomes de status além de cores e layouts móveis. Orientações
de legibilidade prevalecem sobre usar fonte pixel pequena nos resultados.
Playwright e React Best Practices aplicados aos fluxos, stale state e acessibilidade.

Skills são exclusivas do desenvolvimento; Hermes não as instala nem executa.
