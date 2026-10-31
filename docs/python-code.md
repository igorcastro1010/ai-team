# Código Python com testes isolados

## Usar no Windows

Requisitos: painel/API/worker locais, Docker Desktop com engine Linux e executor
Codex próprio ou Hermes autenticado. Para preparar a imagem oficial revisada:

```powershell
docker pull python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
powershell -NoProfile -File .\tools\start.ps1
```

O runner usa `--pull never`; não baixa nem instala dependências por tarefa.
Somente o worker controla Docker. Não montar socket Docker no Hermes ou API.
O Compose de desenvolvimento não inclui o executor Docker dentro do worker;
esta entrega homologa o worker nativo Windows, com Docker Desktop local.

1. Crie ou selecione um projeto e abra **Conversa com CEO**.
2. Escolha **Tipo de entrega → Código Python com testes isolados**.
3. Descreva um módulo pequeno, por exemplo: `Crie main.py com uma função add(a,b)
   e testes unittest para números positivos, negativos e zero.`
4. Autorize o envio ao executor. CEO planeja, DEV gera arquivos, DESIGNER revisa
   usabilidade e QA gera testes. No modo manual, aprove cada próxima etapa.
5. Revise os arquivos apresentados e o identificador SHA-256. Baixe o ZIP se desejar.
6. Clique em **Aprovar execução dos testes** e confirme. Esta decisão vale somente
   para o run, projeto, etapa e conteúdo revisados, inclusive no modo automático.
7. QA executa a suíte; CEO consolida. Consulte status, código de saída e saída
   limitada dos testes. O escritório mostra QA durante a suíte e CEO no relatório.

Nenhum checkout existente é editado. São arquivos novos e baixáveis, não um PR
ou alteração automática de outro projeto. A integração GitHub continua restrita
à política anterior de documentos e exige decisões próprias.

## Isolamento e limites

- Python 3.12, biblioteca padrão e unittest. Até 12 arquivos simples `.py`, sem
  diretórios, traversal, nomes reservados ou módulos que substituam a stdlib.
- Até 48 KiB UTF-8 no conjunto, com limite individual de 16 mil caracteres.
  Somente QA fornece `test_*.py`; os testes não substituem arquivos DEV.
- Contêiner por tarefa, usuário 65532, rede desligada, raiz somente leitura,
  capabilities removidas e no-new-privileges. Nenhum mount, segredo ou checkout.
- Workspace em tmpfs de 16 MiB; 1 CPU, 256 MiB, 64 PIDs e saída até 32 KiB.
- Timeout do controlador de 30 s, supervisor interno de 28 s e watchdog de
  30 s no contêiner. `--rm` remove o contêiner ao terminar.
- Nome e admissão persistidos antes da criação. Cancelamento/lease expirada
  reconciliam apenas nome exato e label própria; não repetem execução incerta.
  Se Docker estiver offline, cleanup fica incerto e novos pedidos Python aguardam;
  o worker continua atendendo pedidos textuais.
- O supervisor não importa código gerado. A suíte roda em subprocesso e precisa
  confirmar término normal e quantidade positiva de testes por canal separado.
  `os._exit(0)` antecipado e suíte vazia não contam como sucesso.

O resultado confirma execução e término da suíte gerada; não garante que testes
deliberadamente falsificados ou incompletos comprovem correção do programa.
Docker compartilha o kernel: este desenho local de proprietário único não é
homologação para executar código hostil em serviço público multiusuário.

O fluxo textual existente e os agendamentos continuam preservados. Nenhuma
migração de tabelas: artefatos, autorização e resultados usam o JSON das etapas.
Sem deploy, ampliação da GitHub App, publicação, Telegram ou merge automático.

## Verificação

```powershell
# Suíte sem consumo de modelo; testes Docker exigem opt-in explícito.
$env:AI_TEAM_SANDBOX_TESTS='1'
.venv\Scripts\python.exe -m pytest services/api/tests -q
Remove-Item Env:AI_TEAM_SANDBOX_TESTS

# Até cinco chamadas reais, banco temporário e projeto fictício.
.venv\Scripts\python.exe tools/smoke_hermes.py --real --python-code
```

Em 30/10/2026: 248 testes passaram e 7 PostgreSQL foram omitidos por ausência
de banco descartável específico. Docker real cobriu sucesso, falha, timeout,
saída excessiva, isolamento, cancelamento, suíte vazia, saída UTF-8 inválida e
morte forçada da árvore do controlador. O watchdog encerrou o contêiner sem
depender do `finally` do host. Aprovação alterada/repetida, CSRF e recuperação
de worker/Docker offline têm regressões automatizadas.

Lint, typecheck e build passaram. A suíte Playwright passou em 21 cenários,
incluindo a entrega Python a 390 px, aprovação por hash, ZIP válido através do
proxy Next.js e verificação automatizada WCAG A/AA. A imagem local
`artifacts/python-code-390.png` foi inspecionada; os dados são sintéticos.
Revisão independente identificou os problemas de contêiner órfão e término
prematuro da suíte; ambos foram reproduzidos/corrigidos com regressões. A revisão
final não identificou outro bloqueio no escopo local aprovado.

Smoke final com Hermes próprio e `gpt-6.1-sol`: cinco etapas, geração de arquivos,
aprovação por hash e seis testes unittest reais aprovados. Uso reportado: 9.427
tokens de entrada e 1.990 de saída, sem preço monetário confirmado. Evidência
privada ignorada: `artifacts/python-code-smoke.json`. Sem dados de projetos reais.

Referência: [opções oficiais Docker](https://docs.docker.com/reference/cli/docker/container/run/).
