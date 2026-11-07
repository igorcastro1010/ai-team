# Renderer V0.8.1 — evidência local

Contrato: `render(job, output, active, executable=None, *, assets=None, progress=None)`.
`assets` mapeia UUID (string ou UUID) para arquivos privados verificados pelo worker.
O renderer revalida o documento, copia arquivos para nomes fixos em diretório
privado temporário, descarta áudio de clipes e aceita apenas áudio global explícito.
O worker mantém responsabilidade por projeto, hashes, aprovação e política de 1080p.

FFmpeg usa argumentos fixos, `shell=False`, protocolos file/pipe, ambiente mínimo,
fontes locais revisadas, UTF-8 em textfile e expansion=none. Limites: dois threads
por decoder/encoder e filtro, prazo total de 300s em 720p ou 600s em 1080p e
resultado de até 100MB. Cancelamento encerra o processo e limpa temporários,
sem publicar resultado parcial. O progresso usa timestamps produzidos pelo FFmpeg
e conclusão real de cada etapa; os pesos 85/5/9 reservam 100 para publicação final.

Saída a 24fps em H.264/yuv420p. Formatos 720x1280, 720x720, 1280x720; 1080p
escala 1,5x. Crop cover central, cenas sequenciais sem sobreposição, transição fade
através de preto de 0,4s em cada ponta. Zoom 1+0,08p; pan com escala 1,08 movendo
a janela de crop horizontalmente. Fade de texto e mídia de 0,4s na entrada e saída.
Slide do texto em Y: entrada de +16 para 0 e saída de 0 para -16 pixels de base 720,
com o mesmo fade. Fontes sans/serif/mono fornecidas por `font_path(font)`.
Tamanho de fonte é baseado em largura 720; âncoras de texto usam a área disponível
após medir texto. Quebra de linha Python textwrap: 27 caracteres para largura até
1080, 48 acima, preservando compatibilidade V0.8. Preview espelha essa regra.

Reprodução sem rede/inferência:

```powershell
.venv/Scripts/python.exe -m pytest services/api/tests/test_video_render_studio.py services/api/tests/test_video.py -q
.venv/Scripts/python.exe tools/smoke-video-studio.py --output artifacts/v081-studio-smoke.mp4
```

Validação em 2026-11-06: 20 testes direcionados passaram; Ruff passou nos três
arquivos Python. Smoke com PNG, MP4 e WAV sintéticos locais: H.264 720x720 + AAC,
6,000s, 421783 bytes; SHA-256
`782f17b1c84f3998ba7637f058f08e7395f768235bb9ba500875347eba514f0b`.
O JSON adjacente contém probe, documento e progresso observado. Artefatos são
locais e ignorados pelo Git. O smoke exercita diretamente o renderer; autorização
e worker são cobertos separadamente pelos testes de integração do projeto.
