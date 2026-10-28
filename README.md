# AI TEAM

Sala de operações em português para projetos, tarefas e agentes de IA. Plataforma independente para navegador no Windows e futura hospedagem Web. **V0.1: controle e persistência reais; execução de IA e integrações externas ainda não habilitadas.**

## O que funciona
- Proprietário único, senha Argon2, sessão HTTP-only expirada em 12h, logout revogável e limite de login persistente.
- Cadastro de projetos, preferência de autonomia e tarefas por agente.
- Quadro com transições validadas, armazenamento persistente e histórico de auditoria.
- Visão geral, papéis dos quatro agentes, status das integrações e relatório JSON.
- Interface responsiva, formulários acessíveis e bloqueio de acesso sem login.

## Windows: instalar e abrir
Requisitos: Git, Node.js 22 ou 24 LTS e [uv](https://docs.astral.sh/uv/). Python 3.12 será localizado/instalado pelo uv.

```powershell
git clone https://github.com/igorcastro1010/ai-team.git
cd ai-team
.\tools\setup.ps1
.\tools\start.ps1
```

O instalador solicita uma senha com pelo menos 12 caracteres, sem exibí-la ou gravá-la em claro. Depois abra [localhost:3000](http://localhost:3000), usuário `admin`. Para outro nome: `ai-team create-owner --username NOME` no ambiente virtual, antes do cadastro inicial. Não existe senha padrão nem registro público.

API escuta apenas em 127.0.0.1:8000; painel em 127.0.0.1:3000. O script mantém a API oculta e encerra o processo que iniciou ao fechar o painel. O modo de desenvolvimento não é uma instalação de produção. Não há EXE ou serviço Windows instalado.

### Instalação manual / Linux
```sh
uv venv --python 3.12 .venv
uv pip sync --python .venv/Scripts/python.exe services/api/requirements.lock
uv pip install --python .venv/Scripts/python.exe --no-deps -e services/api
npm ci
.venv/Scripts/python.exe -m ai_team.cli create-owner --username admin
.venv/Scripts/python.exe -m uvicorn ai_team.main:app --host 127.0.0.1 --port 8000
# Em outro terminal:
npm run dev
```
No Linux substitua `.venv/Scripts/python.exe` por `.venv/bin/python`. Se houver restrição local a scripts PowerShell, execute os comandos manualmente; não é necessário alterar a política do sistema.

## Configuração
Copie `.env.example` para `.env` na raiz somente se precisar mudar os padrões. Arquivos `.env` são ignorados. O painel usa `AI_TEAM_API_URL` somente no servidor; em hospedagem configure-a no ambiente da Vercel. A API lê `AI_TEAM_PUBLIC_ORIGIN`, `AI_TEAM_ENVIRONMENT`, `AI_TEAM_DATABASE_URL` e `AI_TEAM_SESSION_TTL_SECONDS`.

SQLite local: `.data/ai-team.db`. Não apague este arquivo para atualizar. Backup com o serviço parado; manter também eventuais arquivos WAL até o fechamento das conexões. Nunca versionar o banco ou logs locais.

## PostgreSQL / Supabase
Use `AI_TEAM_DATABASE_URL=postgresql+psycopg://.../postgres?sslmode=require` no servidor privado. Inicialize explicitamente com `ai-team init-db`, depois cadastre o proprietário. As tabelas ficam no schema `ai_team`, sem permissão de PUBLIC. Não adicione esse schema aos expostos pelo PostgREST/Supabase Data API. O painel conversa exclusivamente com FastAPI; não recebe service_role ou senha do banco.

V0.1 oferece criação inicial de schema; ainda não migra instalações de versões futuras automaticamente. PostgreSQL/Supabase precisa de homologação real antes de hospedagem. Mudar DATABASE_URL não copia o SQLite: faça migração de dados revisada. Não presumir RLS multiusuário; a instalação é de proprietário único.

## Verificação
```powershell
.\tools\check.ps1
```
Os E2E criam banco e usuário exclusivos de teste, sob `.data/`; não usam o banco real. Chromium pode precisar de `npx playwright install chromium`. Resultados e capturas ficam ignorados pelo Git. O comando de build é separado do servidor dev; não rode os dois simultaneamente sobre a mesma pasta `.next`.

## Estrutura
```text
apps/web/           painel Next.js e E2E
services/api/       API, autenticação, banco e testes
.agents/skills/     skills locais de desenvolvimento
tools/              instalação, execução e verificação Windows
docs/               arquitetura, pesquisa, marcos e evidências
```

## Evolução e limites
- V0.1: base local funcional.
- V0.2: CEO, especialistas, LangGraph e tarefas executadas por worker.
- V0.3: GitHub com recursos permitidos e fluxo de desenvolvimento.
- V0.4: Codex e Vercel com mecanismos oficiais homologados.
- V0.5: automações, relatórios de execução e limites de uso.
- V1.0: homologação, segurança de produção e publicação autorizada.

Nenhum deploy é feito pela V0.1. Preferências de modo são persistidas, mas ainda não autorizam execução externa. Não há leitura de outros projetos, execução de shell, exclusões, pagamentos ou acesso à sessão local do Codex. Integrações planejadas aparecem como planejadas. Veja [desenho](docs/superpowers/specs/2026-10-27-ai-team-design.md), [skills](docs/skills.md) e [releases](docs/releases.md).
