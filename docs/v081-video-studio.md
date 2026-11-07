# V0.8.1 — Estúdio de Vídeos 2.0

Base: V0.8 `aabc658`, sem merge ou revisão geral de versões anteriores.
O estúdio reutiliza API, proprietário/sessão, banco e worker existentes.
Não chama IA, serviços de voz, música, geração de mídia ou APIs pagas.

## Começar no Windows

1. Pare a inicialização anterior com Ctrl+C e atualize para a branch da V0.8.1.
2. Use `tools/start.ps1`: ele inicializa as tabelas aditivas e inicia API, painel e
   worker de vídeo. A conta existente é preservada; não recrie o usuário.
3. Abra `/videos`, escolha o projeto e informe um título. As edições passam a ser
   salvas automaticamente como rascunho, após uma breve pausa na digitação.
4. Importe seus arquivos, monte as cenas, confira a prévia e prepare a revisão.
5. Aprove o digest do roteiro salvo. O worker renderiza em segundo plano; a
   interface consulta estados/progresso persistidos e libera o download ao concluir.

FFmpeg e FFprobe locais continuam obrigatórios. A instalação já aprovada no
Windows usa Gyan.FFmpeg/WinGet, ou `AI_TEAM_FFMPEG` com caminho explícito do servidor.
Nenhum executável, fonte ou mídia é baixado automaticamente pelo editor.

## Editor e mídia

Cenas podem ser selecionadas, reordenadas, duplicadas e excluídas. O editor mantém
pelo menos uma e no máximo seis; cada cena dura 1–20s e o total é limitado a 60s.
Texto, posição X/Y, tamanho, cor, fundo e fonte são editáveis. Fontes sans, serif
ou mono vêm de arquivos locais conhecidos e são servidas autenticadas para a prévia.

Formatos: 9:16 (720×1280), 1:1 (720×720), 16:9 (1280×720), a 24fps.
MP4 H.264/yuv420p funciona sem GPU dedicada. Para habilitar 1080p, o operador deve
confirmar recursos e definir `AI_TEAM_VIDEO_1080P=1` tanto na API quanto no worker.
No Windows, antes do launcher: `$env:AI_TEAM_VIDEO_1080P='1'`. O padrão é 720p;
configuração desconhecida não habilita 1080p. Em Compose, use a variável no ambiente
privado de ambos os serviços; nenhuma publicação ou VM é criada por isso.

Tipos de upload aceitos: PNG, JPEG, WebP; MP4 e WebM; MP3, WAV e Ogg para áudio.
Até 25MB por arquivo, 100 arquivos e 500MB por projeto. Vídeos/áudios de origem
podem ter até 300s; o resultado continua limitado a 60s. SVG, GIF, playlists,
URLs remotas e formatos não reconhecidos são recusados. A biblioteca é privada
por projeto; arquivos são imutáveis e não podem ser substituídos pela API.
Não há exclusão de mídia nesta versão, para preservar referências e aprovações.

Importe somente mídia própria ou licenciada. Não há busca/download de músicas,
voz contratada ou geração por IA. O áudio nativo dos clipes é silenciado. Uma faixa
selecionada explicitamente na biblioteca adiciona áudio de fundo com volume e
fades; se for curta, o restante fica silencioso. Sem faixa, o MP4 permanece sem
trilha de áudio. O renderer não mistura nem repete músicas automaticamente.

## Prévia, animações e templates

Prévia com play/pause e scrub da timeline: cover central da mídia, zoom suave,
pan lateral, fade in/out, texto com fade ou deslocamento vertical de entrada e saída.
Transições são fade através de preto, sem sobrepor cenas: a duração total é a soma
das cenas. A prévia usa os mesmos parâmetros e fontes do renderer, inclusive
áudio curto seguido de silêncio. Antialiasing, rasterização e métricas de texto do
navegador podem diferir ligeiramente do FFmpeg; confira o MP4 antes de publicar.

Seis templates originais editáveis: Reels de divulgação, Apresentação de produtos,
Promoções, Tutorial rápido, Anúncios de serviços e Vídeo institucional. Têm textos
orientativos, formatos, cores e presets de movimento; nenhuma mídia de terceiros.
Aplicar um template substitui o documento atual, sem gerar vídeo. Também é possível
salvar o documento como template próprio, incluindo referências à mídia do projeto.
Templates e rascunhos nunca são compartilhados com outros projetos.

O rascunho usa revisão otimista: duas sessões não sobrescrevem silenciosamente
as alterações. Em conflito, o editor preserva as edições locais e oferece recarga
explícita da versão do servidor. Dados já gravados sobrevivem a reinício da API.

## Segurança, fila e limites

- Endpoints exigem proprietário e origem/CSRF; uploads têm limite no proxy e API.
  Dois uploads simultâneos por processo; admissão de arquivos/bytes serializada
  por projeto no banco. Rascunhos e nomes rejeitam padrões conhecidos de segredos.
