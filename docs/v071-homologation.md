# V0.7.1 — homologação final

Data: 05/11/2026. Branch `codex/ai-team/v07-memoria-optimizer`, PR #11.
Base V0.7: `33d9d2c`, com seus 27 commits preservados. Main não foi modificada.
Nenhum merge, deploy, squash, rebase, force push ou ampliação de permissões.

## Resultado

- Revisão automatizada independente dos 61 arquivos originais, em três frentes;
  quatro achados iniciais e uma corrida adicional receberam correções/regressões.
  Não se declara revisão humana independente. [Cobertura e resolução](v071-independent-review.md).
- Vault: exclusão mútua entre processos, digest/ausência rechecados antes da
  substituição; painel permite revisar arquivo atual, conteúdo proposto, versão,
  confirmar ou cancelar reexportação. Novos testes cobrem conflito de conteúdo,
  criação externa, falha de escrita, auth, escopo e versão SQL alterada.
- Painel: geração de requisições impede snapshots antigos de sobrescrever estado
  novo; busca vazia restaura lista. Escritório Pixel Art e `/ceo` preservados.
- Benchmark A/B offline: pares determinísticos, mesmo contexto inicial/instruções/
  modelo/parâmetros, digests, recibos vinculados, tokens de entrada/saída/total,
  duração, cache e rubrica manual. Fixtures e bytes permanecem separados.
  JSON funciona também em consoles Windows não UTF-8.

## GitHub Issues — integração real

O proprietário autorizou especificamente uma única publicação pelo digest
`d39f225c1d78ab4daa318239ce06a7a97a30c049af3fb6e4dbba7702401991ed`.
App própria criou [Issue #12](https://github.com/igorcastro1010/ai-team/issues/12).
GET confirmou título/corpo aprovados; sync persistiu `open`; segunda admissão não
encontrou trabalho. Auditoria: proposta → decisão → sucesso → sincronização.
Issue permanece aberta, sem edição. [Conteúdo e evidência](v071-issue-proposal.md).

Criação/deduplicação locais foram executadas em banco isolado e persistente de
teste. Falhas, concorrência, payload alterado e resultado incerto têm testes de
contrato; não são falhas provocadas no GitHub real. Não se repetiu POST incerto.
Também foram verificadas instalação seletiva e leitura da Issue #1, sem alterá-la.

## Token Optimizer — medição e pendência

**Inferências reais nesta rodada: 0. Tokens reais consumidos: 0. Economia real de
tokens: não medida.** Não há autorização específica de cota/orçamento para A/B.
Recibos sintéticos dos testes não são evidência de uso real do provider.

[Protocolo e comandos A/B](v071-token-benchmark.md) preparados. Exemplo reproduzido
localmente: 610 → 537 bytes UTF-8 de entradas serializadas, não tokens; digest do
par `157330c5d0d23bbc32d128de0a38015e41477cbc1f5ddd3bbdfbe3752d9ba302`.
Identidade do modelo nesse exemplo é placeholder explícito; nenhum modelo foi
invocado ou declarado validado. O CLI não possui opção de inferência.

O analisador não autentica recibos fornecidos. Antes de divulgar economia real,
conferir origem, modelo efetivo, parâmetros suportados, qualidade sob a mesma
rubrica, cache, duração e execução autorizada. Scores iguais não provam equivalência.

## Verificações executadas

| Verificação | Resultado |
|---|---|
| Python completo, Windows | 454 aprovados, 28 opt-ins ignorados |
| Docker real, sandbox Python | 27 aprovados |
| PostgreSQL real, CI descartável | 12 aprovados, run `42079091768` |
| Playwright completo | 31 aprovados, incluindo `/memoria`, `/ceo`, Pixel Art, mobile e auth/CSRF |
| Ruff, ESLint, typecheck, build | Aprovados |
| Graphify 0.9.93 offline | Query/export exit 0, duas notas, canvas e wikilink verificados |
| GitHub App | Criação #12, leitura, sincronização, digest e auditoria reais |

Logs privados ignorados: `artifacts/v071-python-verified.log`, `v071-docker.log`,
`v071-e2e.log`, `v071-lint-final.log`, `v071-typecheck.log`, `v071-build.log`,
`v071-issue-result.json`, `v071-ab-pair.json`. Não há segredos versionados.
As primeiras regressões falharam antes das correções (RED/GREEN); uma rodada
Python iniciada durante alterações do benchmark foi substituída pela rodada
final estável acima. Dublês de inferência não contam como homologação externa.

Reprodução: comandos no [guia V0.7](v07-memory-optimizer.md), mais:

```powershell
.venv/Scripts/python.exe -m pytest services/api/tests/test_vault_concurrency.py services/api/tests/test_vault_export_review.py services/api/tests/test_optimizer_ab_benchmark.py -q
npm run test:e2e --workspace @ai-team/web -- knowledge.spec.ts vault-export.spec.ts
git rev-list --count 33d9d2c..HEAD
git log --reverse --format="%H %s" 33d9d2c..HEAD
```

Não executar build e dev na mesma `.next` simultaneamente. E2E usa banco e vault
descartáveis próprios. CI e SHAs finais são conferidos e registrados no PR #11
após o último push; consulte os checks vinculados ao HEAD, não a um SHA antigo.

## Limites operacionais

O lock `.nome.md.lock` é exclusivo entre escritores AI TEAM. Se o processo morrer,
o lock pode permanecer: pare API/worker e editores, confira que não há exportação
ativa e somente então remova manualmente o lock específico. Sem expiração ou
remoção automática de locks alheios.

Obsidian não participa desse protocolo. A rechecagem final não garante CAS atômico
contra edições externas entre a última leitura e a substituição; conclua/pare
edições antes de confirmar. ACL continua obrigatória, sem defesa prometida contra
administrador ou processo hostil alterando diretórios. Graphify é offline;
segredos/injection têm defesa em camadas, sem detecção universal por regex.
Reservas incertas e chamadas admitidas que ultrapassem estimativas mantêm os
limites documentados na V0.7. Vault pessoal não foi acessado.

Próximos passos: revisão humana do PR; se desejado, autorização específica de
quota/modelo/admissões para comparar inferências reais. Nenhuma V0.8 foi iniciada.
