# V0.9 — Fábrica de Conteúdo Automatizada

## Uso

Abra `/videos`, escolha um projeto e mantenha **Modo automático**. Descreva o vídeo, selecione proporção, duração (4–60 segundos) e estilo. Importe logo, fotos, vídeos ou áudio próprios/licenciados e marque até dez mídias visuais. O botão Iniciar produção cria uma solicitação persistente; não inicia uma chamada de IA.

O worker de vídeo existente avança seis etapas: CEO (requisitos), PESQUISADOR (estrutura), DESIGNER (montagem), DEV (fila/renderização FFmpeg), QA (inspeção do MP4) e CEO (entrega). A implementação atual usa regras locais e quatro cenas editáveis, identificadas como processamento determinístico sem inferência. Não interpreta pedidos abertos com um modelo, não pesquisa na internet nem fabrica fotos, voz ou música.

Sem mídia visual, a produção aguarda seu upload. Selecione a mídia e use Retomar. Na revisão, altere textos e durações, salve, confira a prévia e marque o consentimento para aprovar o digest exibido. Qualquer edição anterior à aprovação gera nova revisão e novo digest. Depois da aprovação, o roteiro fica imutável; cancele a produção ou revise uma tentativa que falhou, que exige novo digest e nova aprovação. O download é liberado pela fábrica somente após QA e consolidação.

O **Modo avançado** preserva o editor anterior, templates, biblioteca, áudio, animações, autosave e revisão de renderização. Os rascunhos avançados e roteiros automáticos são separados: trocar de modo não sobrescreve o seu rascunho.

## Persistência, segurança e execução

Tabela aditiva `content_productions`, com chave única por projeto/request_id, checkpoints, revisão, digest, vídeo vinculado e leases de 90 segundos. As tabelas são criadas pelo inicializador existente em SQLite local ou no schema PostgreSQL privado. A aplicação continua de proprietário único; não é um desenho multiusuário.

LangGraph despacha uma etapa por admissão do worker; os checkpoints duráveis são SQL da aplicação, não um checkpointer nativo LangGraph. Não foi adicionado outro agente/modelo nem outro serviço de fila. O worker de vídeo continua separado de HTTP e do frontend: `python -m ai_team.video_worker`. `tools/start.ps1` já inicia esse processo.

Quedas retomam somente a etapa incompleta, até duas recuperações automáticas de lease por produção. Falhas ficam visíveis e exigem retomada explícita; falha após montagem exige nova aprovação. A criação do VideoJob usa UUID determinístico, evitando render duplicado após queda entre fila e checkpoint. Cancelamento revoga a lease e cancela o VideoJob vinculado; há teste para cancelamento antes de sua autorização. Duas produções ativas por projeto, além dos limites existentes do renderer e de mídia (25 MB por arquivo, 100 arquivos/500 MB por projeto).

Somente IDs de mídia do próprio projeto são aceitos. Segredos são rejeitados nos pedidos/roteiros; mensagens de erro não expõem subprocessos nem caminhos. A fila FFmpeg mantém validação de schema, manifesto imutável, hash dos arquivos, consentimento, limites, timeout e cancelamento existentes. QA inspeciona um caminho derivado do UUID, sem shell, com FFprobe limitado a protocolo local, timeout de 15 segundos e ambiente sem credenciais do servidor. Verifica H.264, dimensões e duração. Não é análise semântica ou revisão humana da qualidade visual.

O escritório `/escritorio` recebe estados e histórico realmente persistidos. Renderização anima DEV somente com lease válida do VideoJob. Espera por mídia/aprovação não anima trabalho. Detalhes identificam o executor local e abrem a produção. A interface integrada do PR #15 é preservada na própria branch; esta V0.9 parte da V0.8.1 conforme solicitado, sem fundir PRs.

## Prévia preta

A causa era opacidade zero do fade exatamente no início/fim da cena. Durante edição pausada nesses extremos, a prévia mostra mídia e texto. Durante reprodução, mantém o fade do render. A diferença de edição está indicada na prévia. O E2E verifica imagem decodificada e opacidade, além de exportar MP4 real.

## Evidências e limites de homologação

Testes direcionados: `pytest services/api/tests/test_content_factory.py services/api/tests/test_office.py services/api/tests/test_video.py services/api/tests/test_video_studio_worker.py -q`; Playwright `content-factory.spec.ts`, `video-studio.spec.ts` e `video.spec.ts`. Incluem MP4 real de 15 segundos/720×1280, quatro cenas, edição, digest antigo recusado, persistência após recarga, cancelamento, isolamento, estados reais no escritório e download autenticado. PostgreSQL possui teste de reinício/checkpoints no CI privado existente.

A imagem de teste é uma fixture descartável, não a logo FORTALAKA. O exemplo com a logo real continua pendente porque ela não foi fornecida nesta solicitação. Não foi buscada em outros projetos nem inventada. ARM64 físico, julgamento visual humano e uso com mídias finais do proprietário permanecem pendentes. Logs completos `.data/v09-*.log` e screenshot `artifacts/v09-factory-mobile.png` são ignorados pelo Git.

Sem inferência externa, API paga, publicação em redes sociais, merge ou deploy. O status definitivo de teste completo/CI deve ser consultado no último SHA do PR V0.9.
