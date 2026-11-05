# V0.7.1 — revisão automatizada independente

Revisão em três agentes separados do implementador, em `8686559...33d9d2c`,
cobrindo os 61 arquivos originais do PR #11. Revisores não editaram arquivos nem
fizeram chamadas externas durante a revisão. Correções posteriores são revisadas
pelo implementador e validadas com regressões. **Não é revisão humana independente.**

| Frente | Cobertura | Resultado original |
|---|---|---|
| Memória e filesystem | memory models/store/routes/safety/vault, knowledge graph/routes/automation/models, db/config/main, deltas worker/workflow e testes correspondentes | P2: exportações concorrentes passam pelo mesmo digest e sobrescrevem uma à outra |
| Admissão e integrações | optimizer models/routes/selection/cache/benchmark, Issues models/store/routes, deltas GitHub actions/client, providers/worker/repository/workflow e testes | Nenhum bypass concreto de aprovação, cache ou escopo confirmado |
| Web e entrega | sete arquivos web, configuração/lock/versionamento, README/AGENTS/env, quatro documentos originais e tools | P2: reexportação sem revisão; P2: resposta inicial antiga sobrescreve estado novo; P3: busca vazia não restaura lista |

Reprodução do filesystem: duas threads revisaram o mesmo digest, bloqueadas por
barreira antes de criar temporários; ambas retornaram sucesso e somente uma
alteração permaneceu. Isso é concorrência normal, não ataque de administrador.

Reprodução da interface: reter a primeira resposta de grafo após snapshot vazio
de memórias, salvar nota/atualizar e liberar resposta antiga. A lista volta ao
snapshot vazio. Busca sem resultados seguida de busca vazia mantém lista vazia.
Exportar uma nota já exportada retorna 409 porque o painel enviava sempre `{}`.

Limites: inspeção estática e reprodução focada não provam ausência de defeitos.
Segredos e injection são tratados por defesa em camadas; regex não certifica
segurança de qualquer texto. ACL do vault continua obrigatória. Chamadas já
admitidas podem superar estimativas; reservas incertas não expiram. Metadados de
branch/SHA/PR não comprovam existência remota. Nenhuma revisão humana foi obtida.
