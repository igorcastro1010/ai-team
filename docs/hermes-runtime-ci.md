# Smoke do runtime oficial Hermes no CI

**Homologação observada:** [run 40922239576](https://github.com/igorcastro1010/ai-team/actions/runs/40922239576)
concluído com sucesso no commit `823e45761cecee851f0fbd63d6e1b5be05831723`.
Gateway, autenticação, política efetiva, sete perfis nativos e persistência
de SessionDB após recriação passaram. Nenhuma inferência foi executada.

O workflow `.github/workflows/hermes-runtime.yml` inicia o serviço `hermes`
do Compose em runner Linux amd64 descartável. Constrói também a imagem da API
e executa seu cliente HTTP em um contêiner transitório, sem iniciar servidor
web, worker, scheduler, Telegram ou inferência. Não recebe credenciais de provedor ou
segredos do repositório. O arquivo `.env.hermes` criado no runner fica vazio.

Imagem fixada:
`nousresearch/hermes-agent@sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d`.
Não trocar o digest sem nova revisão de origem, contratos e segurança.

## O que um run aprovado comprova

1. A imagem oficial inicia o gateway e passa pelo health check real de política.
2. O container não publica portas no host. As sondagens HTTP executam dentro
   dele, em `127.0.0.1:8642`, como usuário `hermes` sem privilégios de root.
3. `/v1/capabilities` e `/v1/toolsets` rejeitam ausência de token e token inválido
   com HTTP 401; aceitam apenas a chave efêmera gerada para aquele job.
4. O inventário real usa os envelopes oficiais de capabilities e toolsets;
   todos os toolsets publicados estão desabilitados. A resolução Python oficial
   verifica também MCP padrão, que não aparece integralmente no inventário REST.
5. O provisionador cria os sete homes nativos, é idempotente e a API Python
   oficial `list_profiles(lazy_skill_count=True)` encontra esses perfis.
6. A classe oficial `hermes_state.SessionDB` grava e lê uma sessão/mensagem
   sintética em `/opt/data/ai-team-ci-<run>-<attempt>.sqlite3`. Esse arquivo é
   exclusivo do teste; o smoke não abre nem modifica o `state.db` do gateway.
7. O workflow força a criação de outro container, confere a mudança de ID,
   preserva o volume do job e repete autenticação, política, descoberta dos
   perfis e leitura da sessão sintética. Nenhum endpoint de execução é chamado.

Esse teste de persistência usa o armazenamento oficial, mas não prova que uma
conversa obtida por inferência ou pelos endpoints HTTP sobreviva à reinicialização.

## Isolamento, limites e diagnóstico

- Permissões GitHub: somente `contents: read`; sem provisioning pago.
- Projeto Compose exclusivo por run/attempt. O encerramento remove somente
  os containers, redes e volumes desse projeto. Não usa `docker system prune`.
- Limite total de 20 minutos; pull de 10 minutos; duas esperas de prontidão
  de 4 minutos; cada fase do smoke limitada a 90 segundos. Container limitado
  a 2 CPUs, 2 GiB e 256 processos pelo Compose/override do job.
- No override de CI, as duas redes são internas: o container não tem saída
  externa. O pull ocorre no host antes do início do gateway.
- A chave aleatória é mascarada imediatamente e passada pelo ambiente do
  servidor. Não se imprime ambiente, Compose renderizado, configuração,
  resposta HTTP bruta, traceback ou logs do container. O driver de logs do
  container fica desabilitado no CI. O script publica apenas fase e resultado.
- Falhas indicam a fase sem divulgar os dados. Para investigar, revisar o código
  fixado e reproduzir em ambiente descartável; não habilitar dumps com segredos.

O workflow roda nos pushes de `main` e `codex/hermes-integration`, e nos PRs que
alterem seus arquivos relevantes; também permite execução manual na aba Actions.
Execuções concorrentes da mesma branch de origem (push e PR) são canceladas.
O runner hospedado é
descartável, inclusive se cancelamento impedir a etapa final de limpeza.

## Origem dos contratos e estado da validação

O primeiro run real no GitHub, `40920937548` (job `123613645703`), iniciou a
imagem fixada, passou pelo health check e pelas fases HTTP de autenticação,
capabilities, inventário e política efetiva de ferramentas. Falhou na fase de
perfis; persistência e reinicialização ainda não foram comprovadas nesse run.
O erro original ocultava todo o detalhe, portanto sua causa exata não deve ser
apresentada como confirmada.

A investigação seguinte leu diretamente a camada de código da imagem amd64,
verificando seu SHA-256
`fcf720a342af7b5020f7a08992d0fd6437bd319f66b1cd3a76ad735c06a04899`.
Ela confirmou `list_profiles(lazy_skill_count=True)` e o retorno `ProfileInfo.name`.
O runtime usa `hermes_yaml`/ruamel como API YAML oficial; PyYAML não é uma
dependência direta do core dessa imagem. O provisionador agora usa a API
oficial quando disponível, mantendo PyYAML para desenvolvimento local. Não há
instalação adicional ou alteração na imagem. O smoke passou a emitir subetapas
fixas e categorias de erro permitidas, sem mensagens ou nomes de módulos vindos
de exceções. O run aprovado acima confirmou a correção e completou as duas
fases do teste, incluindo recriação e leitura dos dados preservados.

Contratos conferidos diretamente no código oficial no commit
[`e298669b44ce032a995c8a67ceae025801b0f4bf`](https://github.com/NousResearch/hermes-agent/tree/e298669b44ce032a995c8a67ceae025801b0f4bf):

- [`gateway/platforms/api_server.py`](https://github.com/NousResearch/hermes-agent/blob/e298669b44ce032a995c8a67ceae025801b0f4bf/gateway/platforms/api_server.py):
  auth Bearer, capabilities e inventário de toolsets.
- [`hermes_cli/profiles.py`](https://github.com/NousResearch/hermes-agent/blob/e298669b44ce032a995c8a67ceae025801b0f4bf/hermes_cli/profiles.py):
  `list_profiles` e descoberta sob o home configurado. O teste usa a API Python
  diretamente; não depende de sintaxe CLI presumida.
- [`hermes_state.py`](https://github.com/NousResearch/hermes-agent/blob/e298669b44ce032a995c8a67ceae025801b0f4bf/hermes_state.py),
  `hermes_state_sessions.py` e `hermes_state_messages.py`: `SessionDB(db_path=...)`,
  criação de sessão, append e leitura de mensagens.
- [`Dockerfile`](https://github.com/NousResearch/hermes-agent/blob/e298669b44ce032a995c8a67ceae025801b0f4bf/Dockerfile):
  entrypoint supervisionado, usuário `hermes`, runtime Python e `/opt/data`.

Em 29/10/2026, a preparação foi verificada localmente com compilação Python,
Ruff, inspeção YAML e sondagens de contrato com servidor HTTP local sintético.
**Docker não está disponível nesta máquina. O runtime tem evidência parcial no
GitHub descrita acima; perfis, persistência e reinicialização ainda precisam de
um workflow aprovado.** Não confundir testes de contrato
sintéticos com execução da imagem oficial. Registrar URL, SHA e resultado do
run observado antes de atualizar esse estado.

Inferência/modelo, consumo, cancelamento remoto, Telegram/pairing, subagentes,
PostgreSQL, sandbox e implantação de produção continuam fora deste smoke.

Verificações estáticas locais:

```powershell
.venv/Scripts/python.exe -m py_compile infra/hermes/runtime_smoke.py
.venv/Scripts/python.exe -m ruff check infra/hermes/runtime_smoke.py
```
