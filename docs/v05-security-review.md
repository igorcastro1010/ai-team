# Revisão V0.5

## Escopo
Recorrências imutáveis e limitadas, processo scheduler separado, API/painel autenticados e relatório agregado com histórico paginado. Sem deploy, novas credenciais ou inferência real nesta etapa.

## Garantias verificadas
- Consentimento obrigatório; modo, prompt, projeto e limites persistidos na autorização. Campos extras de escopo são rejeitados.
- Início futuro nos próximos sete dias, intervalo de 1 hora a 7 dias, até cinco ocorrências e validade de 30 dias. Modo do projeto não altera o modo já autorizado na agenda.
- CAS no registro de agenda, verificação de ocorrência ativa após bloqueio e transação única para contador, data, Run, vínculo e auditoria. Restrição composta impede repetição do número da ocorrência.
- Dois schedulers concorrentes geram uma ocorrência. Falha ao inserir a execução reverte contador e data; cancelamento concorrente impede gerações posteriores. Ocorrência enfileirada antes do cancelamento mantém sua autorização e precisa de cancelamento próprio.
- Scheduler não importa provedor, cofre ou ferramentas GitHub. Processo real `--once` testado duas vezes no banco temporário, sem inferência e sem duplicação.
- Ocorrência automática sintética percorreu as cinco etapas no worker existente com provedor de teste; cinco chamadas e resultado persistido. Não foi criada recorrência no banco de uso real.
- Autenticação, Origin/CSRF, decisões existentes e limite de corpo do proxy preservados. Relatório não exporta prompts, respostas, leases ou sessões.
- Total SQL e cursor com desempate por ID testados com 205 execuções, além do limite do workspace. E2E cobre criação/cancelamento, exportação JSON, cursor, navegação móvel e axe.

## Revisão independente
Encontrou-se starvation: o limite de vinte agendas era aplicado antes de excluir as ocupadas. Vinte ocorrências aguardando aprovação impediam as seguintes de gerar. Teste reproduziu zero gerações incorretamente; corrigido com NOT EXISTS antes do limite, mantendo a segunda verificação sob bloqueio. Segunda revisão confirmou a correção e não encontrou novos defeitos relevantes no painel/proxy de relatórios.

## Limites
Concorrência homologada em SQLite temporário; PostgreSQL hospedado ainda precisa de homologação. Máquina desligada não executa scheduler/worker; nenhum serviço Windows é instalado. Não há teto monetário verificável: limiar de tokens impede reservar a próxima chamada, mas o último retorno pode excedê-lo. Contagem de chamadas inclui reservas; respostas que falharam podem não informar todos os tokens. Autorização expirada impede novas ocorrências, sem revogar execuções já criadas. GitHub exige aprovação separada e continua limitado a documentos no ai-team. Nenhuma publicação autorizada ou realizada.
