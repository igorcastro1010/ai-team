# Ativação local: Docker/WSL, Codex próprio e Telegram

Escolhas do proprietário: executar neste PC com Docker/WSL, autenticar o
Hermes com OpenAI/Codex em login próprio e criar um bot Telegram novo.
Não importar a sessão do Codex Desktop nem contratar serviços.

## Antes de instalar

O Docker precisa de virtualização habilitada no firmware e WSL 2 operacional.
Confira `Virtualização: Habilitada` em Gerenciador de Tarefas → Desempenho → CPU.
Se desabilitada, habilite Intel Virtualization Technology/VT-x ou AMD SVM no
firmware, conforme o manual da placa. O agente não altera BIOS nem reinicia o PC.

Habilitar os componentes WSL/Virtual Machine Platform pode exigir confirmação
de administrador e reinício. Confira a conclusão antes de instalar o Docker.
Reserve espaço para Docker, imagens e volumes; não apague arquivos pessoais
ou bancos para fazer a instalação caber. A falta de espaço deve ser resolvida
antes do download das imagens. Não confundir o executável `wsl.exe` com um
runtime WSL 2 já instalado.

Referências: [Docker Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
e [Microsoft WSL](https://learn.microsoft.com/windows/wsl/install).

## Arquivos privados preparados

- `.env`: chave aleatória do adaptador; não imprimir nem versionar.
- `.env.hermes`: reservado ao gateway, sem chave de provedor nesta configuração
  OAuth. Telegram será configurado no contexto próprio do CEO.
- `.data/hermes-local/config.yaml`: cópia privada com ferramentas desabilitadas
  e `auth.adopt_external_logins: false`.
- `.data/hermes-local/compose.local.yaml`: substitui somente o mount da
  configuração Hermes por essa cópia gravável. O assistente oficial pode
  salvar o modelo escolhido. Para conectar o worker Windows, publicar somente
  `127.0.0.1:8642:8642`, com a chave privada exigida pelo gateway. O Compose base
  continua sem porta Hermes publicada. Nunca usar `8642:8642` sem endereço.

Override privado para o worker Windows (caminhos relativos ao Compose da raiz):

```yaml
services:
  hermes:
    volumes:
      - ./.data/hermes-local/config.yaml:/opt/data/config.yaml
    ports:
      - "127.0.0.1:8642:8642"
```

Validar com `docker compose -f compose.yaml -f .data/hermes-local/compose.local.yaml config --quiet`.
Não imprimir a configuração resolvida: ela contém a chave do gateway.

Esses arquivos não constituem login válido ou homologação de inferência.
Não sobrescrever arquivos privados existentes em uma nova preparação.

## Diagnóstico antes de iniciar

```powershell
powershell -NoProfile -File .\tools\doctor.ps1
powershell -NoProfile -File .\tools\doctor.ps1 -Json -RequireHermes
```

O diagnóstico apenas verifica dependências e executa comandos fixos de versão/status,
com timeout. Não lê `.env`, cofre, sessão Codex ou configuração privada Docker.
Sem `-RequireHermes`, o código de saída indica a prontidão do painel/API nativos;
com essa opção, exige também WSL compatível no Windows, ausência de reinício
pendente, engine Docker Linux e Compose. `0` significa pré-requisitos atendidos;
`2` indica pendência. Mesmo um diagnóstico aprovado não comprova autenticação,
inferência, Telegram ou produção. Os campos JSON distinguem `base_ready` e
`hermes_ready`, e não exibem stdout/stderr bruto das ferramentas.

Em 30/10/2026, foram instalados WSL 3.0.3 e Docker Desktop 4.97.0 neste PC,
com autorização explícita, por fontes oficiais e sem reiniciar. O Windows registrou
reinício pendente e hipervisor inativo. O primeiro instalador Docker recusou a
ausência de VirtualMachinePlatform; após o instalador WSL concluir, a instalação
Docker por usuário terminou com êxito. O runtime Hermes continua sem homologação
local naquele momento, até reiniciar, iniciar a engine e concluir o login próprio. Nenhuma chave
ou sessão externa foi importada.

Após o reinício e o login próprio, o teste textual real passou em cinco etapas.
Ver as evidências e os limites atuais em [homologação local](hermes-validation.md#homologação-local-após-login-próprio--30102026).

Fontes: [instalação WSL](https://learn.microsoft.com/windows/wsl/basic-commands)
e [instalação Docker por usuário](https://docs.docker.com/desktop/setup/install/windows-install/).

## Depois dos pré-requisitos

Na raiz do projeto, conferir primeiro `docker version` e `docker compose version`.
Iniciar somente o Hermes, mantendo os volumes:

```powershell
docker compose -f compose.yaml -f .data/hermes-local/compose.local.yaml up -d --no-deps hermes
docker compose -f compose.yaml -f .data/hermes-local/compose.local.yaml exec --user hermes hermes hermes model
```

No assistente oficial, escolher OpenAI/Codex e **login novo**, sem importar
credenciais existentes. O usuário conclui a autenticação no navegador e escolhe
um modelo disponível em sua conta. Não registrar código de login, URL contendo
credenciais ou tokens em documentos, mensagens, capturas ou logs compartilhados.
Revisar a configuração sem imprimir segredos; confirmar que ferramentas e
adoção externa continuam desabilitadas. Depois iniciar API/worker/monitor e
executar o smoke opt-in documentado em [configuração](hermes-setup.md).

### Falha ao salvar login: `auth.lock`

O gateway e os comandos de autenticação usam o usuário `hermes` (UID 10000
na imagem fixada). O health check também deve executar como esse usuário,
via `/command/s6-setuidgid hermes`, pois os imports do runtime podem criar
`/opt/data/auth.lock`. Executá-lo como root pode deixar a trava inacessível
ao login, mesmo com o gateway saudável.

Na recuperação local de 30/10/2026, a trava era de root e o teste como `hermes`
reproduziu `PermissionError`. O contêiner foi parado, somente o proprietário
da trava foi corrigido para `hermes:hermes`, com modo `0600`, e o serviço foi
recriado com o health check corrigido. Nenhum volume ou credencial foi excluído.
Validar a aquisição da trava como `hermes` antes de pedir novo login. Não usar
`chmod 777`, apagar o volume nem desabilitar o mecanismo de lock.

O volume Compose é separado do banco Windows existente. Não migrar ou substituir
dados implicitamente e não usar `docker compose down -v`.

## Telegram e delegação

Criar o bot em [@BotFather](https://t.me/BotFather) com `/newbot`. Guardar o
token localmente e informar apenas o username do bot e o ID numérico do dono.
Configurar o gateway oficial no contexto CEO com allowlist/pairing; nunca
habilitar acesso irrestrito nem executar dois gateways com o mesmo token.
Confirmar mensagens reais, resposta, recusa de usuário não autorizado e
persistência antes de anunciar conexão. Ver [próximas fases](hermes-next-phases.md).

Delegação requer uma política própria e teste real após inferência funcionar.
O contexto API básico permanece sem ferramentas. Validar o contrato da versão
instalada, limites de filhos/turnos/duração e ferramentas herdadas antes de
habilitar `delegate_task`. Não liberar terminal, arquivos do host, GitHub ou
publicação para concluir a configuração. Perfil criado não comprova Bot Mode.
