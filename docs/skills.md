# Skills e pesquisa — 27/10/2026

## V0.9 — fábrica local supervisionada

Find Skills e catálogo já revisados reutilizados, sem instalar skills ou pacotes.
SKILL.md locais de LangGraph fundamentals/persistence, Supabase Postgres, UI/UX
Pro Max, React e Playwright aplicados ao pipeline e editor. LangGraph é um
despachante determinístico por etapa; persistência e aprovação ficam no SQL
existente, sem alegar checkpoint nativo nem inferência Hermes/Codex. Origem e
limitações das skills continuam nas seções anteriores. Testes e QA são técnicos,
não revisão humana ou validação da logo real do proprietário.

## Revisão V0.7 — 05/11/2026

Find Skills e leaderboard skills.sh consultados; `npx skills find obsidian --owner kepano`
localizou `kepano/obsidian-skills@obsidian-markdown` (94,8 mil instalações na consulta).
SKILL.md lido na origem oficial `github.com/kepano/obsidian-skills`, somente leitura,
sem instalar/rodar conteúdo remoto. Utilidade: Markdown/wikilinks compatíveis; não
fornece isolamento nem sincronização, implementados e testados pelo AI TEAM.

Skills locais lidas: TDD e depuração/verificação (Superpowers), LangGraph fundamentals,
Supabase Postgres, segurança de prompts, UI/UX Pro Max, React/Vercel e Playwright.
Nenhuma nova skill foi instalada. A identidade existente prevalece sobre sugestões
visuais genéricas. Graphify instalado 0.9.93 foi validado em corpus sintético offline;
nenhum hook, extração semântica ou provedor de inferência foi acionado.
Fontes e limites: [V0.7](v07-memory-optimizer.md) e [Graphify](v07-graphify.md).

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

## V0.6.1 — estabilização

Find Skills executado com `npx skills find hermes --owner nousresearch`;
nenhuma instalação adicional. Revisados o hub oficial NousResearch (MIT), sua
referência `security-privacy.md` e o redator oficial `agent/redact.py`.
Origem: https://github.com/NousResearch/hermes-agent/tree/main/skills/autonomous-ai-agents/hermes-agent.
O runtime continua fixado por digest; descoberta não autoriza ferramentas novas.

Aplicadas skills existentes: TDD (RED/GREEN nas correções), revisão independente
somente leitura, verificação antes de concluir, segurança de prompts, LangGraph
fundamentals, Supabase Postgres, Playwright, UI/UX Pro Max e React/Next.js.
Inspeções e testes não equivalem a inferência Hermes homologada. Limites e
resultados reais: [relatório V0.6.1](v061-stabilization.md).

### Homologação final V0.6.1

Find Skills consultado novamente na origem oficial NousResearch; nenhuma skill
instalada. Aplicadas TDD, investigação sistemática, revisão independente,
LangGraph, segurança, Playwright e PostgreSQL. Consultados a referência oficial
Hermes de proteção de segredos e RFC 9110 sobre Retry-After. A própria imagem
oficial executa a regressão de redator/JSON; não se desliga a proteção.
O [relatório final](v061-final-homologation.md) distingue inferência real,
testes de contrato, CI e publicação externa ainda não autorizada.

## V0.7.1 — homologação final

Find Skills: catálogo skills.sh consultado novamente; reutilizadas as skills
locais já revisadas, sem instalação adicional ou ampliação de ferramentas.
TDD, investigação sistemática e verificação antes de concluir (obra/superpowers):
regressões vermelhas e verdes para concorrência, respostas antigas, busca vazia,
reexportação e encoding Windows. Segurança de prompts: dados recuperados sem
autoridade, cache e propostas sem credenciais conhecidas. LangGraph fundamentals:
revisão dos contratos existentes, sem mudar o grafo nesta rodada.

React/Vercel e documentação Next.js incluída na versão instalada: controle de
respostas assíncronas e fronteira client/server. UI/UX Pro Max e Playwright:
revisão explícita, foco, teclado, estados e testes do painel. Supabase Postgres:
testes existentes no schema privado descartável; nenhuma migração nova.
Limitações: skills não certificam segurança nem homologam integrações; revisão
independente nesta rodada é automatizada, não humana. Ver evidências V0.7.1.

## V0.8 — central e vídeo local

Reutilizadas Find Skills (catálogo skills.sh, sem instalação adicional), TDD e
verificação antes de concluir de obra/superpowers; revisão de segurança de prompts,
Supabase Postgres, UI/UX Pro Max, React/Next.js e Playwright já revisadas localmente.
Foram consultadas as referências oficiais Google Gemini/API Keys/Cloud Billing,
autenticação Codex e FFmpeg. Não foram instaladas skills obtidas de respostas de
modelos ou hooks. O vídeo usa FFmpeg local com argumentos fixos; não chama Veo ou
API de mídia paga. Skills orientam desenvolvimento e testes, não provam elegibilidade
de cobrança, integração externa ou revisão humana. Nenhuma nova permissão de
runtime foi concedida a agentes por esta descoberta.

## V0.8.1 — editor local de vídeo

Find Skills: catálogo skills.sh consultado; reutilizadas skills locais revisadas,
sem instalar pacote/skill adicional. Superpowers TDD e plano por módulos com
subagent-driven-development; UI/UX Pro Max, React/Vercel e Playwright para editor,
preview, autosave e fluxos. Supabase Postgres para tabelas aditivas, CAS e testes
privados. Revisão independente automatizada limitada ao novo pipeline de mídia;
não é revisão humana nem revisão geral das versões anteriores. Remotion foi
consultado como referência de editor, mas o runtime permanece FFmpeg existente,
sem dependência/licença/serviço de renderização adicional. Referências técnicas:
https://ffmpeg.org/ffmpeg-filters.html e https://skills.sh/.
