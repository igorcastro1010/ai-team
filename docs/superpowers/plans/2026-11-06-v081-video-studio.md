# V0.8.1 Estúdio de Vídeos 2.0 — plano

Base aabc658, branch codex/ai-team/v081-video-studio. Sem merge, deploy,
inferência, instalação de serviço pago ou revisão geral de PRs anteriores.

Arquitetura: FFmpeg/worker existentes; mídia imutável privada por projeto;
rascunho persistente com revisão otimista; templates JSON reutilizáveis;
editor React com prévia por timeline e as mesmas propriedades do renderer.
Transição escolhida: fade através de preto, sem sobreposição temporal, para
manter duração total e prévia coerentes. Áudio de origem dos clipes é descartado;
música/áudio selecionado explicitamente é opcional e local.

Contrato de documento (video_schema.py): title, format vertical/square/horizontal,
resolution 720p/1080p, scenes (1..6, total <=60s), audio opcional.
Cena: text, duration int1..20, media_id UUID opcional, x/y 0..100,
font_size18..96 em pixels de base720, color/background #rrggbb,
font sans/serif/mono, animation none/fade/zoom/pan,
text_animation none/fade/slide, transition cut/fade. Fade dura min(.4,duração/2).
Texto usa âncoras (w-text_w)*x%, (h-text_h)*y%. Fontes locais servidas autenticadas.
Sem comandos/filtros/URLs livres. Render valida mídias/hash/projeto e digest.

API /video-studio/{project_id}: GET/POST media (POST corpo binário, query name),
GET media/{id}/content; GET/PUT draft {revision,document}; GET/POST templates
{name,document}; POST render {request_id,document,consent:true}.
Biblioteca retorna {items}; rascunho {revision,document}; template {id,name,document}.
Biblioteca: id,name,kind image/video/audio,mime,bytes,sha256,duration,width,height.
Tabela aditiva VideoProgress(job_id,value,phase) evita alteração destrutiva de banco.
Assets imutáveis; manifesto de hashes entra na aprovação. Upload máximo25MB,
100 arquivos/500MB por projeto, formatos allowlist e probe local com timeout.
720p padrão;1080p depende AI_TEAM_VIDEO_1080P=1 e recursos do operador.

- [ ] Schema e regressões TDD; contrato de compatibilidade V0.8.
- [ ] Mídia privada, validação, rascunhos e seis templates, testes API/isolamento.
- [ ] Renderer imagem/vídeo/animação/transição/áudio e testes FFmpeg reais.
- [ ] Editor, timeline, prévia, autosave, biblioteca, templates e E2E direcionado.
- [ ] Worker/progresso/manifesto, proxy autenticado, testes de integração.
- [ ] Docs, CI completo, PR e evidências; commits atômicos e pushes regulares.

Aplicação de subagent-driven-development: módulos com arquivos separados e
contratos explícitos. Coordenador integra e verifica; nenhum subagente altera main,
faz merge/deploy ou executa inferências. Preserve trabalho alheio e estágio exato.