- O cliente envia bytes, não caminhos. UUIDs e diretórios são derivados pelo
  servidor; caminhos externos, links/junctions e colisões são recusados. Uploads
  passam por assinatura de arquivo e FFprobe com demuxer fixo, timeout de 8s,
  saída limitada e limite de 64MB por alocação. Dimensões máximas 4096 por lado
  e área de 16 milhões de pixels; metadados não verificados bloqueiam o upload.
- A aprovação inclui o manifesto imutável de hashes e metadados. O worker
  verifica projeto, hash, digest, consentimento e resolução novamente. Mídia
  adulterada depois da aprovação falha antes de iniciar o FFmpeg.
- Cada render tem subprocessos/diretório temporário próprios, nomes internos
  fixos, argumentos em lista, `shell=False`, ambiente sem credenciais herdadas e
  protocolos locais. Não aceita filtros, scripts, fontes ou URLs arbitrárias.
  Isolamento nativo não é uma VM por projeto; para limites rígidos de CPU/memória,
  use o serviço Docker revisado e volumes privados, sem socket Docker ou HOME.
- Até dois jobs ativos por projeto, inclusive propostas pendentes. Dois threads
  por etapa de codec/filtro; timeout total 300s (720p) ou 600s (1080p); MP4 até 100 MB.
  O lease é renovado durante atividade válida. Cancelamento revoga o lease; o
  processo encerra na checagem seguinte e não publica arquivos parciais.
- Progresso deriva de timestamps do FFmpeg e conclusão de etapas, ponderado entre
  cenas/montagem/áudio. Não é previsão linear de tempo. 100% somente após publicação
  válida do arquivo no estado concluído. Falhas/crashes não repetem renders
  silenciosamente: o lease expira para falha, mantendo o rascunho para novo pedido
  revisado e aprovado. Não se apagam artefatos automaticamente.
- Conteúdo e arquivos permanecem privados, com download autenticado e suporte a
  Range no proxy para seek. Aplicação de proprietário único; isso não implementa
  autorização multiusuário. Decodificadores devem permanecer atualizados.

Produção: as tabelas são aditivas (`video_media`, `video_drafts`, `video_templates`,
`video_progress`); nenhuma coluna histórica é removida. Inicialize o banco antes
 de iniciar processos concorrentes. API e worker precisam compartilhar banco e
`AI_TEAM_VIDEO_ROOT`; fontes DejaVu também estão na imagem da API. O Compose já
prepara Linux ARM64, mas esta versão não provisionou hospedagem nem homologou
hardware ARM64. Em Vercel, limites próprios de upload/streaming exigem revisão de
hospedagem; uploads grandes foram validados no Next local, sem prometer superar
limites do provedor. API/worker/mídia privados não devem ir para Functions longas.

## Evidências reproduzíveis

Executados localmente, sem inferências:

- 47 testes direcionados de vídeo/schema/biblioteca/worker/fontes/renderer aprovados.
- 2 E2E do estúdio e fluxo V0.8 aprovados em 22,8s: reordenação, duplicação/exclusão,
  autosave/reload, conflito 409 real, upload PNG, prévia autenticada, templates,
  progresso numérico e viewport 390 sem overflow.
- Ruff, ESLint, typecheck e build aprovados. Oito testes de configuração de produção
  aprovados. A suíte completa e PostgreSQL ficam para o CI do SHA final do PR.
- Teste real completo: upload de PNG+MP4+WAV → manifesto → aprovação → worker →
  H.264/AAC de 4s, progresso 100; adulteração de arquivo aprovada bloqueada antes
  do renderer. Outros testes reais cobrem 1080p, três proporções, silêncio, texto,
  fade/zoom/pan, cancelamento e entrada/saída vertical de texto.
- Revisão automatizada independente restrita aos novos caminhos de vídeo:
  corrigidos contrato numérico de progresso e fase após cancelamento/fila.
  Não houve revisão geral dos PRs anteriores nem certificação humana de segurança.

```powershell
.venv/Scripts/python.exe -m pytest services/api/tests/test_video.py services/api/tests/test_video_schema.py services/api/tests/test_video_studio.py services/api/tests/test_video_studio_worker.py services/api/tests/test_video_fonts.py services/api/tests/test_video_render_studio.py -q
.venv/Scripts/python.exe tools/smoke-video-studio.py --format vertical --output artifacts/v081-studio-vertical.mp4
npm exec --workspace @ai-team/web -- playwright test video.spec.ts video-studio.spec.ts
```

Smoke vertical observado: H.264 720×1280 + AAC, 6,000s, 356425 bytes;
SHA-256 `17ca488cc5461d1fac80a997a3e13c6e1b5e57bcf5d53c45a96e2a102a852b07`.
JSON adjacente contém documento, ffprobe e progresso. Artefatos/logs/capturas ficam
em `artifacts/` e `.data/`, ignorados pelo Git. Hash pode variar por plataforma.
Nenhuma API paga, inferência, compra, faturamento, merge ou deploy foi realizado.
Custos de energia, máquina e armazenamento do operador não são medição de custo
zero de infraestrutura; nenhum serviço adicional foi contratado.
