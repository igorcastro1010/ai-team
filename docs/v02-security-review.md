# V0.2 — revisão e evidências

## Fronteiras
API autenticada só enfileira pedidos consentidos. O worker executa uma etapa por claim, com CAS e lease; resultado também depende do token da lease. Aprovar exige status pendente e etapa esperada. Cancelar invalida a lease e o subprocesso monitora o cancelamento. Nenhum endpoint fornece shell ou writes externos.

Os subprocessos Codex usam keyring próprio, ambiente filtrado, schema estrito e configuração restrita. Sem herdar config/rules do usuário, shell, plugins, apps, execução unificada, Web ou subagentes. Perfil oficial de permissões: raiz negada, runtime mínimo e workspace da chamada somente leitura; rede de ferramentas desabilitada. Nenhum fallback para full access.

## Achados da revisão independente
1. Write bloqueante no pipe antes do timeout: reproduzido com 200 KB e filho que não lê stdin. Corrigido para arquivo temporário redirecionado como stdin, com monitoramento imediato. Regressão automatizada.
2. Aprovação antiga escondida após 200 execuções posteriores: reproduzida em banco isolado. Corrigida com consulta de pendências antes do limite, ordenada das mais antigas. Regressão automatizada.

## Homologação real
- Login próprio confirmado sem ler/copy de cache do Desktop.
- CLI oficial testado: `0.163.0-alpha.10.2`, binário disponível no Windows. Compatibilidade de outros builds requer teste explícito; não flexibilizar permissões.
- Fluxo autenticado em banco temporário: solicitação -> CEO -> decisão sintética -> DEV -> DESIGNER -> QA -> CEO, com cinco processos worker separados e checkpoints SQL.
- Resultado: cinco etapas e cinco chamadas concluídas; 56.953 tokens reportados pelo CLI. Isso não é valor monetário nem total de toda a sessão de desenvolvimento.
- Após a correção do stdin, teste com canário sintético fora do workspace: conteúdo não foi retornado; resposta informou ausência de acesso autorizado. O caso foi observado com o perfil ativo; não prova isolamento contra todo ataque ou em outros sistemas operacionais.
- Evidências locais ignoradas no Git: `artifacts/codex-smoke.json`, `artifacts/codex-boundary.json`.

## Limitações materiais
Sem teto financeiro rígido por CLI/conta ChatGPT; máximo de cinco chamadas e 120s por chamada. Limiar de 50 mil tokens verificado entre chamadas, com possibilidade de ultrapassagem durante a chamada corrente. Cancelamento não desfaz consumo já enviado. Não há retry automático de chamadas incertas. Checkpoints da aplicação salvam fronteiras de etapas, não retomam uma inferência interrompida. Persistência PostgreSQL e sandbox fora deste Windows ainda não homologados.

Skills aplicadas: LangGraph fundamentals, referência Python, persistence e human-in-the-loop; Supabase Postgres para fila/schema; Playwright, React e UI/UX para painel; revisão de segurança de prompts; TDD e revisão independente para concorrência e limites.
