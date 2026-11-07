# V0.8 — preparação Linux ARM64 e operação 24/7

Esta configuração prepara API privada, worker central, scheduler e renderer local
em processos separados. Nenhuma VM, conta, serviço pago, banco de produção ou
deploy foi criado. Não oferece garantia de disponibilidade 24/7: energia, rede,
backup restaurável, disco, monitoramento e revisão operacional continuam necessários.

## Configuração privada e fronteiras

Use `compose.production.yaml` isoladamente, sem combinar com o Compose de
desenvolvimento. O host precisa de Docker Engine/Compose e arquitetura Linux ARM64;
`AI_TEAM_PLATFORM=linux/amd64` permite validação alternativa, sem provar ARM físico.
O frontend e o proxy HTTPS são externos a este arquivo. A única porta publicada é
`127.0.0.1:8000`; o proxy do host encaminha `/api` à API privada, preservando origem
e cookies seguros. `AI_TEAM_PUBLIC_ORIGIN` deve ser a origem HTTPS real do frontend.
Não usar IP público, túnel aberto ou porta 8000 exposta. A configuração da aplicação
rejeita produção sem HTTPS/PostgreSQL e usa cookies Secure.

Crie fora do repositório um arquivo de interpolação privado (exemplo sem valores
reais; caminhos Linux):

```dotenv
AI_TEAM_PRODUCTION_ENV_FILE=/etc/ai-team/runtime.env
AI_TEAM_SECRETS_DIRECTORY=/etc/ai-team/app-secrets
AI_TEAM_PUBLIC_ORIGIN=https://painel.example.invalid
AI_TEAM_POSTGRES_PASSWORD_FILE=/etc/ai-team/postgres_password
AI_TEAM_PLATFORM=linux/arm64
```

O arquivo `runtime.env` contém apenas configurações operacionais aprovadas. Não
defina `AI_TEAM_DATABASE_URL` nele: o arquivo de segredo abaixo tem precedência.
Não use `docker compose config` sem `--quiet` com variáveis reais, pois a expansão
do arquivo privado pode revelar valores. Proteja os arquivos com ACL/permissões
do host; `/etc/ai-team/app-secrets` precisa permitir travessia pelo UID/GID 10001,
e seus arquivos precisam ser legíveis por esse UID sem leitura pública. Um padrão
é root:10001 com diretório 0750 e arquivos 0640. O arquivo de interpolação e o
`runtime.env` podem permanecer root:root 0600, lidos pelo operador do Compose.

O diretório estreito `app-secrets` é montado somente para leitura em `/run/secrets`.
Não monte o diretório pessoal, o repositório, Docker socket nem cofres de outros
aplicativos. O entrypoint aceita somente comandos fixos de serviço e lê uma lista
fixa de arquivos; links e arquivos não regulares são recusados. Nenhum shell lê
comandos de mensagens ou respostas de modelos.

| Arquivo em app-secrets | Destino em memória | Obrigatório |
| --- | --- | --- |
| `database_url` | `AI_TEAM_DATABASE_URL` | Sim |
| `gemini_api_key` | `AI_TEAM_GEMINI_API_KEY` | Não |
| `google_read_token` | `AI_TEAM_GOOGLE_READ_TOKEN` | Não |
| `gemini_project_id` | `AI_TEAM_GEMINI_PROJECT_ID` | Não |
| `gemini_project_number` | `AI_TEAM_GEMINI_PROJECT_NUMBER` | Não |

Valores ficam no ambiente do processo servidor, nunca em Git ou argumentos de
comando. Gemini ausente permanece indisponível; configuração não prova elegibilidade
gratuita, quota, billing desabilitado ou conexão testada. Não ativar billing nem
fazer inferência/comparações sem autorização específica. Rotação requer recriação
dos containers; não registrar conteúdo de arquivos/variáveis no diagnóstico.

Codex central requer CLI/app-server documentado, instalação e autenticação próprios
no Linux. A imagem não instala o CLI e não herda sessão ou tokens do Desktop.
Não copiar o cofre Windows para a VM. Sem integração própria validada, tratar Codex
como indisponível e preservar o fluxo supervisionado; não inventar credencial ou
fallback pago. Hermes não é provisionado nesta composição.

## PostgreSQL privado e dados

`database_url` usa `postgresql+psycopg://...`. A opção padrão é banco privado existente
(incluindo Supabase opcional), com TLS verificado, rede/allowlist e papel exclusivo
para AI TEAM. Nunca colocar credenciais no frontend. Dimensione o pool: cada
processo da aplicação pode abrir até dez conexões; não aumentar réplicas antes de
rever limites do banco. Uma URL válida não equivale a conexão testada.

O perfil opcional `local-db` oferece PostgreSQL 17.11 fixado pelo mesmo digest da CI,
sem porta publicada e sem rede de saída. O segredo `postgres_password` fica em
arquivo separado, fora de `app-secrets`, legível pelo usuário postgres da imagem.
O papel `ai_team_admin` serve apenas à inicialização/administração. Antes de ligar
os serviços, crie por sessão administrativa privada um papel de aplicação sem
superusuário/CREATEDB/CREATEROLE, schema `ai_team` e concessões mínimas necessárias;
use esse papel no `database_url` operacional. A composição não distribui senha de
superusuário aos processos da aplicação e não cria política de acesso automaticamente.

