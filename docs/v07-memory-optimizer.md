# V0.7 — memória por projeto e Token Optimizer

Base: V0.6.1 integrada na main (`8686559`). Desenvolvimento exclusivo em
`codex/ai-team/v07-memoria-optimizer`; PR #11. Nenhum merge ou deploy da V0.7.

Homologação posterior: [V0.7.1](v071-homologation.md), incluindo Issue real
autorizada, revisão independente automatizada e correções. Os resultados abaixo
registram a rodada original V0.7; consulte o relatório novo para as verificações atuais.

## Como usar

1. Atualize o checkout e execute `tools/setup.ps1` / `tools/start.ps1` conforme o README.
   Bancos existentes não devem ser apagados. Em produção, execute `ai-team init-db`
   explicitamente antes de iniciar os serviços; não há implantação automática.
2. Abra **Memória e contexto** (`/memoria`) e escolha o projeto. Cadastre fatos,
   requisitos e decisões sem credenciais. A página permite buscar, editar por versão
   e consultar histórico; trocar projeto limpa os dados e requisições anteriores.
3. Em **Issues**, prepare uma proposta local e revise título, corpo e digest.
   **Integrações → propostas GitHub** mantém a aprovação e a fila existentes.
   Preparar uma proposta não publica uma Issue. O worker só executa a ação aprovada.
4. Em **Otimizador**, calcule uma prévia local e configure limites por projeto,
   agente ou execução. A prévia e o benchmark não chamam nenhum modelo.
5. Em **Relações**, consulte a proveniência das ligações derivadas dos registros SQL.
   O escritório Pixel Art e suas animações continuam ligados aos eventos anteriores.

## Persistência e recuperação

Novas tabelas privadas e aditivas: `memory_entries`, `memory_revisions`,
`memory_chunks`, `delegated_tasks`, `issue_links`, `optimizer_budgets`,
`optimizer_admissions`, `optimizer_records`. SQLite continua restrito ao ambiente
local; PostgreSQL usa o schema privado `ai_team`, sem exposição PostgREST.

Cada nota tem projeto, origem, digest SHA-256, versão e datas. O histórico é
imutável; atualizações exigem a versão revisada e não alteram versões anteriores.
Escritas são serializadas por projeto para deduplicar conteúdo sob concorrência.
O índice de trechos é atualizado na mesma transação que a nota; a busca trata
acentos e recupera até 12 passagens, com 1.600 caracteres por passagem.
SQL filtra por projeto e termos antes de carregar até 240 candidatos.
Não há embeddings ou serviço semântico contratado.

O worker registra resumos já produzidos em checkpoints reais, sem nova inferência.
Etapas anteriores não são inventadas ou marcadas concluídas pela memória.
Tarefas delegadas têm associação explícita execução/tarefa, não associação por título.
O CEO prepara propostas locais de Issue com identificador persistente por tarefa.
Conteúdo inválido é recusado e auditado sem impedir outras propostas válidas.

CEO, DEV, DESIGNER, QA e PESQUISADOR recuperam notas relevantes antes da chamada
ao provedor. As notas entram como `untrusted_project_memory`, com proveniência;
nunca substituem instruções, permissões ou aprovações. Padrões explícitos de
prompt injection ficam em quarentena e fora da recuperação/grafo.
Esse detector não prova que todo texto seja seguro; a autoridade continua
nos limites e aprovações implementados pelo executor.

## Obsidian no Windows

Configure somente no ambiente privado do servidor:

```powershell
$env:AI_TEAM_MEMORY_VAULT = 'C:\AI-Team\vault'
.\tools\start.ps1
```

Cada projeto usa `<vault>/<project_id>/*.md`. Abra a raiz como vault no Obsidian,
sem plugins obrigatórios; arquivos Markdown e wikilinks são preservados.
O caminho nunca vem de um modelo ou do formulário do painel.
Sincronização explícita no painel e atualização antes das chamadas dos agentes
importam incrementalmente os arquivos externos modificados. Arquivos removidos
não apagam automaticamente o histórico SQL.

Somente nomes planos Markdown: sem travessia, UNC, ADS, nomes de dispositivo,
symlinks, junctions, hardlinks ou configurações `.obsidian`. Leitura por arquivo
limitada a 64 KB e varredura a 1.000 entradas por projeto. Credenciais conhecidas
são recusadas antes da persistência. Arquivos exportados usam IDs de notas;
espelhos modificados são recusados na importação para exigir revisão explícita,
sem reverter silenciosamente a versão SQL. Substituir um arquivo exige seu digest.

O diretório deve pertencer exclusivamente ao operador/serviço, protegido por ACL.
Não se promete isolamento contra um administrador ou processo hostil que possa
trocar diretórios simultaneamente; limites de filesystem não substituem ACL/sandbox.
Nenhuma nota, banco, vault ou arquivo de autenticação deve ser versionado.

## GitHub Issues e consentimento

A App continua instalada seletivamente no `igorcastro1010/ai-team`, com os mesmos
perfis de permissão. A verificação aceita a visibilidade pública atual escolhida
pelo proprietário, preservando identidade, ID do repositório e restrições da instalação.
Tokens temporários de leitura usam `issues:read`; publicação aprovada reutiliza
o executor existente e seu token restrito. Nenhuma permissão foi ampliada.

