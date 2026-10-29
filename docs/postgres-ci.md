# Compatibilidade PostgreSQL no CI

O workflow `.github/workflows/postgres-integration.yml` executa cinco testes com
PostgreSQL real em serviço descartável do GitHub Actions. As credenciais são
sintéticas, exclusivas do CI; não há provisionamento hospedado, inferência ou Telegram.
A API FastAPI é exercitada em processo com seu banco PostgreSQL real; não há
engine, transação ou resposta do banco simulada.

## Serviço oficial e isolamento

Imagem oficial `postgres:17.11-bookworm`, fixada no índice SHA-256
`839fbb5a4942a7758dd93e18b42ea5649807491a0545b5eeeb8f0b8bb11857a5`.
O digest foi resolvido no registro oficial e conferido contra o hash da resposta
em 29/10/2026; o manifesto Linux amd64 corresponde a
`2cd2c0f809604aaeff6f0ec8f40aecbd025613107561015c69369a1a7f1d3416`.
A origem é a [imagem oficial PostgreSQL](https://hub.docker.com/_/postgres).
O major 17 está suportado segundo a
[política oficial de versões](https://www.postgresql.org/support/versioning/).
Revisar suporte, patch e digest antes de atualizações.

O serviço cria exclusivamente `ai_team_ci`, sem volume persistente do usuário.
A porta publicada no runner descartável é dinâmica. O job tem permissões apenas
`contents: read`, prazo de 9 minutos, container limitado a 2 CPUs/1 GiB/128
processos e execução pytest limitada a 180 segundos. O GitHub encerra o serviço
ao finalizar o job. Não há comandos de limpeza contra bancos ou volumes externos.

O administrador do serviço cria somente o login sintético `ai_team_ci_app`, com
senha aleatória e sem superuser, criação de bancos/roles ou replicação. A aplicação
executa sob esse login; ele recebe CONNECT e CREATE apenas no banco de CI para
exercitar a inicialização real do schema. Isso testa o proprietário do schema e
seu inicializador; separar a identidade de migrações da identidade de execução
em produção ainda exige configuração específica de hospedagem.

## Guardas antes de qualquer escrita

Sem `AI_TEAM_TEST_POSTGRES_URL` explícita, todo o módulo é marcado como skipped.
Quando configurada, a suíte exige simultaneamente:

- `CI=true` e `AI_TEAM_POSTGRES_CI=fresh-ephemeral`;
- driver `postgresql+psycopg`, host loopback e nome de banco exatamente
  `ai_team_ci`, sem parâmetros de conexão fornecidos externamente;
- `current_database()` exatamente `ai_team_ci` no servidor conectado;
- ausência do schema `ai_team`, de tabelas/views de aplicação e do role de CI.

Estado preexistente encerra a suíte antes de criar role ou schema. O módulo não
executa DROP, TRUNCATE ou DELETE de preparação/limpeza; nenhum teste apaga registros.
O fluxo normal de login inclui a limpeza interna de sessões já expiradas da
aplicação, mas não há sessões expiradas ou dados de terceiros nesse banco novo.
O banco inteiro é descartado com o serviço ao final do job.

O workflow monta a URL dentro do processo, sem registrá-la no ambiente mostrado
pelo runner ou em argumentos de comandos. Não imprime URLs, senhas, cookies,
ambiente completo ou logs do banco. A senha administrativa literal é exclusiva
desse serviço descartável; nenhum GitHub Secret ou segredo de produção é usado.

## Evidência fornecida pelos testes

1. Inicialização repetida preserva proprietário, hash Argon2 e registro sentinela;
   as tabelas reais ficam sob `ai_team`. Inspeção de `pg_namespace.nspacl`, com
   `aclexplode` e grantee OID zero, verifica que PUBLIC não tem USAGE nem CREATE
   nesse schema. As consultas da aplicação usam login sem superuser.
2. Login e sessão opaca são persistidos; chamadas sem autenticação são negadas,
   origem ausente é recusada e criação de run exige consentimento. A escolha de
   executor Hermes sobrevive à reconexão; registro legado continua Codex.
   O request apenas enfileira o trabalho, com zero chamadas de modelo.
3. Dois threads com conexões reais disputam a mesma etapa: apenas uma admissão
   fica persistida, exercitando lock e índice único no PostgreSQL.
4. Observações terminais concorrentes exercitam o UPDATE com SQL CASE: tokens
   reportados preservam o maior valor, estado terminal não regride e resposta
   tardia de cancelamento não transforma conclusão em cancelamento confirmado.
5. Cancelamento local invalida o lease e impede criar uma admissão Hermes.

Todos os registros são sintéticos. A suíte não afirma RLS, conexão Supabase
hospedada, isolamento multiusuário, backup/restauração ou prontidão de produção.

## Estado em 29/10/2026

Preparação local: Ruff e compilação Python aprovados; cinco testes corretamente
skipped sem URL de CI; YAML e guardas inspecionados. Docker/PostgreSQL não foram
iniciados nesta máquina. **Compatibilidade real permanece pendente até um run
aprovado desse workflow.** Registrar URL do run e SHA antes de anunciar homologação.

Comandos locais seguros, sem configuração de conexão:

```powershell
.venv/Scripts/python.exe -m ruff check services/api/tests/test_postgres_integration.py
.venv/Scripts/python.exe -m pytest services/api/tests/test_postgres_integration.py -q
```
