# Projetos Next.js com build e testes

## Usar no Windows

Requisitos: API/painel/worker nativos, Docker Desktop com engine Linux e executor
próprio autenticado. A preparação abaixo baixa dependências somente na criação
da imagem revisada; não recebe arquivos nem credenciais de outros projetos.

```powershell
.venv\Scripts\python.exe tools/setup_next_sandbox.py
powershell -NoProfile -File .\tools\start.ps1
```

1. Selecione um projeto em **Conversa com CEO**.
2. Escolha **Projeto Next.js com build e testes** em **Tipo de entrega**.
3. Descreva uma página pequena em português e autorize o envio ao executor.
4. CEO planeja, DEV gera TSX, DESIGNER gera CSS e QA propõe critérios do HTML
   e cenários de interação quando aplicáveis.
5. Revise fontes, CSS, critérios e SHA-256. O ZIP inclui o scaffold fixo completo.
6. Clique em **Aprovar build e testes** e confirme a autorização. Esta aprovação
   é obrigatória também no modo automático, vinculada ao conteúdo e à execução.
7. O worker faz build, valida HTML e executa os cenários de navegador incluídos.
   Depois o CEO consolida o resultado real.
   Baixe em **Baixar projeto Next.js**. O escritório acompanha QA e CEO.

O projeto gerado é novo e independente. Nenhuma edição de repositório, push,
publicação ou ampliação da GitHub App é feita por essa entrega.

## Contrato e isolamento

- Scaffold fixo: Next.js 16.4.3, React 19.3.1, TypeScript 5.9.3 e Node 24.
  `package-lock.json`, scripts, layout e configurações pertencem ao servidor.
  Não há pacotes extras escolhidos pelo modelo nem instalação durante tarefas.
- DEV: `app/page.tsx` e componentes simples em `components/`; DESIGNER:
  `app/globals.css`; QA: `tests/acceptance.json`, entre 1 e 12 verificações
  declarativas de status, texto obrigatório e texto proibido. Nenhuma URL ou
  comando QA é aceito. Até 18 arquivos e 256 KiB no projeto completo.
- Docker por tarefa, rede desligada, usuário 65532, raiz somente leitura,
  capabilities removidas, no-new-privileges, sem mounts, portas ou segredos.
  Recursos: 2 CPUs, 1 GiB, 128 PIDs, tmpfs 256 MiB, saída até 32 KiB e 120 s.
- A imagem é selecionada por ID imutável e fingerprint dos fontes revisados.
  A preparação usa um snapshot tar apenas desses fontes, sem contexto privado.
  Ao atualizar runtime/scaffold, prepare novamente a imagem.
- A aprovação cobre arquivos completos e fingerprint do runtime. O snapshot é
  persistido no QA: downloads e hashes históricos sobrevivem a atualizações.
  Um runtime alterado não executa uma aprovação antiga: gere nova solicitação.
- O supervisor mantém os critérios originais em memória antes de rodar build,
  exige BUILD_ID, inicia o servidor apenas dentro do contêiner e verifica a raiz
  em endereço fixo. Leitura HTML limitada a 512 KiB com UTF-8 incremental.
- Build/QA e relatório usam leases separadas: cinco chamadas de IA em seis ciclos
  de worker. O resultado persistido é reutilizado, sem repetir o build.
  Snapshot do scaffold não é enviado ao modelo no relatório.
- Cancelamento e lease expirada reutilizam a reconciliação por nome/label próprios.
  Falha ou resultado incerto não autoriza repetição automática. Nenhuma migração
  de tabelas: artefatos e resultados usam o JSON existente das etapas.

A validação cobre build, HTML inicial e os cenários de interação presentes no QA.
Navegação arbitrária, acessibilidade e comportamentos fora desses cenários exigem
revisão posterior. Critérios
propostos por IA podem ser incompletos; passar não comprova correção integral.
Docker local de proprietário único não é homologação para código hostil em um
serviço público multiusuário. Workers Compose não recebem o socket Docker;
o executor homologado aqui é o worker nativo Windows.

## Verificação

```powershell
$env:AI_TEAM_NEXT_SANDBOX_TESTS='1'
$env:AI_TEAM_SANDBOX_TESTS='1'
.venv\Scripts\python.exe -m pytest services/api/tests -q
Remove-Item Env:AI_TEAM_NEXT_SANDBOX_TESTS, Env:AI_TEAM_SANDBOX_TESTS
npm run lint
npm run typecheck
npm run build
npm run test:e2e

# Opt-in: até cinco chamadas reais, banco descartável e página sintética.
.venv\Scripts\python.exe tools/smoke_hermes.py --real --nextjs-code
```

Evidências locais ignoradas: `artifacts/nextjs-code-smoke.json` e
`artifacts/nextjs-project-smoke.zip`. Não contêm projetos reais. O teste E2E do
painel usa provedor e sandbox simulados; o teste Docker e o smoke real são
validações separadas. Sem merge ou deploy nesta entrega.

