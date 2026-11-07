# V0.8 — evidências e limites

## Escopo e base

Branch `codex/ai-team/v08-central-ia`, baseada em `19114907571e03f3be288cdeff5096344ef05a77`.
PR #10 já integrado; PR #11 continuava aberto e homologado ao iniciar esta versão.
PR #13 é empilhado sobre a branch V0.7.1, sem alterar main ou reescrever histórico.
Nenhum merge, deploy, provisionamento, compra ou ativação de billing foi realizado.

Entregue: central `/modelos`, preferências por agente/projeto, fila persistente,
Gemini REST com prova de elegibilidade, cotas serializadas, roteamento e auditoria,
Token Optimizer existente e encaminhamento Codex supervisionado. Estúdio `/videos`
com cenas/legendas, consentimento, aprovação por digest, worker separado, MP4 local,
cancelamento e download autenticado. Preparação de serviços Linux/ARM64 privados.

## Evidências locais — 06/11/2026, com término em 07/11 UTC

| Verificação | Resultado observado |
| --- | --- |
| Python completo, `pytest services/api/tests -q` | 515 aprovados, 32 ignorados, 213,20s; execução anterior à última extensão de padrões Google |
| Regressões finais Google/memória/vault/central/vídeo | 39 aprovados, 1 ignorado; inclui três novos testes de padrões Google após o teste completo |
| Vídeo com FFmpeg Windows | 13 aprovados, incluindo renderização real, cancelamento, credenciais e auditoria |
| PostgreSQL descartável real | 16 aprovados; schema privado, concorrência global de cotas, idempotência e recuperação após reconexão |
| Sandbox Docker opt-in Python/Next | 41 aprovados, 3 ignorados; testes unitários e execução real com limites |
| Playwright completo | 33 aprovados em 2,7 minutos; backend real, contratos de modelos controlados, sem inferência |
| Ruff, ESLint, typecheck, Next build | aprovados localmente |
| Imagem `Dockerfile.production --target video` | build Linux amd64 aprovado |
| Renderer na imagem Linux | MP4 real de 7.208 bytes, sem rede, sem capabilities, rootfs readonly, usuário 10001, limite 2 CPU/512MB |
| ARM64 | manifests oficiais compatíveis verificados; hardware e execução ARM64 ainda não homologados |

Logs locais ignorados pelo Git: `artifacts/v08-python-final.log`,
`v08-postgres.log`, `v08-docker.log`, `v08-e2e.log`, `v08-lint.log`,
`v08-typecheck.log`, `v08-build.log` e `v08-image-build.log`.
Reprodução segue os comandos dos testes, `AI_TEAM_SANDBOX_TESTS=1` para Docker e
as salvaguardas CI PostgreSQL documentadas em `docs/postgres-ci.md`. Nunca apontar
esses testes de banco para dados existentes. O CI do SHA final é a referência
remota e está vinculado no PR; consultar seu estado atual, sem inferi-lo destes logs.

A primeira rodada E2E falhou porque o novo cenário deixava um pedido central na
fila compartilhada. A limpeza explícita desse pedido corrigiu a interferência;
a suíte completa posterior passou. Não se desativaram asserts de funcionalidades.
Regressões adicionais RED/GREEN: consentimento estrito, cooldown longo, reserva
JSON, mensagens de verificação enfileirada, espera no escritório, entrada com
credenciais, padrões Google e evento atômico de aprovação de vídeo.

## MP4 local reproduzível

```powershell
.venv\Scripts\python.exe tools\smoke-video.py --output artifacts\v08-demo-reels.mp4
```

Banco temporário e roteiro sintético, aprovação exata, worker real e ffprobe:
720×1280, H.264, 24 fps, quatro segundos, 21.875 bytes, sem áudio.
SHA-256 observado: `d012d08789c7c245c45e4a9c5cb3da015e74e3f333a7580f3159b04395be2a73`.
O JSON adjacente registra digest e metadados. Hashes podem variar por versão de
FFmpeg/plataforma; não são fixture binária obrigatória. Frame extraído inspecionado:
legenda portuguesa legível, dentro do quadro. Artefatos, banco e MP4 não entram no Git.

FFmpeg Windows: Gyan.FFmpeg 9.0.2, instalado pelo WinGet com hash verificado,
distribuição `ffmpeg-9.0.2-full_build.zip` no repositório GyanD/codexffmpeg.
SHA-256 do pacote: `759d0a9831c436a0eb331ad36f236c06cb04aaa0005da46571f0e9d3d9206f6b`.
O aplicativo não instala binários nem baixa fontes ao renderizar.

## Segurança revisada e pendências explícitas

- Isolamento por projeto, autenticação, origem/CSRF, idempotência e digest foram
  exercitados nos testes. Aprovação não libera comandos arbitrários ou serviços pagos.
- Chaves ficam exclusivamente no ambiente privado/secret mounts; padrões conhecidos
  são recusados em texto persistido. Nenhum detector garante identificar todo segredo:
  o proprietário precisa revisar os dados antes de enviar.
- Nenhuma chamada real Gemini/Codex/Hermes nesta versão: tokens reais adicionais
  de inferência **zero executados**, economia real **não medida**. Doubles HTTP e de
  contratos não homologam conexão externa. Verificação pública de documentação
  foi leitura; não houve inferência ou alteração de contas.
- Gemini exige chave própria, token OAuth de leitura, projeto sem billing comprovado,
  cotas confirmadas e consentimento. O catálogo expira em 14/11/2026 UTC; modelo,
  preço ou prova desconhecidos bloqueiam execução. Não houve configuração de
  credenciais Google nem homologação externa no ambiente do proprietário.
- Codex na central é handoff manual documentado, com digest e resultado não atestado.
  A importação ocorre pela API autenticada; não se afirma inferência automática.
  Fluxos próprios anteriores permanecem sob suas autorizações anteriores.
- Infraestrutura ARM64 preparada não significa hospedagem gratuita contratada ou
  operação 24/7 testada. Linux smoke foi amd64; HTTPS/frontend externo, backup,
  monitoramento, disponibilidade de recursos gratuitos e revisão operacional pendentes.
- MP4 contém cenas gráficas/textuais e legendas; voz, música, imagens geradas por IA,
  upload de mídia e publicação em redes sociais não fazem parte desta entrega.
- Revisões desta entrega são automatizadas e técnicas; não substituem revisão humana.

## Histórico

Commits convencionais e pushes progressivos; sem squash, force push ou alterações
artificiais. A descrição final do PR #13 registra a quantidade e todos os SHAs,
incluindo os commits de documentação posteriores a este relatório. Os commits
V0.1–V0.7.1 permanecem ancestrais. O PR deve ser integrado somente após autorização,
respeitando primeiro a dependência do PR #11; não há merge automático.
