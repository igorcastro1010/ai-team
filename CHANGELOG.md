# Histórico de versões

## 0.8.1

- Biblioteca de mídia privada por projeto com uploads validados, hashes e limites.
- Editor de cenas, timeline, prévia, posição/cores/fontes e autosave com controle de revisão.
- Seis templates editáveis e templates próprios do projeto.
- Imagem/vídeo, fade, zoom, pan, transições e entrada/saída de texto no FFmpeg.
- Áudio local opcional com volume/fades; silêncio sem faixa selecionada.
- Três proporções, 720p/1080p controlado pelo servidor, progresso real e download autenticado.
- Testes direcionados, suíte completa no CI e evidências em `docs/v081-video-studio.md`.
- V0.8 preservada, sem merge, deploy, contratação ou inferência externa.

## 0.8.0

- Central `/modelos`, preferências por agente/projeto, fila supervisionada e histórico.
- Adaptador Gemini oficial com prova de projeto sem billing, catálogo gratuito
  temporário e bloqueio na ausência de elegibilidade, cota ou consentimento.
- Admissão serializada, limites por projeto Google/AI TEAM, Retry-After e integração
  com Token Optimizer; nenhum fallback pago ou inferência externa nesta release.
- Codex central por encaminhamento manual vinculado a digest; Hermes/Codex existentes preservados.
- Estúdio `/videos`: cenas e legendas, aprovação, worker FFmpeg local, MP4 vertical
  ou horizontal, cancelamento e download autenticado. Sem áudio ou geração por IA.
- Preparação de serviços privados Linux ARM64, volumes, healthchecks e shutdown;
  nenhum provisionamento ou deploy. Ver evidências em `docs/v08-validation.md`.

As versões V0.1–V0.7.1 e suas evidências permanecem no histórico Git e em `docs/`.
