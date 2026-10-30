# Execução local Windows após 811bebf

**Objetivo:** ativar os pré-requisitos locais do Hermes e tornar o diagnóstico de instalação verificável, sem substituir a integração já incorporada no GitHub.

**Execução:** direta, com skills de planejamento, TDD, diagnóstico e verificação. Autonomia local e commits/push já autorizados. O proprietário autorizou explicitamente instalar WSL 2 e Docker em 30/10/2026, sem reinício automático ou publicação.

**Arquitetura:** diagnóstico CLI somente leitura, com subprocessos de comandos fixos e timeout, sem ler `.env`, cofres ou sessões. Distinguir painel/API nativos de Hermes opcional e diferenciar executável instalado de engine funcional. Nenhuma nova dependência, migração ou alteração da política dos agentes.

- [ ] Instalar WSL sem distribuição adicional e Docker Desktop por usuário, backend WSL 2, pelas fontes oficiais. Verificar resultado e necessidade de reinício; não reiniciar o PC.
- [ ] Criar `ai_team.doctor` e wrapper `tools/doctor.ps1`. Testar ambiente base, Docker ausente, WSL antigo, engine indisponível/Windows, timeout e sanitização. Observar falha antes de implementação. Commit validado e push.
- [ ] Verificar inicialização nativa: falhas de Python/API devem impedir painel aparentemente funcional. Corrigir somente se a investigação/teste confirmar a lacuna. Testes e commit separados.
- [ ] Executar diagnóstico real, pytest/lint/typecheck/build/E2E e revisão; integrar somente após CI aprovado. Documentar limites e resultados reais, sem afirmar inferência/Telegram antes de homologação.

WSL exige ativação administrativa e pode pedir reinício. Docker instalado não comprova engine, Compose, autenticação Codex, inferência ou Telegram. O login próprio do Hermes será conduzido pelo assistente oficial quando o runtime estiver disponível. Nenhuma chave existente será importada.