`postgres-data`, `app-data` e `vault-data` são volumes distintos. O vault Markdown
fica em `/vault` e arquivos operacionais/artefatos ficam em `/data`. O armazenamento
de vídeos usa `AI_TEAM_VIDEO_ROOT=/data/videos`, comum à API e ao renderer. Faça backup
consistente do PostgreSQL e dos volumes, criptografado, com retenção e ensaio de
restauração. Não executar `down -v`, limpar volumes ou substituir banco existente.

`init-db` é manual e aditivo (`create_all`), não uma migração versionada. Mudanças
em colunas existentes exigem plano próprio de migração, backup e autorização.
Para inicializar com credencial DDL separada, use outro arquivo de interpolação
privado apontando temporariamente a um diretório de segredos de manutenção. Nunca
substitua a credencial do serviço em execução por credencial administrativa.

## Sequência operacional para futura implantação autorizada

Os comandos abaixo são um roteiro; sua documentação não autoriza deploy:

```sh
docker compose --env-file /etc/ai-team/compose.env -f compose.production.yaml config --quiet
docker compose --env-file /etc/ai-team/compose.env -f compose.production.yaml build api worker scheduler
# Somente se banco local foi escolhido e autorizado:
docker compose --env-file /etc/ai-team/compose.env -f compose.production.yaml --profile local-db up -d postgres
# Com segredo de manutenção e banco previamente revisados:
docker compose --env-file /etc/ai-team/maintenance.env -f compose.production.yaml --profile maintenance run --rm init-db
docker compose --env-file /etc/ai-team/maintenance.env -f compose.production.yaml --profile maintenance run --rm create-owner
# Usar novamente o papel operacional de privilégios mínimos:
docker compose --env-file /etc/ai-team/compose.env -f compose.production.yaml up -d api worker scheduler
```

Senha do proprietário é solicitada interativamente, sem argumento/arquivo Git.
Antes de acesso público, verificar login, CSRF, revogação, persistência, limites,
aprovações, proxy HTTPS e recuperação. API não executa jobs longos; Vercel hospeda
apenas frontend, sem API/worker de longa duração.

Esta composição é para elaboração textual e fila supervisionada. O sandbox de
Python/Next/repositório existente necessita executor isolado revisado separadamente.
Não montar Docker socket para fazê-lo funcionar; tarefas que exigem sandbox não
estão prontas nesta topologia. O acesso de saída permite provedores, não constitui
isolamento de execução de código gerado.

O perfil `video` acrescenta `python -m ai_team.video_worker`; a imagem opcional
instala FFmpeg e fontes DejaVu dos repositórios oficiais Debian. Não há serviço de
renderização externo, modelo baixado ou inferência no build. Para uso autorizado:
`docker compose --env-file /etc/ai-team/compose.env -f compose.production.yaml --profile video up -d --build video-worker`.
Rever quota de disco e tempo de render antes disso. A imagem Linux não compartilha
instalações FFmpeg, fontes ou credenciais do Windows.

## Saúde, encerramento e evidências

API verifica HTTP local e `SELECT 1`; worker verifica processo e heartbeat recente
em `worker_heartbeats` (janela 120s). A composição pressupõe uma única réplica do
worker: heartbeat agregado não identifica uma réplica individual. Scheduler e
video-worker verificam processo Linux e conectividade SQL, sem prometer progresso
de fila/renderer. Não há heartbeat funcional deles ainda. Todos os probes são
privados e omitem exceções/URLs; nenhum invoca modelos ou comandos arbitrários.
Um container `unhealthy` não é reiniciado automaticamente pelo Compose: configurar
monitor externo aprovado para alertar travamentos e não apenas quedas de processo.

Containers usam UID sem root, filesystem somente leitura, tmpfs limitado, todas
capabilities removidas, `no-new-privileges`, limites CPU/RAM/PIDs, logs com rotação,
`restart: unless-stopped` e SIGTERM com 45s (PostgreSQL 60s). Revisar o tratamento de
SIGTERM dos processos e leases no ensaio de reinício: a política de restart não
prova encerramento gracioso de cada job. Segredos são leitura; volumes de dados
permanecem graváveis pelo serviço.

Em 2026-11-06 `docker buildx imagetools inspect` confirmou manifestos Linux ARM64:

| Base oficial | Digest do índice | Manifesto ARM64/v8 |
| --- | --- | --- |
| Python 3.12.15 slim | `a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704` | `6c6ae3622772575c3ac02ecb2b02a06d05f19e1713a0cbff476ef37bca79e90f` |
| PostgreSQL 17.11 bookworm | `839fbb5a4942a7758dd93e18b42ea5649807491a0545b5eeeb8f0b8bb11857a5` | `e692f23ba2393c8b13879dd4ee9f4f0d7bd146fbddceb4c8e10c4ce1fb53e737` |

Manifestos confirmam disponibilidade da base, não execução em hardware ARM64.
Build, FFmpeg, permissões de volumes e reinício devem ser registrados separadamente
dos testes Python/Compose. Hardware ARM64 e operação contínua 24/7 não foram
validados neste ambiente Windows. Nenhum banco real foi conectado nesta preparação.
O CLI Docker estava disponível, mas `docker info` não encontrou o pipe do Engine
Linux: nenhum build de imagem ou teste de FFmpeg/container foi executado. Os oito
testes direcionados Python passaram, incluindo renderização JSON do Compose com
arquivos de ambiente sintéticos e verificação de isolamento/limites; Ruff passou.
