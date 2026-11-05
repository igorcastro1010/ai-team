# V0.7 — relações locais e Graphify

O painel consulta `GET /knowledge/{project_id}/graph`, autenticado como proprietário.
O retorno contém `project_id`, `nodes`, `links`, `truncated` e `source: native`.
Cada nó tem `id`, `kind`, `label` e `provenance`; cada relação tem `source`, `target`,
`relation` e `provenance`. IDs e proveniência identificam registros, sem incluir corpo
de notas, prompts, entregáveis, conteúdo de commits, tokens ou URLs de integração.

O grafo é uma projeção dos dados SQL persistidos. Não é uma resposta de modelo nem
um detector de relações semânticas. Projetos, tarefas, papéis atribuídos, execuções,
decisões registradas, títulos de memórias e ações GitHub compartilham o mesmo escopo
de projeto. Referências a Issue, branch, commit e PR exigem resultado bem-sucedido
da fila GitHub. Entregas em repositório exigem estado `published` e digest revisado;
SHAs, namespace de branch e URL do PR no repositório selecionado são validados.
Pendências e propostas não se apresentam como objetos remotos já criados.

O limite padrão/máximo é 500 nós e 2.000 relações; `?limit=100` permite reduzir os
nós retornados. Consultas SQL são limitadas e ordenadas; a resposta marca truncamento
e omite arestas cujos nós não couberam. Agentes aparecem quando existem atribuições
ou etapas registradas. Não há cache global nem acesso ao conteúdo de outro projeto.

## Intercâmbio opcional em disco

`GraphifyAdapter(root)` recebe uma raiz definida pelo operador no servidor; nenhum
request, modelo ou memória escolhe caminhos. `export(project_id, snapshot)` grava
`<root>/<project_id>/graph.json`; `read(project_id)` importa somente o subconjunto
node-link validado abaixo. `write(project_id, graph)` valida antes de gravar.
Importação não altera registros SQL, instruções, políticas, aprovações ou a resposta
nativa do painel. Não existe endpoint público para importar arquivos ou executar CLI.

```json
{
  "directed": true,
  "multigraph": false,
  "graph": {"project_id": "example", "schema_version": 1},
  "nodes": [
    {"id": "memory:one", "label": "Planejamento", "kind": "memory",
     "provenance": "memory_entries:one"}
  ],
  "links": []
}
```

O limite de arquivo é 512 KiB, lido com teto antes de decodificar. A validação rejeita
nós/relações duplicados, arestas pendentes, tipos não permitidos, metadados extras,
atributos `source_file`, caminhos arbitrários, controles e padrões conhecidos de
credenciais. Identificadores de projeto rejeitam travessia, unidades Windows, UNC,
ADS e nomes de dispositivo. Symlinks e junctions em qualquer ancestral são recusados;
a gravação usa arquivo temporário e substituição atômica.

A raiz precisa ficar sob controle exclusivo do processo/operador confiável, sem
permissão de escrita de usuários não confiáveis: verificações de caminho por si só
não isolam um invasor local que pode trocar diretórios concorrentemente. A detecção
de segredos reconhece padrões conhecidos, não garante reconhecer todo texto secreto;
por isso os corpos sensíveis não entram na projeção.

Este formato é um subconjunto seguro de Graphify, não um importador genérico de todo
`graphify-out/graph.json`. Grafos externos precisam ser revisados e normalizados pelo
operador. Não são aceitos atributos de confiança `INFERRED`, hipera-restas ou campos
que possam carregar conteúdo/caminhos não revisados. Sem inferência, embeddings,
hooks, serviço hospedado Graphify, alteração global de configuração ou publicação.

## CLI oficial e verificação Windows

Origem revisada: [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify).
A documentação distingue AST local de passes semânticos que podem chamar modelos.
Nesta entrega usamos apenas comandos documentados `query` e `export obsidian`, que
consomem JSON já disponível. Não executar `extract`, `label`, `add`, `watch`, instalação
de hooks ou extração semântica como parte do painel. Graphify não é dependência para
iniciar API/worker. Não foi instalado pacote adicional nesta etapa.

Com uma instalação local previamente revisada:

```powershell
.venv\Scripts\python.exe tools\smoke_graphify.py --binary C:\Users\igorc\.local\bin\graphify.exe
.venv\Scripts\python.exe -m pytest services\api\tests\test_knowledge_graph.py -q
```

O smoke usa um grafo sintético de dois nós em diretório temporário privado. O processo
recebe ambiente mínimo de sistema, HOME/APPDATA temporários e nenhuma chave, cookie,
sessão Codex ou proxy herdado. Os argumentos são listas fixas, sem shell; cada chamada
tem timeout de 30 segundos. Saída bruta do CLI fica no temporário e não é exibida.
O temporário é removido ao terminar.

Evidência local em 05/11/2026: Graphify **0.9.93**, `--version`, `query` com seed/budget
e `export obsidian` terminaram com código 0. A consulta encontrou ambos os nós.
O export gerou **2 notas Markdown e 1 canvas**, com wikilink `[[Scheduler]]`, relação
`documents` e aresta no canvas. Nenhum hook foi instalado e nenhuma chamada de
inferência foi feita. O smoke confirma compatibilidade de arquivos, sem abrir o app
Obsidian; sincronização por plugins, vault pessoal e serviços remotos não foram usados.

Para uso manual em JSON previamente revisado, os comandos oficiais são:

```powershell
graphify query "Planejamento" --graph C:\raiz-privada\example\graph.json --budget 100
graphify export obsidian --graph C:\raiz-privada\example\graph.json --dir C:\vault-privado
```

Os caminhos desses exemplos são definidos pelo operador; a aplicação não executa
essas strings. Exportar uma nota não a transforma em evidência, permissão ou instrução
confiável para os agentes.
