# Entregas e evidências

## V0.1 — base local funcional
- API FastAPI, autenticação de proprietário único, projetos, tarefas, transições manuais e eventos persistentes.
- Painel Next.js com visão geral, projetos, tarefas, papéis dos agentes, histórico, relatório JSON e estado das integrações.
- SQLite local; caminho PostgreSQL privado configurável, ainda sem homologação Supabase.
- Skills locais revisadas, AGENTS.md, arquitetura, instalação Windows, lockfiles e CI.

### Verificação local
- Python 3.12.15 / Node 24.16.0.
- `pytest services/api/tests/test_api.py -q`: 16 testes aprovados.
- `ruff check services/api`: aprovado após formatação, incluindo imports.
- `npm run lint`, `npm run typecheck`, `npm run build`: aprovados.
- `npm run test:e2e`: 5 testes aprovados; autenticação, CSRF, projeto/tarefa, persistência após reload, logout, 9 rotas móveis a 360px, checagem de overflow e varredura axe WCAG A/AA no login/visão geral.
- Captura de tela inspecionada localmente; conteúdo de E2E não foi semeado no banco de uso real.
- Graphify code-only: extração bem-sucedida, uso opcional e local.
- Revisão independente: corrigido desempate de eventos pelo UUID, substituído por sequenciador persistente. Teste observou falha antes e aprovação depois.

### Limitações
Agentes ainda não executam IA; papéis e modos são preparatórios. Não há gateway Codex, ferramentas GitHub, deploy Vercel, scheduler ou worker nesta versão. Não há EXE Windows. PostgreSQL e instalação em outro PC não foram testados.

Commit `600931d` publicado em `origin/main`. [CI remoto](https://github.com/igorcastro1010/ai-team/actions/runs/40622338992) concluído com sucesso no Ubuntu, incluindo pytest, lint, typecheck, build e E2E. Repositório confirmado privado.

### Próximo marco
V0.2: LangGraph, fila persistente, executor Codex com autenticação própria e limites. A escolha do usuário foi Codex oficial com login próprio. Nenhuma sessão ou credencial do Desktop pode ser copiada.

### Preparação de credenciais
Adicionado comando próprio de login e status. Dois testes adicionais verificam ambiente filtrado, contexto separado e armazenamento obrigatório em keyring (18 testes no total). Probe real `login status` retornou `Not logged in` no contexto AI TEAM, confirmando ausência de herança automática do Desktop. Fluxo de dispositivo iniciado para interação do proprietário; autenticação e inferência não declaradas funcionais antes de sua conclusão.
