# V0.6 — execução em repositório autorizado

Plano de implementação incremental na branch `codex/ai-team/v06-agentes-executores`.

## Decisões de escopo

- Reutilizar sessões, fila Run, leases, worker, provedores próprios e sandbox Python.
- Primeiro perfil: Python 3.12/biblioteca padrão e documentação Markdown, até 12 arquivos
  explicitamente autorizados de uma pasta de `igorcastro1010/ai-team`, congelados em SHA.
- CEO → PESQUISADOR → DEV → DESIGNER → QA → CEO. Pesquisa limitada aos arquivos
  autorizados; não representa navegação na internet. Nenhum modelo recebe shell ou tokens.
- Git local por tarefa, sem remotes, hooks, credenciais ou execução do código no host.
- Testes somente no Docker sem rede, 1 CPU, 256 MiB e 30 s. Aprovação do digest antes
  dos testes; resultado, diff e proposta de PR persistidos. Falhas não viram sucesso.
- Aprovação final vinculada a SHA, arquivos e resultado. Nunca merge ou deploy.
- Escritas remotas são uma etapa separada: não confundir proposta persistida com PR publicado.

## Entregas e validação

1. Contratos de caminhos, autorização e artefatos; testes negativos antes da implementação.
2. Snapshot GitHub somente leitura e workspace Git privado com diff verificável.
3. Persistência, seis agentes, checkpoints, aprovação e execução independente dos testes.
4. API autenticada, painel e escritório alimentados por estados persistidos.
5. Recuperação/cancelamento, testes de regressão, homologação com provedor e Docker reais.
6. Documentação e PR de desenvolvimento sem merge/deploy.

Cada entrega terá testes direcionados, commit convencional e push. A release depende de
pytest, lint, typecheck, build e E2E; mocks cobrem contratos, não homologação do provedor.
