# Benchmark A/B V0.7.1 — preparado, sem inferência

Esta rodada não tem autorização específica de cota/orçamento. **Chamadas reais:
zero; consumo real e economia percentual real: não medidos.** Autorizações da
V0.6 não são transferidas. O CLI abaixo não tem opção de executar inferências.

## Preparação reproduzível

Crie `artifacts/ab-input.json` localmente, sem dados sensíveis:

```json
{
  "provider": "hermes",
  "model": "SUBSTITUIR_PELO_MODELO_EFETIVAMENTE_CONFIGURADO",
  "params": {},
  "instructions": "Responda em português. Preserve requisitos e limites. Não use ferramentas.",
  "context": {
    "request": "Documentar uma fila Python com cancelamento",
    "requirements": ["Biblioteca padrão", "Sem credenciais", "Sem publicação"],
    "approvals": {"approved": false},
    "optional_sections": [
      {"content": "Fila Python: worker separado e cancelamento cooperativo."},
      {"content": "Fila Python: worker separado e cancelamento cooperativo."},
      {"content": "Catálogo de viagens sem relação com a tarefa."}
    ]
  },
  "memories": [],
  "budget": 50000
}
```

```powershell
.venv/Scripts/python.exe tools/prepare_optimizer_ab.py artifacts/ab-input.json
.venv/Scripts/python.exe tools/prepare_optimizer_ab.py artifacts/ab-input.json --receipts artifacts/ab-receipts.json
```

O par preserva o mesmo contexto inicial, instruções, modelo e parâmetros. O braço
baseline recebe contexto original; o otimizado recebe somente a transformação
definida pelo otimizador. Digests vinculam identidade, entradas e par. Bytes
serializados são separados de tokens. O cache de seleção não é usado neste
harness offline e não deve ser apresentado como cache do provedor.

## Rodada futura, somente após autorização

Antes de enviar qualquer chamada, registrar autorização, provider/modelo efetivo,
parâmetros suportados, limite de admissões e orçamento. Usar processos próprios e
os adaptadores existentes, sem importar sessões do Desktop. Não presumir suporte
a temperature/seed no Hermes ou Codex; fixar somente opções efetivamente disponíveis.

Executar ambos os braços com as mesmas configurações, sem reutilizar resposta de
um no outro. Para reduzir viés de aquecimento, alternar a ordem em pares repetidos
se a autorização comportar; amostra única não prova resultado generalizável.
Interromper novas admissões em 429, timeout, orçamento ou uso desconhecido.
Não repetir automaticamente uma chamada enviada com resultado incerto.

Guardar evidência privada por braço: SHA do código, digest da entrada, modelo
efetivo, recibo original do provider sem segredos, input/output/total tokens,
cache informado pelo provider (desconhecido não é zero), duração monotônica,
artefato produzido e avaliação manual sob a mesma rubrica de requisitos,
correção e segurança. Conferir recuperação de contexto e proveniência separadamente.

O analisador recebe uma lista JSON de dois recibos com: `arm` (baseline/optimized),
`pair_digest`, `input_digest`, `provider`, `model`, `params`,
`provenance: "provider_reported"`, `evidence_kind: "provider_receipt"`,
`status: "completed"`, `input_tokens`, `output_tokens`, `total_tokens`,
`duration_ms`, `cached_input_tokens` e
`quality: {"method":"manual_rubric","rubric":"identificador da rubrica","score":1}`.
Contagens desconhecidas ou incompletas impedem estabelecer economia; não preencher
lacunas com estimativas. O total deve ser a soma dos componentes compatíveis do
provider. Sem esse detalhamento, manter comparação pendente.

Percentual por componente: `(baseline - optimized) / baseline * 100`; baseline
zero produz percentual indisponível. Aumento de uso resulta percentual negativo.
Qualidade é exibida separadamente; scores iguais não provam equivalência.
Fixtures usam `evidence_kind: "fixture"` e ficam em campos sintéticos separados.

O analisador valida consistência e associação dos recibos fornecidos, **não
autentica sua origem**. Digests não são assinatura do provider. Resultados só
podem ser apresentados como homologação real após conferir recibos e execução;
os testes unitários do analisador não são evidência de inferência real.
