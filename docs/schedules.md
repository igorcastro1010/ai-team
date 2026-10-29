# Agendamentos textuais

O painel permite autorizar um prompt imutável, projeto, modo, início e recorrência. Intervalos de 1 hora a 7 dias, início nos próximos 7 dias, de 1 a 5 ocorrências e autorização válida por 30 dias. Horários exibidos em America/Fortaleza; banco usa timestamps UTC.

O scheduler apenas cria execuções na fila. O worker separado chama o Codex com seu login próprio. Manual pede aprovação entre etapas; supervisionado pede após o plano CEO; automático autoriza as cinco etapas textuais. Nenhum modo permite shell, deploy ou aprovar ações GitHub automaticamente. Cada ocorrência mantém os limites existentes de cinco chamadas e limiar de 50 mil tokens antes da próxima reserva. O último retorno pode ultrapassar esse limiar; custo monetário não é mensurado nem limitado pela API do login ChatGPT.

Não há sobreposição de ocorrências da mesma agenda, inclusive durante aprovação ou bloqueio do Codex. Após parada do Windows, apenas uma ocorrência vencida é criada; a próxima data parte do instante atual. Contador, execução, vínculo e evento são gravados na mesma transação. CAS e chave composta protegem contra dois schedulers. Cancelamento impede novas ocorrências; use Execuções para cancelar uma já criada. Agendas encerradas permanecem no histórico e não podem ser editadas ou reativadas.

## Windows e processo separado

`powershell -NoProfile -File .\tools\start.ps1` inicia API, painel, worker e scheduler locais. Ctrl+C encerra os processos iniciados pelo script. O Windows precisa permanecer ligado; esta versão não instala serviço ou tarefa no Agendador do Windows.

Para execução separada, após `ai-team init-db`:

```powershell
.\.venv\Scripts\python.exe -m ai_team.scheduler
# Um único ciclo, sem executar IA:
.\.venv\Scripts\python.exe -m ai_team.scheduler --once
```

Logs ficam em `.data/scheduler.stdout.log`, ignorados pelo Git e sem prompts/segredos. Produção exige banco PostgreSQL privado inicializado previamente, worker/scheduler sempre ativos e hospedagem aprovada; não usar Vercel Functions para esses processos. Nenhuma agenda é criada automaticamente pela instalação.
