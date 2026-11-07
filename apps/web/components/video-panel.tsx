"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Project } from "@/lib/api";
import "@/styles/video.css";
import { VideoStudio } from "./video-studio";
import { ContentFactoryPanel } from "./content-factory-panel";
import type { StudioDocument } from "@/lib/video-studio";

type Scene = { text: string; duration: number };
type Video = { id: string; title: string; format: "vertical" | "square" | "horizontal"; scenes: Scene[]; digest: string; status: string; error: string; progress?: number; phase?: string };
type Snapshot = { items: Video[]; renderer: { available: boolean; reason: string; supports_1080p?: boolean } };
const labels: Record<string, string> = { pending_approval: "Aguardando sua aprovação", queued: "Na fila do worker", rendering: "Renderizando no worker", completed: "MP4 pronto", cancelled: "Cancelado", failed: "Falha na renderização", blocked: "Renderização indisponível" };

export function VideoPanel({ projects }: { projects: Project[] }) {
  const [mode, setMode] = useState("automatic");
  const [selected, setSelected] = useState("");
  const project = selected || projects[0]?.id || "";
  return <section className="video-panel" aria-label="Produção de vídeos">
    <div className="video-toolbar"><label>Projeto dos vídeos<select value={project} onChange={event => setSelected(event.target.value)}>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><p>Roteiro, aprovação e MP4 em um só lugar.<br />Renderização local, sem chamadas de IA ou serviços pagos.</p></div>
    <div className="factory-mode" role="group" aria-label="Modo de criação"><button className="button" aria-pressed={mode === "automatic"} onClick={() => setMode("automatic")}>Modo automático</button><button className="button" aria-pressed={mode === "advanced"} onClick={() => setMode("advanced")}>Modo avançado</button></div>
    {project ? mode === "automatic" ? <ContentFactoryPanel key={project} project={project} /> : <ProjectVideos key={project} project={project} /> : <p>Crie um projeto para preparar seu primeiro vídeo.</p>}
  </section>;
}

function ProjectVideos({ project }: { project: string }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const generation = useRef(0);

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
    if (busy) return false;
    setBusy(true); setError(""); generation.current += 1;
    try { await action(); await refresh(); setMessage(success); return true; }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível concluir"); return false; }
    finally { setBusy(false); }
  }
  useEffect(() => {
    if (!snapshot?.items.some(job => ["queued", "rendering"].includes(job.status))) return;
    const controller = new AbortController();
    const timer = window.setInterval(() => { void refresh(controller.signal).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Falha ao atualizar progresso"); }); }, 1800);
    return () => { controller.abort(); window.clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot?.items]);

  return <>
    <div className="video-statusbar"><p role="status">{message}</p><button className="button" disabled={busy} onClick={() => void perform(async () => {}, "Vídeos atualizados")}>Atualizar vídeos</button></div>
    {error && <p role="alert" className="video-error">{error}</p>}
    {snapshot && !snapshot.renderer.available && <aside className="video-notice"><strong>Renderizador indisponível neste servidor</strong><p>{snapshot.renderer.reason}. Você pode preparar e revisar o roteiro. A geração exige o worker de vídeo configurado.</p></aside>}
    <VideoStudio key={project} project={project} supports1080p={snapshot?.renderer.supports_1080p === true} busy={busy} onRender={(document: StudioDocument, requestId: string) => perform(() => api(`/video-studio/${project}/render`, { method: "POST", body: JSON.stringify({ request_id: requestId, document, consent: true }) }), "Roteiro pronto para revisão")} />
    <div className="video-history"><h2>Produção do projeto</h2><p>Revise o roteiro salvo antes de aprovar. O worker processa a fila em separado; use Atualizar vídeos para acompanhar.</p>{snapshot?.items.length === 0 && <p>Nenhum vídeo neste projeto.</p>}{snapshot?.items.map(job => <article className="panel video-card" key={job.id}><div className="video-card-heading"><h3>{job.title}</h3><span className="video-badge">{labels[job.status] || job.status}</span></div><p>{job.format === "vertical" ? "Vertical" : job.format === "square" ? "Quadrado" : "Horizontal"} · {job.scenes.reduce((sum, scene) => sum + scene.duration, 0)} segundos</p><ol>{job.scenes.map((scene, index) => <li key={index}><p className="video-caption">{scene.text}</p><small>{scene.duration} segundos</small></li>)}</ol>{typeof job.progress === "number" && ["queued", "rendering"].includes(job.status) && <div className="video-progress"><progress aria-label={`Progresso de ${job.title}`} max={100} value={job.progress} /><small>{job.phase} · {Math.round(job.progress)}%</small></div>}{job.error && <p className="video-error">{job.error}</p>}{job.status === "pending_approval" && <><small className="video-digest">Digest do roteiro: {job.digest}</small><div className="video-actions"><button className="button primary" disabled={busy} onClick={() => void perform(() => api(`/videos/${job.id}/decision`, { method: "POST", body: JSON.stringify({ digest: job.digest, approve: true }) }), "Roteiro aprovado; vídeo na fila")}>Aprovar e gerar MP4</button><button className="button" disabled={busy} onClick={() => void perform(() => api(`/videos/${job.id}/decision`, { method: "POST", body: JSON.stringify({ digest: job.digest, approve: false }) }), "Roteiro recusado")}>Recusar roteiro</button></div></>}{["queued", "rendering"].includes(job.status) && <button className="button" disabled={busy} onClick={() => void perform(() => api(`/videos/${job.id}/cancel`, { method: "POST" }), "Vídeo cancelado")}>Cancelar vídeo</button>}{job.status === "completed" && <a className="button primary" href={`/api/control/videos/${job.id}/download`} download>Baixar MP4</a>}</article>)}</div>
  </>;
}
