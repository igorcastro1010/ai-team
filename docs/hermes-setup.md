# Hermes privado — desenvolvimento e homologação

## Estado da entrega

Adaptador para Runs API oficial, consentimento por executor e diagnóstico
persistente. O padrão continua Codex. Hermes nesta etapa elabora texto sem
ferramentas. Não há shell de modelo, merge ou deploy. Testes de contrato não
comprovam inferência, Telegram, delegação ou persistência de contêiner real.

## Compose

Requer Docker Engine/Desktop com Compose v2; não é instalado automaticamente.
O Compose é uma instalação de desenvolvimento independente: **seu volume
`ai-team-data` não importa nem substitui `.data/ai-team.db` da instalação Windows**.
Não rode dois serviços diferentes sobre o mesmo SQLite. Migração para o Compose
exige backup e transferência revisada; não copie SQLite aberto.

1. Copie `.env.example` para `.env` e
   `infra/hermes/provider.env.example` para `.env.hermes`. Ambos ficam ignorados.
2. Gere um segredo aleatório de 32 bytes no seu gerenciador de senhas e salve
   em `AI_TEAM_HERMES_KEY` no `.env`. Não envie no chat nem use `NEXT_PUBLIC_*`.
3. Configure a chave do seu provedor em `.env.hermes` conforme a documentação
   oficial. Exemplo: `OPENROUTER_API_KEY` para OpenRouter. No arquivo **do host**
   `infra/hermes/config.yaml`, adicione o modelo sem segredos:

   ```yaml
   model:
     provider: openrouter
     default: SEU_ID_DE_MODELO_COMPATIVEL
   ```

   Use o ID disponibilizado pela sua conta. O gateway monta essa configuração
   somente leitura, portanto o assistente `setup` não deve tentar regravá-la.
   OAuth/Nous/Codex exigem o fluxo próprio documentado em home separado e
   homologação antes de uso; não copiar tokens do Desktop.
4. Inicie os serviços e cadastre proprietário **nesta nova instalação**:

   ```sh
   docker compose up -d --build
   docker compose exec api ai-team create-owner --username admin
   npm run dev
   ```

   Abra localhost:3000. API publicada somente em 127.0.0.1:8000; Hermes não
   publica portas. Verifique as dependências com `docker compose ps` e consulte
   logs localmente com `docker compose logs --tail 100 hermes worker`.
   Logs e o volume Hermes podem conter conversas: não compartilhe sem revisão.

O contêiner AI TEAM não inclui sessão Codex ou cofre GitHub do Windows.
Solicitações Codex permanecem bloqueadas nesse worker até configuração própria
compatível. Sua instalação nativa continua usando os scripts existentes.
Para conectar worker nativo a Hermes use túnel privado de loopback revisado;
o adaptador aceita `localhost`, `127.0.0.1`, `::1` ou DNS de serviço `hermes`.
Nunca publique 8642 em 0.0.0.0 no host.

Imagem oficial `nousresearch/hermes-agent:stable` resolvida em 29/10/2026 para
o digest fixado no Compose. O código/documentação auditados são main, conforme
`hermes-audit.md`; stable pode ter capacidades diferentes. Diagnóstico recusa
contrato incompatível. Atualização do digest requer repetir homologação.

## Segurança e limites

API_SERVER_KEY autentica servidor a servidor. O navegador recebe somente
diagnóstico sanitizado. Não há proxy genérico para endpoints Hermes. O gateway
tem volume próprio; sem Docker socket, banco AI TEAM, checkout ou chaves GitHub.
Configuração montada somente leitura, `platform_toolsets` vazios e nenhum MCP.
Cliente verifica `/v1/toolsets` antes da inferência e recusa ferramentas ativas.
O health check do contêiner também resolve o conjunto efetivo do runtime,
incluindo MCP omitidos pelo inventário REST, e falha se encontrar ferramentas.
Essa inspeção não substitui o arquivo controlado: não adicionar plugins/MCP ao
volume. Mudanças de ferramentas exigem outra revisão de permissões e isolamento.

Cada solicitação fica vinculada a Codex ou Hermes na tabela adicional
`run_executors`; linhas antigas e agendas existentes continuam Codex. Em produção
execute `ai-team init-db` antes de atualizar API/worker. Sem remoção de dados ou
alteração de colunas existentes.

Limites preservados: cinco chamadas por solicitação, 120s por chamada e limiar
de 50 mil tokens antes da próxima chamada. Hermes: concorrência API máxima 1,
duas iterações por turno, resposta HTTP máxima 200 KB e schema de resultado
validado. O cliente não repete admissão em erro. Cancelamento/timeout tenta
`/stop`; falha de rede deixa situação remota incerta. Verifique no gateway antes
de pedir novo trabalho. Queda do worker não garante interrupção no provedor.

Tokens são reportados pelo runtime Hermes, não estimados por caracteres. Custo
monetário permanece indisponível: preço varia com modelo, cache, raciocínio e
ferramentas. Configure teto no provedor; os limites locais **não são teto
financeiro rígido**. Não há contratação ou inferência paga automática em testes.

## Critérios de homologação real

Com runtime e provedor já configurados, o comando opt-in
`.venv/Scripts/python.exe tools/smoke_hermes.py --real` autoriza até cinco chamadas
em banco temporário, valida API autenticada, consentimento Hermes, checkpoints e
aprovação e grava `artifacts/hermes-smoke.json`. Não valida subagentes nativos ou
Telegram. No Compose a execução do smoke exige copiar o script para o serviço
API ou executá-lo por túnel privado revisado; não abrir uma porta pública.

- Diagnóstico autenticado responde `reachable`; isso não comprova inferência.
- Criar solicitação **Hermes** em projeto supervisionado, conferir plano, aprovar
  e verificar resultados e tokens do provedor. Confirmar que Codex antigo não mudou.
- Cancelar durante execução e conferir `/stop` no Hermes.
- Reiniciar gateway/worker com volume preservado e inspecionar execuções
  interrompidas/incertas; nenhuma readmissão automática.
- Confirmar que mensagens pedindo shell, segredos, merge ou deploy não executam
  ferramentas; verificar inventário e ausência de mounts sensíveis.
- Confirmar persistência após `docker compose restart`; **não usar `down -v`**.

Sem Docker/provedor configurados, esses itens ficam pendentes, nunca aprovados
por doubles. Backups: parar o serviço, copiar os dois volumes completos para
armazenamento cifrado e testar restauração em volumes novos. Incluir sessões,
WAL e credenciais Hermes; não versionar backup.

## Próximas capacidades nativas

Bot Mode representa perfis Hermes com memória/configuração isoladas. Preparar
CEO, DEV, DESIGNER, QA, PESQUISADOR, MARKETING e ANALISTA via perfis oficiais;
não confundir papéis visuais do AI TEAM com bots provisionados. A entrega básica
mantém o fluxo de cinco etapas existente. Delegação nativa está bloqueada nesta
política sem ferramentas e exige homologação posterior.

Telegram usa o gateway oficial; não criar outro cliente Bot API. Configurar
token pelo assistente oficial ou no `.env` privado do perfil CEO, junto da
allowlist de IDs numéricos e pairing revisado. Ver `hermes-next-phases.md`.

## Produção

Next.js pode permanecer na Vercel. API, Hermes, worker e scheduler precisam de
host persistente, PostgreSQL privado, HTTPS, acesso autenticado entre servidores,
backup e alertas de heartbeat/erros. Não usar Vercel Functions para o gateway.
O Compose entregue usa SQLite/desenvolvimento e não deve ser publicado como
produção. Nenhum host pago foi contratado nem deploy realizado.