APIs `/issues` permitem filtros por projeto, agente, prioridade e situação,
associação a tarefa/subtarefa, branch, SHA e PR. Essas referências são metadados
locais validados sintaticamente; sua existência remota não é presumida.
O corpo da proposta e o digest não mudam ao editar metadados locais.
Sincronização lê uma Issue publicada por número e registra `remote_state`
separadamente da situação local; não fecha tarefas ou publica alterações por conta própria.
PRs retornados pela API de Issues são recusados como Issues.

Propostas concorrentes com o mesmo identificador retornam a mesma ação.
Resultados incertos não são repetidos automaticamente. Toda escrita remota exige
aprovação específica do conteúdo pelo proprietário, inclusive para subtarefas.

## Contexto, cache e orçamento

O adaptador preserva o protocolo `ready/generate` existente de Hermes e Codex.
Não lê sessões do Desktop. Instruções e contexto obrigatório são preservados:
pedido, passos anteriores, código, snapshots, resultados QA, requisitos e aprovações.
Somente `optional_sections` explicitamente opcionais podem ser removidas por
irrelevância, duplicação ou limite; formatos desconhecidos preservam o original.
As passagens de memória são selecionadas pelo pedido/título/conteúdo e pelo espaço
disponível. Acrescentar conhecimento pode aumentar o contexto.

O cache é de **seleção de contexto**, não de respostas ou inferências. Sua chave
inclui projeto, papel, execução, etapa, instruções, conteúdo, versão das memórias,
permissões, limite e versão do algoritmo. Alterações invalidam a reutilização.
Credenciais conhecidas são recusadas antes de gravar contexto; cache e auditoria
continuam no banco privado. Hits/misses não significam chamadas de modelo evitadas.

Orçamentos cumulativos padrão: 500.000 tokens por projeto, agente no projeto e
execução. São limites adicionais aos tetos anteriores, que não foram flexibilizados.
Admissão reserva a estimativa de bytes do contexto/instruções mais margem de 32 mil.
Reservas e reconciliação são persistentes, serializadas e idempotentes.
Uso reportado pelo provedor pode superar a reserva: novas chamadas são bloqueadas,
mas não existe promessa de teto financeiro rígido para uma chamada já enviada.
Falhas/consumo desconhecido mantêm a reserva; não há expiração ou estorno automático.
A função de estorno exige comprovação de que a chamada não foi enviada.

Estimativas usam bytes UTF-8 serializados como margem conservadora, não tokenizer.
O painel separa estimativas, tokens reportados, reservas e economia medida.
**Economia real no provedor permanece indisponível:** não houve autorização para
comparação de inferências nesta entrega. Os workflows antigos preservam seu
contexto obrigatório completo; não se promete redução em toda chamada.

## Reprodução e evidências

```powershell
.venv\Scripts\python.exe -m pytest services/api/tests -q
.venv\Scripts\python.exe -m ruff check services/api
$env:AI_TEAM_SANDBOX_TESTS = '1'
.venv\Scripts\python.exe -m pytest services/api/tests/test_python_sandbox.py -q
Remove-Item Env:AI_TEAM_SANDBOX_TESTS
npm run lint
npm run typecheck
npm run build
npm run test:e2e
.venv\Scripts\python.exe tools/benchmark_optimizer.py
.venv\Scripts\python.exe tools/smoke_graphify.py
```

Não rode build e dev sobre a mesma pasta `.next` simultaneamente.
PostgreSQL real é verificado no workflow dedicado, em banco/usuário descartáveis,
incluindo reinicialização do cliente, isolamento, orçamento e deduplicação concorrente.
Testes de providers em Python/E2E usam dublês e não constituem homologação de inferência.

Resultados locais: 418 testes Python aprovados, 28 opt-ins ignorados; Docker real
27 aprovados; Playwright 29 aprovados; lint/typecheck/build aprovados. PostgreSQL
real: 12 aprovados no CI (run `42061964510`). Novas alterações após essa rodada
recebem regressões focadas e nova verificação no CI do PR.

Leitura externa real: GitHub App própria verificou a instalação atual e consultou
a Issue #1, aberta, sem publicar, editar, criar branches ou alterar permissões.
A publicação de uma nova Issue da V0.7 não é declarada homologada nesta rodada.
Graphify 0.9.93: consulta local exit 0, exportação Obsidian exit 0, duas notas,
um canvas e wikilink verificados; veja [limites do adaptador](v07-graphify.md).

Benchmark sintético com pedido/requisitos/aprovação idênticos:

| Cenário | Contexto original | Contexto selecionado | Redução de bytes |
|---|---:|---:|---:|
| Python | 3.200 bytes | 1.131 bytes | 64,66% |
| Interface | 3.088 bytes | 1.079 bytes | 65,06% |

São bytes de JSON de entradas sintéticas, não economia de tokens reais, preço,
qualidade comparada de respostas ou benchmark de produção. **Inferências reais: 0.**

Revisão final de segurança pelo implementador: escopo SQL/cache, credenciais,
concorrência, quarentena, caminhos Windows, protocolo de provider e aprovações.
Revisão independente final permanece pendente; revisões parciais dos módulos não
substituem essa etapa. CI verde também não equivale a homologação externa não executada.
