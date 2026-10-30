# Execução local Windows após 811bebf

**Objetivo:** ativar os pré-requisitos locais do Hermes e tornar o diagnóstico de instalação verificável, sem substituir a integração já incorporada no GitHub.

**Execução:** direta, com skills de planejamento, TDD, diagnóstico e verificação. Autonomia local e commits/push já autorizados. O proprietário autorizou explicitamente instalar WSL 2 e Docker em 30/10/2026, sem reinício automático ou publicação.

**Arquitetura:** diagnóstico CLI somente leitura, com subprocessos de comandos fixos e timeout, sem ler `.env`, cofres ou sessões. Distinguir painel/API nativos de Hermes opcional e diferenciar executável instalado de engine funcional. Nenhuma nova dependência, migração ou alteração da política dos agentes.

- [x] Instalar WSL sem distribuição adicional e Docker Desktop por usuário, backend WSL 2, pelas fontes oficiais. Verificar resultado e necessidade de reinício; não reiniciar o PC.
- [x] Criar `ai_team.doctor` e wrapper `tools/doctor.ps1`. Testar ambiente base, Docker ausente, WSL antigo, engine indisponível/Windows, timeout e sanitização. Observar falha antes de implementação. Commit validado e push.
- [x] Verificar inicialização nativa: falhas de Python/API devem impedir painel aparentemente funcional. Corrigir somente se a investigação/teste confirmar a lacuna. Testes e commit separados.
- [x] Executar diagnóstico real, pytest/lint/typecheck/build/E2E e revisão; integrar somente após CI aprovado. Documentar limites e resultados reais, sem afirmar inferência/Telegram antes de homologação.

WSL exige ativação administrativa e pode pedir reinício. Docker instalado não comprova engine, Compose, autenticação Codex, inferência ou Telegram. O login próprio do Hermes será conduzido pelo assistente oficial quando o runtime estiver disponível. Nenhuma chave existente será importada.

Resultado local: WSL 3.0.3 e Docker Desktop 4.97.0 instalados. Reinício Windows pendente, hipervisor ainda inativo; Hermes não foi iniciado nem autenticado. Diagnóstico real confirma base nativa pronta e Hermes pendente. Revisão corrigiu indicador adicional Windows Update e rechecagem da API após os filhos. Sem deploy, importação de sessão ou inferência.
