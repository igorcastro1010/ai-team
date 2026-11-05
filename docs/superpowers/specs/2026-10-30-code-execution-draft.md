# Execução real de código — proposta de próxima entrega

Estado: alternativa 1 (Python primeiro) aprovada pelo proprietário em 30/10/2026.

## Situação verificada

O worker executa cinco etapas textuais via LangGraph. `DraftContent` contém
resumo, parecer e delegações; não há contrato de arquivos executáveis.
O Codex nativo bloqueia shell e escrita. Hermes tem ferramentas desativadas.
O GitHub aceita commits somente em `docs/agent-output/*.md`, com aprovação.
Essas políticas permanecem válidas para as execuções textuais existentes.

## Alternativas

1. Recomendada: primeira entrega vertical para Python sem dependências externas.
   DEV gera arquivos estruturados, QA propõe testes e um executor separado roda
   uma suíte fixa em Docker. Menor superfície para comprovar isolamento.
2. Python e Next.js juntos: exige duas imagens, políticas de dependências e
   comandos de teste diferentes; maior escopo de validação.
3. Melhorar primeiro escritório pixel 2D e animações: evolução visual, sem
   habilitar execução de código nesta entrega.

## Desenho proposto para a alternativa 1

- Novo escopo opt-in, sem transformar pedidos textuais antigos em execução.
- Workspace descartável por tarefa, criado pelo servidor; não aceitar caminhos
  absolutos, links, travessia de diretório ou comandos vindos do modelo.
- DEV retorna arquivos delimitados por schema e limites de tamanho/quantidade.
- QA produz testes separados; o worker usa comando fixo de descoberta de testes.
- Aprovação vinculada ao projeto e hash exato dos arquivos antes de executar.
- Executor local controla Docker fora do contexto dos agentes. Nenhum socket
  Docker, pasta pessoal, checkout original ou credencial entra no contêiner.
- Imagem revisada e fixada por digest; rede desligada, usuário sem privilégios,
  capabilities removidas, raiz somente leitura e limites de CPU, RAM, PIDs,
  duração e tamanho de saída. Sem instalar dependências durante a tarefa.
- Coletar diff, código de saída e relatório limitado. Cancelamento encerra o
  contêiner específico; falha de isolamento bloqueia a execução.
- Persistir estados/eventos e apresentar resultados reais no painel e no
  escritório existente. Saída de processos é conteúdo não confiável.
- Gerar artefatos revisáveis; envio ao GitHub requer etapa posterior, com
  política própria e aprovação por SHA. Sem ampliar a App implicitamente.

## Critérios de aceite antes de anunciar funcionamento

Testar autenticação/CSRF, autorização por hash e projeto, isolamento entre
workspaces, validação de caminhos/links, limites de saída e recursos, timeout,
cancelamento, recuperação do worker e preservação de pedidos antigos.
Realizar teste Docker com sucesso e falha de código gerado, tentativa de acesso
ao host/rede e atualização dos estados do painel. Testes unitários com mocks
não comprovam isolamento real. Docker local é uma camada de contenção;
execução pública multiusuário exige revisão adicional de isolamento.

## Fora desta entrega proposta

Edição de outros repositórios, instalação arbitrária, terminal livre, merge,
deploy, publicação, Telegram e expansão automática de ferramentas do Hermes.
