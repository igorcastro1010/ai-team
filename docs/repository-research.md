# Padrões dos repositórios consultados

Consulta somente leitura em 27/10/2026. Nenhum checkout existente foi alterado.

| Projeto | Arquivo consultado no GitHub | Evidência | Aplicação aqui |
|---|---|---|---|
| Fortalaka | `package.json`, branch master | Next.js 16.3.8, React 19.2.8, Supabase, TypeScript, ESLint | App Router, TypeScript estrito, API protegida e UI responsiva |
| Bambu AI Studio | `pyproject.toml`, branch master | Python 3.12, pytest, dependências fixadas, CLI própria | Python 3.12 isolado, testes e comando administrativo |
| VestLink | `requirements.txt`, branch main | Django, psycopg, PostgreSQL, armazenamento separado | Persistência SQL e separação de frontend/serviços |

O inventário do GitHub também confirmou repositórios privados e convenções main/master. Este novo projeto usa main e não reutiliza remotes, bancos ou credenciais dos outros projetos.

## Compatibilidade verificada
- Node 24.16.0 instalado; Next.js 16.4.3 requer Node >=20.9.0.
- React/React DOM 19.3.1 resolvidos em conjunto pelo npm.
- Python 3.12.15 disponível via uv. Python 3.14 global não é usado no projeto.
- Resolução Python feita pelo uv e versões fixadas em `services/api/requirements.lock`; build e testes registrados por release.
