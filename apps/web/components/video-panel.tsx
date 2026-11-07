"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Project } from "@/lib/api";
import "@/styles/video.css";

type Scene = { text: string; duration: number };
type Video = { id: string; title: string; format: "vertical" | "horizontal"; scenes: Scene[]; digest: string; status: string; error: string };
type Snapshot = { items: Video[]; renderer: { available: boolean; reason: string } };
const labels: Record<string, string> = { pending_approval: "Aguardando sua aprovação", queued: "Na fila do worker", rendering: "Renderizando no worker", completed: "MP4 pronto", cancelled: "Cancelado", failed: "Falha na renderização", blocked: "Renderização indisponível" };

export function VideoPanel({ projects }: { projects: Project[] }) {
  const [selected, setSelected] = useState("");
  const project = selected || projects[0]?.id || "";
  return <section className="video-panel" aria-label="Produção de vídeos">
    <div className="video-toolbar"><label>Projeto dos vídeos<select value={project} onChange={event => setSelected(event.target.value)}>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><p>Roteiro, aprovação e MP4 em um só lugar.<br />Renderização local, sem chamadas de IA ou serviços pagos.</p></div>
    {project ? <ProjectVideos key={project} project={project} /> : <p>Crie um projeto para preparar seu primeiro vídeo.</p>}
  </section>;
}

function ProjectVideos({ project }: { project: string }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState<"vertical" | "horizontal">("vertical");
  const [scenes, setScenes] = useState<Scene[]>([{ text: "", duration: 5 }]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const requestId = useRef("");
  const generation = useRef(0);
  const total = scenes.reduce((sum, scene) => sum + scene.duration, 0);

  async function refresh(signal?: AbortSignal) {
    const current = ++generation.current;
    const result = await api<Snapshot>(`/videos?project_id=${project}`, { signal });
    if (!signal?.aborted && generation.current === current) setSnapshot(result);
  }
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => { void refresh(controller.signal).then(() => { if (!controller.signal.aborted) setMessage("Vídeos atualizados"); }).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Falha ao carregar"); }); }, 0);
    return () => { controller.abort(); window.clearTimeout(timer); generation.current += 1; };
    // Project changes remount this component and discard all previous project state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project]);

  async function perform(action: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(true); setError(""); generation.current += 1;
    try { await action(); await refresh(); setMessage(success); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível concluir"); }
    finally { setBusy(false); }
  }
  function editScene(index: number, patch: Partial<Scene>) {
    requestId.current = "";
    setScenes(current => current.map((scene, at) => at === index ? { ...scene, ...patch } : scene));
  }

  return <>
    <div className="video-statusbar"><p role="status">{message}</p><button className="button" disabled={busy} onClick={() => void perform(async () => {}, "Vídeos atualizados")}>Atualizar vídeos</button></div>
    {error && <p role="alert" className="video-error">{error}</p>}
    {snapshot && !snapshot.renderer.available && <aside className="video-notice"><strong>Renderizador indisponível neste servidor</strong><p>{snapshot.renderer.reason}. Você pode preparar e revisar o roteiro. A geração exige o worker de vídeo configurado.</p></aside>}
    <div className="video-columns"><form className="panel video-form" onSubmit={event => { event.preventDefault(); if (!requestId.current) requestId.current = crypto.randomUUID(); void perform(async () => { await api("/videos", { method: "POST", body: JSON.stringify({ project_id: project, request_id: requestId.current, title, format, scenes, consent }) }); requestId.current = ""; }, "Roteiro pronto para revisão"); }}>
      <div><span className="video-eyebrow">ESTÚDIO LOCAL</span><h2>Do roteiro ao vídeo.</h2><p>Cenas com legendas em fundo gráfico. MP4 silencioso, 24 fps. Até 6 cenas e 60 segundos.</p></div>
      <label>Título do vídeo<input required maxLength={120} disabled={busy} value={title} onChange={event => { setTitle(event.target.value); requestId.current = ""; }} /></label>
      <label>Formato do vídeo<select disabled={busy} value={format} onChange={event => { setFormat(event.target.value as "vertical" | "horizontal"); requestId.current = ""; }}><option value="vertical">Vertical · 720 × 1280</option><option value="horizontal">Horizontal · 1280 × 720</option></select></label>
      <div className="video-scene-heading"><h3>Cenas do roteiro</h3><span>{total} / 60 segundos</span></div>
      {scenes.map((scene, index) => <fieldset key={index} disabled={busy} className="video-scene"><legend>Cena {index + 1}</legend><label>Texto da cena {index + 1}<textarea rows={3} maxLength={240} required value={scene.text} onChange={event => editScene(index, { text: event.target.value })} /></label><div className="video-actions"><label>Duração da cena {index + 1} (segundos)<input type="number" min={1} max={20} required value={scene.duration} onChange={event => editScene(index, { duration: Number(event.target.value) })} /></label>{scenes.length > 1 && <button type="button" className="button" onClick={() => { setScenes(current => current.filter((_, at) => at !== index)); requestId.current = ""; }}>Remover cena {index + 1}</button>}</div></fieldset>)}
      <button type="button" className="button" disabled={busy || scenes.length >= 6} onClick={() => { setScenes(current => [...current, { text: "", duration: 5 }]); requestId.current = ""; }}>Adicionar cena</button>
      <label className="video-consent"><input type="checkbox" checked={consent} disabled={busy} onChange={event => { setConsent(event.target.checked); requestId.current = ""; }} />Autorizo gerar este vídeo localmente após revisar o roteiro</label>
      <button className="button primary" disabled={busy || !consent || total > 60 || !total}>Preparar revisão</button>
    </form>
    <div className="video-history"><h2>Produção do projeto</h2><p>Revise o roteiro salvo antes de aprovar. O worker processa a fila em separado; use Atualizar vídeos para acompanhar.</p>{snapshot?.items.length === 0 && <p>Nenhum vídeo neste projeto.</p>}{snapshot?.items.map(job => <article className="panel video-card" key={job.id}><div className="video-card-heading"><h3>{job.title}</h3><span className="video-badge">{labels[job.status] || job.status}</span></div><p>{job.format === "vertical" ? "Vertical" : "Horizontal"} · {job.scenes.reduce((sum, scene) => sum + scene.duration, 0)} segundos</p><ol>{job.scenes.map((scene, index) => <li key={index}><p className="video-caption">{scene.text}</p><small>{scene.duration} segundos</small></li>)}</ol>{job.error && <p className="video-error">{job.error}</p>}{job.status === "pending_approval" && <><small className="video-digest">Digest do roteiro: {job.digest}</small><div className="video-actions"><button className="button primary" disabled={busy} onClick={() => void perform(() => api(`/videos/${job.id}/decision`, { method: "POST", body: JSON.stringify({ digest: job.digest, approve: true }) }), "Roteiro aprovado; vídeo na fila")}>Aprovar e gerar MP4</button><button className="button" disabled={busy} onClick={() => void perform(() => api(`/videos/${job.id}/decision`, { method: "POST", body: JSON.stringify({ digest: job.digest, approve: false }) }), "Roteiro recusado")}>Recusar roteiro</button></div></>}{["queued", "rendering"].includes(job.status) && <button className="button" disabled={busy} onClick={() => void perform(() => api(`/videos/${job.id}/cancel`, { method: "POST" }), "Vídeo cancelado")}>Cancelar vídeo</button>}{job.status === "completed" && <a className="button primary" href={`/api/control/videos/${job.id}/download`} download>Baixar MP4</a>}</article>)}</div></div>
  </>;
}
