# V0.6.1 — homologação final em ambiente de testes

Data: 05/11/2026. PR [#10](https://github.com/igorcastro1010/ai-team/pull/10),
branch `codex/ai-team/v06-agentes-executores`. Versão Web/API: **0.6.1**.

**As seis etapas Hermes foram homologadas com inferência e Docker reais.**
A entrega multifile foi validada localmente até a prévia anterior à autorização
externa. Nenhum artefato gerado foi enviado a uma branch remota; nenhum PR de
artefatos, merge, deploy, permissão adicional ou provedor pago foi criado.
O CI do HEAD é acompanhado nos [checks do PR](https://github.com/igorcastro1010/ai-team/pull/10/checks).

## Execução real

- Run: `b200d06f-4738-4042-b557-830641285afa`.
- Snapshot via GitHub App própria, somente ai-team, no SHA
  `0f05ac93cdbc1d543f1dac327f6b7fc7f23e4cea`.
- Banco descartável privado, proprietário de teste, aprovação de sandbox por
  digest e worker real. Não reutiliza banco, sessão ou credenciais do Desktop.
- **6 admissões**, todas `remote_status=completed` e `bridge_status=succeeded`.
  Nenhuma nova inferência foi solicitada depois da sexta.

| Etapa | Agente | Entrada | Saída | Total |
|---|---|---:|---:|---:|
| Planejamento | CEO | 1.538 | 781 | 2.319 |
| Pesquisa do snapshot autorizado | PESQUISADOR | 2.391 | 1.030 | 3.421 |
| Código Python | DEV | 3.545 | 515 | 4.060 |
| Guia de uso | DESIGNER | 3.990 | 1.651 | 5.641 |
| Testes unittest | QA | 5.631 | 2.328 | 7.959 |
| Revisão do diff e resultado Docker | CEO | 13.533 | 695 | 14.228 |
| **Total** | | **30.628** | **7.000** | **37.628** |

O teto desta tarefa foi 78.000 tokens. Somando os 21.894 informados na tentativa
Hermes anterior, são **59.522 tokens informados entre as duas rodadas**. O uso
desconhecido da chamada anterior recusada por cota não é declarado como zero.
Nenhuma API paga ou fallback foi contratado. Tokens não são convertidos em
custo monetário quando o provedor não informa esse custo.

DEV preservou `remaining_tokens` e os valores das constantes, acrescentou
`summarize_usage` com validações de tipos/limites. DESIGNER produziu guia em
português; QA gerou testes independentes. O Docker executou **15 testes, todos
aprovados, exit code 0**. CEO recebeu a saída real e consolidou a revisão.
Código, guia e testes permanecem no workspace isolado e no ZIP privado; não
foram aplicados ao checkout de desenvolvimento nem publicados.

O DESIGNER deste perfil produz Markdown. Edição de interfaces TSX em repositórios,
Bot Mode e delegação nativa Hermes continuam fora desta homologação. Os seis
papéis são orquestrados por LangGraph e usam o adaptador oficial Runs do Hermes.

## Proteção de segredos e HTTP 429

A falha anterior permanece em [estabilização](v061-stabilization.md). Não era uma
falha simulada: o código recebido continha uma constante substituída por `***`
e a sexta chamada foi recusada pela cota da assinatura.

Constantes numéricas agora são solicitadas com anotação de tipo, como
`MAX_TOKENS: int = 50_000`. Código proposto inválido é rejeitado por AST antes
de escrever/aprovar artefatos; snapshots quebrados continuam legíveis para reparo.
Não há execução/importação do código gerado no host.

O probe do contêiner oficial verifica JSON aninhado com constantes tipadas e
confirma que uma chave sintética continua sendo ocultada. A proteção não foi
desligada, o runtime não foi alterado e não foram autorizadas ferramentas novas.

429 agora fecha a admissão, sem repetir inferência. `Retry-After` em segundos ou
data HTTP é respeitado; sem valor válido, a espera exponencial começa em 60 s e
chega a 3.600 s. Um prazo válido maior do servidor prevalece. O prazo é persistido
em auditoria e compartilhado por worker, monitor e rotas de controle, inclusive
429 durante `/stop`. Consultar um bloqueio não renova seu prazo. Stop explícito
continua disponível para tentar encerrar uma execução já admitida.

Não houve novo 429 na rodada final. Casos de 429, reinício, clientes distintos e
cancelamento são regressões de contrato; não são apresentados como uma nova
inferência real deliberadamente limitada. Chamadas concluídas não são readmitidas
automaticamente: o journal mantém referências remotas e checkpoints. A rodada
anterior com código inválido não podia ser reaproveitada como entrega aprovada.

Referências: [RFC 9110, Retry-After](https://httpwg.org/specs/rfc9110.html#field.retry-after)
e [segurança oficial Hermes](https://github.com/NousResearch/hermes-agent/blob/main/skills/autonomous-ai-agents/hermes-agent/references/security-privacy.md).

## Multifile: validação até a autorização externa

Arquivos reais no snapshot/plano:

1. `services/api/ai_team/execution_limits.py` — código alterado.
2. `services/api/ai_team/execution_guide.md` — documentação nova.
3. `services/api/ai_team/test_execution_limits.py` — testes novos.

O preparador confere o checkpoint, a aprovação dos testes, seu resultado, os
bytes UTF-8 e os blobs/modos do índice Git, o diff persistido, ausência de remote,
branch UUID da tarefa e ausência de mudanças extras. O manifesto inclui árvore
Git local, SHA-256 por arquivo, consumo, hash da saída de testes e corpo de
Git Tree proposto. A consulta GitHub é somente leitura; gerar um manifesto não
invoca `/publish` nem concede autorização externa.

Vínculos confirmados:

- Checkpoint da revisão aprovada:
  `d368decb1f8e4a496215827c88a1ce315a3a64d9a9af37c3ae7add510160e445`.
- Digest de execução/aprovação Docker:
  `dacd45927f7d172a3918ae6c695a24c9bfc695b572b5509b6172eecb4a057c47`.
- Bundle/política:
  `2dd3031deb589fdb0a1bcdb196b4e19ef0d2a595c1a28f9f1eceafdf305f78d9`.
- Árvore Git local:
  `dba2c162862bbca0e95dfe8df793c902771e6952`.

A revisão final foi aprovada somente no banco descartável, com evento de
auditoria e digest exato. A autorização externa **não foi solicitada nem gravada**:
`publication_authorized=false`, `published=false`, sem estado de entrega remota.

A branch de desenvolvimento avançou após o snapshot, como esperado durante as
correções. A pré-checagem registra `base_branch_matches=false`; o executor recusa
publicar esse plano sobre uma origem diferente. Uma publicação futura exige
revisão da base atualizada e autorização específica do novo digest/SHA. Essa
recusa é uma proteção validada, não uma publicação remota homologada.

## Evidências reproduzíveis privadas

Arquivos ignorados pelo Git, sem credenciais no pacote:

- `artifacts/v06-repository-hermes-smoke.json` — seis passos e resultados reais.
- `artifacts/v061-prepublication-b200d06f-4738-4042-b557-830641285afa.json` — manifesto.
- Mesmo nome com `.zip` — três arquivos, diff, saída Docker e manifesto.
- `.data/v06-hermes-smoke-*.db` — journal, auditoria e checkpoints. Esse banco
  contém autenticação sintética de teste e não deve ser publicado.
- `artifacts/v061-hermes-first-failure.json` — falha anterior preservada.

Rever a entrega já existente não consome inferência nem publica:

```powershell
.venv/Scripts/python.exe tools/prepare_repository.py --evidence artifacts/v06-repository-hermes-smoke.json
```

`--approve-test-review` serve somente para a revisão local no banco descartável;
não autoriza publicação. O script recusa bancos fora do contrato `.data/v06-*-smoke-UUID.db`.
Não executar novamente o script `smoke_repository.py --real`: as seis admissões
autorizadas desta rodada já foram utilizadas.

## Qualidade e limites da entrega

- Python completo: **345 passed, 25 skipped**. Opt-ins executados separadamente.
- Suíte PythonSandbox com Docker real habilitado: **27 passed**, incluindo
  isolamento, timeout, cancelamento, watchdog, saída e encerramento prematuro.
- Playwright completo: **27 passed**, incluindo `/ceo`, escritório, aprovações,
  autenticação/CSRF, responsividade e regressões de integrações.
- PostgreSQL real: **10 passed**, incluindo consumo concorrente e cooldown após
  reconexão; [evidência CI](https://github.com/igorcastro1010/ai-team/actions/runs/42020894319).
- Ruff, ESLint, typecheck e build de produção aprovados. Metadados Web/API e
  OpenAPI em memória conferidos em 0.6.1; instalação editable atualizada.
- Segundo revisor somente leitura: nenhum problema acionável remanescente.
- Projeção do escritório com o run real: cinco especialistas/CEO concluídos,
  sem animação de trabalho após término; papéis futuros permanecem disponíveis.

Fixtures em testes de transporte/E2E não contam como homologação de inferência.
O orçamento limita novas admissões; uma resposta em andamento pode ultrapassar
o teto. Testes gerados não são uma atestação inviolável contra código malicioso.
O perfil continua restrito a Python padrão/Markdown, sem rede no sandbox e com
aprovações humanas obrigatórias para os conteúdos indicados.

O PR permanece para revisão, sem merge/deploy. A base desta rodada contém 41
commits preservados. Novos SHAs e quantidade são reproduzidos por
`git log f550dfc..HEAD --format='%H %s'` e exportados no registro privado final;
o histórico completo permanece sem squash ou commits vazios.
