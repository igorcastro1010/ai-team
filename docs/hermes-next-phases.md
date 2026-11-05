# Próximas fases Hermes — configuração e critérios de aceite

## Equipe nativa (fase 2)

`infra/hermes/team.yaml` define CEO, DEV, DESIGNER, QA, PESQUISADOR, MARKETING e
ANALISTA. A ferramenta cria homes nativos com `config.yaml` e `SOUL.md` em
`HERMES_HOME/profiles/<nome>/`; diretórios existentes são preservados, sem copiar
`.env`, memória ou sessão de outro perfil. Não inicia agentes nem faz inferência.

No host com Compose funcionando:

```sh
docker compose exec -T hermes python /opt/ai-team/hermes_profiles.py --home /opt/data --manifest /opt/ai-team/team.yaml
# Revise o dry run e aplique as configurações sem iniciar agentes:
docker compose exec -T hermes python /opt/ai-team/hermes_profiles.py --home /opt/data --manifest /opt/ai-team/team.yaml --apply
```

O [Hermes reconhece esses homes como perfis](https://hermes-agent.nousresearch.com/docs/user-guide/profiles).
Um perfil se torna Bot Mode bot quando o próprio Hermes registra sua apresentação
e conversa canônica no roster. Faça essa etapa no Bot Mode oficial, sem inventar
registros nas tabelas Hermes. Modelos e credenciais de cada perfil precisam de
configuração própria. Papéis no escritório AI TEAM não comprovam bots nativos.

O fluxo existente permanece CEO → DEV → DESIGNER → QA → CEO, com pareceres
textuais. Subagentes nativos usam `delegate_task`, uma capacidade de ferramenta.
Antes de habilitar, revisar limite de filhos, modelo, tokens, concorrência,
ambiente isolado e escopo de ferramentas. Validar uma delegação real e conferir
IDs, resultado e consumo no runtime. **A política básica bloqueia ferramentas**;
não simular delegação com animações ou scripts que devolvem resultados prontos.

## Telegram (fase 4)

Reutilizar o [gateway oficial Telegram](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram).
Primeiro habilitar runtime e provedor; depois configurar o perfil CEO. O nome do
perfil e o token do bot Telegram são identidades distintas. Não assumir que criar
um perfil publica um bot Telegram ou integra a fila de aprovações do AI TEAM.

- Token obtido pelo proprietário no BotFather; salvar somente no `.env` privado
  do perfil CEO como `TELEGRAM_BOT_TOKEN`.
- Definir `TELEGRAM_ALLOWED_USERS` com IDs numéricos explícitos; não habilitar
  `GATEWAY_ALLOW_ALL_USERS` nem aceitar autorização a partir de texto de mensagens.
- Alternativa: pairing oficial. No contexto do perfil CEO, inspecionar pendências
  com `hermes -p ceo pairing list` e aprovar só o código conferido com o usuário:
  `hermes -p ceo pairing approve telegram CODIGO_CONFERIDO`.
- Revogação: `hermes -p ceo pairing revoke telegram ID_NUMERICO`.
- Iniciar/reiniciar somente o gateway configurado para esse perfil. Evitar dois
  processos concorrentes usando o mesmo token e a mesma home.
- Confirmar `/status`, conversa real, resposta, recusa de um segundo usuário e
  revogação de pairing. Relatórios recorrentes precisam de destino consentido.

Nenhuma mensagem foi enviada nesta entrega. Token/ID e pairing precisam de ação
do proprietário no ambiente privado. Não colar token ou código de login no chat.

## Codex e GitHub (fase 5)

O AI TEAM preserva Codex CLI oficial em home próprio e GitHub App com propostas
aprovadas, sem merge. O [OpenAI Codex app-server/SDK](https://developers.openai.com/blog/codex-as-a-platform)
é o mecanismo oficial para incorporar Codex; não é uma API secreta do Desktop.
Hermes também documenta provedor `openai-codex` com autenticação própria. Usar
Codex como provedor não dá automaticamente permissão de editar checkouts.

O novo [fluxo Python local](python-code.md) gera módulos e executa unittest em
Docker após aprovação dos artefatos por hash. Ele preserva ferramentas Hermes
desativadas e não edita checkouts nem amplia a política GitHub.

Execução geral sobre repositórios existentes ainda não é habilitada. Para fazê-lo:
sandbox por tarefa, checkout isolado, credencial GitHub de escopo mínimo fora do
modelo, política de comandos, nenhum socket Docker do host, diffs/testes como
artefatos e aprovação vinculada ao SHA para PR. Merge e deploy exigem autorização
independente. Não ampliar a GitHub App ou reutilizar cofres do proprietário em
contêineres para ultrapassar a etapa de configuração.

## Automações (fase 6)

Agendas existentes do AI TEAM permanecem Codex. Não duplicá-las no cron Hermes.
Novas rotinas Hermes devem usar o cron oficial e seus controles de pausa/retomada;
somente depois ligar seus IDs e eventos ao painel. A entrega básica não anuncia
pause/resume nativo ou agenda Hermes implementada. Cancelamento e retomada de
pedidos bloqueados do workflow existente continuam disponíveis.

Validar custo/modelo e limite no provedor, orçamento de tokens por execução,
duração e concorrência. Leituras de uso incompletas devem continuar indisponíveis;
não estimar dinheiro sem preços e rota efetiva. Produção, mensagens, pagamentos,
exclusões e alteração de permissões sempre exigem decisões específicas.

## Produção (fase 7)

Painel Next.js permanece compatível com Vercel; não houve deploy. API, Hermes e
workers requerem host persistente, banco privado, TLS e autenticação entre
servidores. O cliente atual aceita DNS `hermes` ou túnel loopback: outro hostname
privado requer revisão da allowlist no servidor, sem aceitar URL do navegador.

Antes de publicar: homologar PostgreSQL sem perda de dados, restauração dos dois
volumes, disponibilidade do provedor, alertas de falhas/heartbeat, acesso pelo
painel autenticado e nenhuma porta Hermes pública. Revisar retenção e cifragem de
conversas, logs e backups. Não usar Compose de desenvolvimento como produção.
Infraestrutura paga, merge e publicação aguardam autorização específica.
