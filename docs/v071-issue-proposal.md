# Issue de teste — proposta para aprovação

Repositório único: `igorcastro1010/ai-team` (público). Preparada em banco local
isolado de homologação, sem worker ativo. Não publicada nem aprovada.

Título: **[Homologação V0.7.1] GitHub Issues supervisionado**

Corpo exato:

```text
Issue de teste do AI TEAM V0.7.1 (PR #11).

Objetivo: validar uma criação pela GitHub App própria, leitura e sincronização do estado remoto, com deduplicação local e aprovação vinculada ao digest.

Escopo: somente igorcastro1010/ai-team; sem código, branches, merge, deploy ou alteração de outras Issues. Esta Issue permanecerá aberta; fechar ou editar exige autorização separada.

Identificador persistente: v071-supervised-issue-homologation-01.
Nenhum teste de inferência ou dado sensível integra esta Issue.
```

Digest do payload completo da ação (modelo `Proposal`, incluindo defaults):
`d39f225c1d78ab4daa318239ce06a7a97a30c049af3fb6e4dbba7702401991ed`.
Projeto de teste: `07107107-1071-4071-8071-071071071071`.
Request ID: `v071-supervised-issue-homologation-01`.

Validação local real: duas chamadas `IssueStore.create` retornaram o mesmo ID;
`GitHubStore.claim()` não admitiu ação pendente. Zero escritas externas.
Publicação deve usar esta ação/digest e a App própria pelo executor existente,
seguida somente de GET/sync. Resultado incerto exige reconciliação, sem novo POST.
Recriar a proposta após falha não autoriza duplicar uma Issue remota.
