# V0.8 — produção local de vídeos

O estúdio prepara vídeos verticais de cenas e legendas para Reels/TikTok: 720 × 1280, H.264, MP4 silencioso, 24 fps. Também permite horizontal 1280 × 720. O roteiro é escrito pelo proprietário; nenhuma inferência, API de geração, upload remoto ou serviço pago é chamado. O custo de computação local/hospedagem continua existindo.

## Fluxo

1. Selecione o projeto, título, formato e até seis cenas. Cada cena aceita 1–20 segundos e 240 caracteres. O total não pode ultrapassar 60 segundos.
2. Marque o consentimento e prepare a revisão. Isso salva um job `pending_approval`, sem executar FFmpeg.
3. Revise o texto e o digest do roteiro persistido. Aprovar vincula o digest ao recurso e coloca o vídeo na fila. Recusar cancela a proposta.
4. O processo `python -m ai_team.video_worker` busca trabalhos aprovados. `--once` processa no máximo um job e encerra.
5. Use Atualizar vídeos para acompanhar o estado. O download autenticado só aparece após `completed` e retorna `video/mp4`.

O worker é independente da API. Nenhuma requisição HTTP renderiza vídeos ou executa tarefa longa. Fila sem worker permanece `queued`; a interface não simula progresso. Cancelar revoga o lease; um processo em andamento encerra na próxima checagem. SIGINT/SIGTERM encerram o subprocesso e não publicam resultado parcial. Um worker interrompido sem encerramento limpo tem seu lease expirado marcado como `failed` quando outro worker consultar a fila, sem repetição silenciosa.

## Dependências e instalação

Python usa somente bibliotecas já existentes no projeto e stdlib; não adicionamos Pillow. O host do worker precisa de FFmpeg com `libx264` e `drawtext`, além de uma fonte local: Arial em `WINDIR/Fonts/arial.ttf` no Windows ou DejaVu Sans em `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` no Linux. Não há download automático de binários, fontes ou assets.

No Windows, instale a distribuição revisada do FFmpeg por fonte oficial do projeto/distribuidor ou gerenciador de pacotes aprovado. Após instalar, abra um terminal novo e valide `ffmpeg -version`. Alternativamente configure `AI_TEAM_FFMPEG` com o caminho absoluto do executável no servidor. Essa variável não é aceita de clientes. Registrar origem e hash do instalador/binário na evidência da homologação.

A API e o worker precisam compartilhar o mesmo banco privado e diretório privado de artefatos. `AI_TEAM_VIDEO_ROOT` define esse diretório no servidor; o padrão de desenvolvimento é `.data/videos` do repositório. Em contêiner, use `/data/videos` em volume compartilhado apenas com API/worker. Não publique esse diretório como conteúdo estático. O processo precisa de permissão de escrita e a API de leitura; proteja o volume com ACL do sistema. Não configure links simbólicos no diretório privado. A configuração de produção e a imagem dedicada estão descritas em `docs/v08-production.md`.

`GET /videos?project_id=UUID` inclui um diagnóstico **local à API** de presença do executável e fonte. Esse diagnóstico não é um heartbeat do worker nem prova de que codecs funcionam. Quando somente a imagem separada do worker contém FFmpeg, a API pode informar indisponibilidade local apesar de o worker estar configurado. O resultado real do job diferencia sucesso, bloqueio e falha.

## Segurança e limites

- Todos os endpoints exigem a sessão do proprietário; mutações também passam pela proteção de origem/CSRF existente.
- O sistema mantém a arquitetura de proprietário único. Projetos isolam listagem, idempotência e admissão; isso não oferece autorização multiusuário.
- `POST /videos` exige UUIDs de projeto e solicitação, consentimento booleano explícito e schemas sem campos extras. A chave `(project_id, request_id)` é única: repetição idêntica retorna o mesmo job; outro roteiro com a mesma chave gera conflito.
- Admissão é serializada por projeto com no máximo dois jobs ativos, incluindo propostas pendentes. O banco mantém índices de fila e unicidade compatíveis com SQLite/PostgreSQL.
- A aprovação só vale para o digest persistido. O executor recalcula o digest, verifica consentimento e valida novamente duração, cenas e formato antes de renderizar.
- FFmpeg recebe argumentos fixos em lista e `shell=False`; texto de cena é gravado em arquivo UTF-8 com `expansion=none`, fora do filtro. Não há URLs, áudio externo, assets remotos, filtros ou comandos fornecidos pelo usuário. O ambiente do subprocesso não herda segredos do servidor.
- Cada render usa no máximo duas threads e tem prazo global de 180 segundos; o lease dura 240 segundos. Use os limites de memória/CPU da imagem dedicada em hospedagem. API e web não precisam do socket Docker.
- A saída é publicada somente após sucesso e lease válido. Arquivos temporários são removidos; downloads não aceitam caminhos livres, links simbólicos ou job não concluído. Erros não retornam saída do processo nem caminhos privados.
- Artefatos concluídos permanecem no volume privado. Não existe exclusão automática nem política de retenção nesta etapa; exclusão precisa de autorização específica. Roteiros e MP4 podem conter dados privados.

## Verificação

`python -m pytest services/api/tests/test_video.py -q` cobre schema/consentimento, idempotência, limites, aprovação/digest, cancelamento, leases, adulteração, autenticação, CSRF e bloqueio honesto sem FFmpeg. Dois testes de integração renderizam um MP4 real com legendas acentuadas/caracteres especiais e exercitam cancelamento quando FFmpeg/fonte estão disponíveis; caso contrário aparecem como `skipped`, nunca sucesso simulado.

`apps/web/e2e/video.spec.ts` exerce o painel com backend real: criação de proposta, revisão, ausência de download antecipado, recusa e troca de projeto. A execução completa de lint, typecheck, build, pytest e E2E é coordenada na release. A existência desses arquivos de teste não equivale à evidência de execução. Nenhuma implantação de produção é feita pelo estúdio ou por esta implementação.

O launcher Windows `tools/start.ps1` também inicia o worker de vídeo e o encerra
junto aos demais serviços. A descoberta local reconhece PATH ou a instalação
Gyan.FFmpeg do WinGet no perfil do proprietário; `AI_TEAM_FFMPEG` explícito tem
precedência e falha se inválido. Nenhuma instalação automática ocorre ao usar o painel.

Para reproduzir o smoke sem tocar no banco do proprietário:

```powershell
.venv\Scripts\python.exe tools\smoke-video.py --output artifacts\v08-demo-reels.mp4
```

O comando usa banco/diretório temporários, roteiro sintético, aprovação exata,
worker real e ffprobe. Salva MP4 e JSON com digest/hash/resolução; não chama modelos.
Aprovação, recusa, cancelamento e transições do worker registram eventos persistentes.
Roteiros com padrões de credenciais conhecidos são rejeitados antes da gravação;
a detecção por padrões não substitui a revisão do proprietário.
