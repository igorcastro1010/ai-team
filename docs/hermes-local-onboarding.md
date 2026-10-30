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
  salvar o modelo escolhido; nenhuma porta Hermes é publicada.

Esses arquivos não constituem login válido ou homologação de inferência.
Não sobrescrever arquivos privados existentes em uma nova preparação.

## Depois dos pré-requisitos

Na raiz do projeto, conferir primeiro `docker version` e `docker compose version`.
Iniciar somente o Hermes, mantendo os volumes:

```powershell
docker compose -f compose.yaml -f .data/hermes-local/compose.local.yaml up -d hermes
docker compose -f compose.yaml -f .data/hermes-local/compose.local.yaml exec --user hermes hermes hermes model
```

No assistente oficial, escolher OpenAI/Codex e **login novo**, sem importar
credenciais existentes. O usuário conclui a autenticação no navegador e escolhe
um modelo disponível em sua conta. Não registrar código de login, URL contendo
credenciais ou tokens em documentos, mensagens, capturas ou logs compartilhados.
Revisar a configuração sem imprimir segredos; confirmar que ferramentas e
adoção externa continuam desabilitadas. Depois iniciar API/worker/monitor e
executar o smoke opt-in documentado em [configuração](hermes-setup.md).

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