Em 30/10/2026: suíte com opt-in Docker passou com 270 testes e 7 PostgreSQL
omitidos por ausência de banco descartável. Após acrescentar a regressão de
contexto do modelo, a suíte final sem opt-in passou com 260 testes e 18 omissões
(11 Docker e 7 PostgreSQL). Lint, typecheck, build e 22 E2E passaram.
O controlador compartilhado foi exercitado com isolamento, cancelamento, saída
excessiva e watchdog; o runtime Next passou build/HTML positivo, texto ausente
e saída zero prematura. Revisão independente confirmou as correções de histórico
e UTF-8 sem outro impedimento concreto no escopo revisado.

Smoke final real: cinco chamadas Hermes próprio, build e critérios HTML
aprovados, relatório concluído; uso reportado de 31.322 tokens de entrada e
3.642 de saída, sem custo monetário confirmado. Em seguida foi testado o filtro
que mantém o snapshot do scaffold fora do contexto do modelo, reduzindo contexto
desnecessário. Esse filtro foi verificado por teste de contrato, sem outra rodada
de inferência. O teste manual do proprietário permanece para depois.

PR incremental: [#7](https://github.com/igorcastro1010/ai-team/pull/7), sobre a
entrega Python [#6](https://github.com/igorcastro1010/ai-team/pull/6). Testes
locais não substituem o resultado do CI; consulte os checks da revisão.

Referências: [instalação oficial Next.js](https://nextjs.org/docs/app/getting-started/installation)
e [isolamento Docker](https://docs.docker.com/reference/cli/docker/container/run/).

## QA no Chromium — 31/10/2026

Para páginas interativas, descreva também o comportamento esperado. Exemplo:
`Crie um formulário com label Nome, botão Salvar e mensagem Olá, Igor depois de
preencher Igor e salvar.` QA pode acrescentar `browser_checks` ao mesmo
`tests/acceptance.json`. Revise esses critérios antes de aprovar.

```json
{
  "checks": [{"name": "titulo", "contains": "AI TEAM"}],
  "browser_checks": [{
    "name": "salvar nome",
    "actions": [
      {"action": "fill", "label": "Nome", "value": "Igor"},
      {"action": "click", "role": "button", "name": "Salvar"}
    ],
    "expect_text": "Olá, Igor"
  }]
}
```

Até 6 cenários, cada um com 1–6 ações e resultado visível exato. Click usa role
`button`, `link` ou `checkbox` e nome acessível exato; fill usa label exata e
valor de até 500 caracteres. Não aceita scripts, selectors, comandos nem URLs.
Cada cenário começa na raiz fixa em contexto novo a 390x844; não herda sessão.
Sem browser_checks, a entrega continua validando somente HTML.

Playwright oficial 1.64.1 e Chromium Headless Shell são instalados em diretório
separado ao preparar a imagem; não entram nas dependências do ZIP gerado.
Execute novamente `tools/setup_next_sandbox.py` ao atualizar o runtime.
O navegador tem prazo total de 30 s dentro dos 120 s existentes. Destinos fora
do próprio servidor, downloads, popups, service workers e WebSockets são
bloqueados. Operações bloqueadas invalidam o cenário.

Chromium roda sem sandbox interno dentro do contêiner Docker restrito já
documentado. Não foram adicionados capabilities, IPC host, portas ou mounts.
Temporários ficam no tmpfs privado. Esta composição continua exclusiva para
desenvolvimento local do proprietário; não visitar sites externos nem oferecer
execução de código hostil como serviço público.

A saída distingue verificações HTML e `browser_check`/`browser_failures`.
Um build aprovado sozinho não comprova interação; o relatório CEO deve citar
somente os cenários efetivamente executados. O painel exibe critérios e saída
em **Ver saída dos testes**, preservando aprovação por hash, download e histórico.

Referência: [Playwright oficial no Docker](https://playwright.dev/docs/docker).

Validação local em 31/10/2026: 285 pytest aprovados com Docker real, 7 casos
PostgreSQL omitidos por ausência de banco descartável. Após o último ajuste
de deadline, os 14 testes de navegador foram repetidos e aprovados. Os 22 E2E
do painel, lint, typecheck e build passaram. Docker cobriu formulário real,
estado independente entre cenários, assertiva negativa e navegação externa
bloqueada. A revisão encontrou TMPDIR somente leitura e prazo de abertura fora
do orçamento; ambos corrigidos, com teste real RED/GREEN para o lançamento.
Uma janela de expiração durante fechamento também foi fechada. Revisão final
sem outro impedimento concreto no escopo.

Smoke Hermes real: cinco chamadas, quatro checks HTML e um cenário Chromium,
zero falhas, relatório CEO concluído. Uso reportado: 15.769 tokens de entrada
e 3.811 de saída; preço monetário não confirmado. Evidências ignoradas em
`artifacts/nextjs-code-smoke.json` e `artifacts/nextjs-project-smoke.zip`.
PR incremental [#8](https://github.com/igorcastro1010/ai-team/pull/8), sem merge
ou deploy; resultado do CI deve ser consultado separadamente.
