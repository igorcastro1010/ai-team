# Skills e pesquisa — 27/10/2026

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
