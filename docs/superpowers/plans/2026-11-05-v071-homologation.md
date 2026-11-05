# V0.7.1 — plano de homologação

**Objetivo:** revisar os 61 arquivos da V0.7, corrigir regressões comprovadas e
preparar evidências reproduzíveis sem inferência ou escrita remota não autorizada.
**Arquitetura:** preservar os adaptadores, banco e fila existentes. Benchmark A/B
offline prepara entradas pareadas e valida recibos separados de métricas sintéticas.
**Base:** `33d9d2c`, 27 commits sobre `8686559`; PR #11, mesma branch.

- [x] Conferir árvore limpa, base e seis checks verdes antes de novas execuções.
- [x] Revisão automatizada independente em três frentes: memória/vault/grafo;
  orçamento/cache/Issues/execução; interface/proxy/testes/documentação.
- [x] TDD: preparar comparação A/B reproduzível com identidade de modelo/parâmetros,
  digest de entradas, tokens de provedor separados de bytes, tempo e qualidade.
  Não executar chamadas; autorização anterior da V0.6 não se aplica.
- [x] Preparar Issue de teste com conteúdo fixo, digest e deduplicação local;
  solicitar aprovação específica antes de publicar. Não ampliar permissões.
- [x] Para cada achado confirmado: regressão vermelha, correção mínima, testes,
  commit convencional e push da entrega validada.
- [x] Reexecutar Python, Docker, PostgreSQL, Playwright, Ruff, ESLint, typecheck,
  build e Graphify offline; conferir CI do último SHA.
- [x] Atualizar relatório/README/PR com evidências, novos SHAs, limitações e
  distinção entre revisão automatizada e revisão humana.

Não fazer merge, deploy, squash, force push ou alterações na main. Artefatos de
execução ficam ignorados; somente documentação sem segredos é versionada.

Evidências e limites: docs/v071-homologation.md. Inferência externa não executada; Issue #12 publicada somente após aprovação específica. Revisão independente automatizada, sem revisão humana. CI do último push é conferido no PR.
