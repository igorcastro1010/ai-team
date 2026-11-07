"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { type Media, type StudioDocument } from "@/lib/video-studio";
import { VideoStudioPreview } from "./video-studio-preview";

type Production = { id: string; project_id: string; status: string; stage: number; revision: number; digest: string; video_id: string | null; document: StudioDocument | null; error: string; request: { prompt: string }; steps: { agent: string; stage: number; summary: string; inference: boolean }[] };
type Video = { id: string; status: string; progress: number };
const labels: Record<string, string> = { queued: "Na fila local", running: "Processando etapa local", waiting_media: "Aguardando suas mídias", awaiting_approval: "Revise e aprove o roteiro", waiting_render: "Aguardando FFmpeg e validação", completed: "MP4 validado", failed: "Falha na produção", cancelled: "Produção cancelada" };
const stages = ["CEO · requisitos", "Pesquisador · roteiro", "Designer · montagem", "DEV · renderização", "QA · validação", "CEO · entrega"];

export function ContentFactoryPanel({ project }: { project: string }) {
  const [items, setItems] = useState<Production[]>([]);
  const [media, setMedia] = useState<Media[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [audio, setAudio] = useState("");
  const [prompt, setPrompt] = useState("");
  const [format, setFormat] = useState("vertical");
  const [seconds, setSeconds] = useState(15);
  const [style, setStyle] = useState("professional");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestId = useRef("");
  const generation = useRef(0);
  const load = useCallback(async (signal?: AbortSignal) => {
    const current = ++generation.current;
    const [rows, library, jobs] = await Promise.all([
      api<{ items: Production[] }>(`/content-factory/${project}`, { signal }),
      api<{ items: Media[] }>(`/video-studio/${project}/media`, { signal }),
      api<{ items: Video[] }>(`/videos?project_id=${project}`, { signal }),
    ]);
    if (!signal?.aborted && current === generation.current) { setItems(rows.items); setMedia(library.items); setVideos(jobs.items); }
  }, [project]);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => { if (document.visibilityState === "visible") void load(controller.signal).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Falha ao consultar produção"); }); };
    const initial = setTimeout(refresh, 0);
    const timer = setInterval(refresh, 2500);
    return () => { controller.abort(); clearTimeout(initial); clearInterval(timer); };
  }, [load]);
  async function perform(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true); setError("");
    try { await action(); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Falha na operação local"); }
    finally { setBusy(false); }
  }
  function invalidate() { requestId.current = ""; }
  async function upload(file?: File) {
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) { setError("Cada arquivo deve ter até 25 MB."); return; }
    await perform(async () => {
      const response = await fetch(`/api/control/video-studio/${project}/media?name=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "content-type": file.type || "application/octet-stream" }, body: file, credentials: "same-origin" });
      if (!response.ok) throw new Error("Upload recusado: verifique formato e limites do projeto.");
      const asset: Media = await response.json();
      if (asset.kind === "audio") setAudio(asset.id); else setSelected(old => [...new Set([...old, asset.id])].slice(0, 10));
      invalidate();
    });
  }
  return <section className="factory-panel" aria-label="Fábrica de conteúdo automatizada">
    <div className="panel"><p className="eyebrow">DA IDEIA AO MP4</p><h2>Descreva. Revise. Dê movimento.</h2><p>Regras e templates locais, sem inferência de IA. Usamos somente suas mídias. A renderização aguarda sua aprovação.</p>
      <form onSubmit={event => { event.preventDefault(); if (!requestId.current) requestId.current = crypto.randomUUID(); void perform(() => api("/content-factory", { method: "POST", body: JSON.stringify({ project_id: project, request_id: requestId.current, prompt, format, duration: seconds, style, media_ids: selected, audio_id: audio || null }) })); }}>
        <label>Descreva o vídeo que deseja criar<textarea required minLength={8} maxLength={2000} rows={4} value={prompt} onChange={event => { setPrompt(event.target.value); invalidate(); }} placeholder="Crie um Reels de 15 segundos apresentando meu chaveiro 3D…" /></label>
        <div className="factory-fields"><label>Formato da produção<select value={format} onChange={e => { setFormat(e.target.value); invalidate(); }}><option value="vertical">Vertical · 9:16</option><option value="square">Quadrado · 1:1</option><option value="horizontal">Horizontal · 16:9</option></select></label><label>Duração em segundos<input type="number" min={4} max={60} required value={seconds} onChange={e => { setSeconds(Number(e.target.value)); invalidate(); }} /></label><label>Estilo<select value={style} onChange={e => { setStyle(e.target.value); invalidate(); }}><option value="professional">Profissional</option><option value="promotion">Divulgação</option><option value="tutorial">Tutorial</option><option value="institutional">Institucional</option></select></label></div>
        <label>Importar logo, foto, vídeo ou áudio<input type="file" disabled={busy} accept="image/png,image/jpeg,image/webp,video/mp4,video/webm,audio/mpeg,audio/wav,audio/ogg" onChange={e => { void upload(e.target.files?.[0]); e.target.value = ""; }} /></label>
        <p className="field-help">Até 25 MB por arquivo. Sem foto do produto, usamos a logo e elementos gráficos; não inventamos imagens, voz ou música.</p>
        <fieldset className="factory-library"><legend>Mídias visuais desta produção · até 10</legend>{media.filter(asset => asset.kind !== "audio").map(asset => <label key={asset.id}><input type="checkbox" checked={selected.includes(asset.id)} disabled={busy || !selected.includes(asset.id) && selected.length >= 10} onChange={e => { setSelected(old => e.target.checked ? [...old, asset.id] : old.filter(id => id !== asset.id)); invalidate(); }} />{asset.name}</label>)}{!media.length && <p>Importe sua logo ou uma mídia própria para a montagem.</p>}</fieldset>
        <label>Áudio licenciado opcional<select value={audio} onChange={e => { setAudio(e.target.value); invalidate(); }}><option value="">Sem áudio</option>{media.filter(asset => asset.kind === "audio").map(asset => <option key={asset.id} value={asset.id}>{asset.name}</option>)}</select></label>
        <button className="button primary" disabled={busy || prompt.trim().length < 8}>Iniciar produção</button>
      </form>
    </div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <div className="section-toolbar"><h2>Suas produções</h2><Link href="/escritorio" className="button">Ver no escritório</Link></div>
    {!items.length && <p>Nenhuma produção automática neste projeto.</p>}
    {items.map(row => <article key={row.id} className="panel factory-production" data-testid="factory-production"><h3>{row.document?.title || row.request.prompt.slice(0, 100)}</h3><p role="status">{labels[row.status] || row.status}</p><p className="field-help">Processamento determinístico local · nenhuma inferência de IA</p>
      <ol className="factory-stages">{stages.map((name, index) => <li key={name} data-done={row.steps.some(step => step.stage === index) && !(index === 2 && row.status === "waiting_media") && !(index === 3 && row.status === "waiting_render")}>{name}</li>)}</ol>
      <details><summary>Histórico real das etapas</summary>{row.steps.map((step, index) => <p key={index}>{step.summary}</p>)}</details>
      {row.error && <p className="notice error">{row.error}</p>}
      {row.status === "failed" && <button type="button" className="button" disabled={busy} onClick={() => void perform(() => api(`/content-factory/${project}/${row.id}/resume`, { method: "POST", body: "{}" }))}>Revisar e tentar novamente</button>}
      {row.status === "waiting_media" && <button type="button" className="button" disabled={busy || !selected.length} onClick={() => void perform(() => api(`/content-factory/${project}/${row.id}/resume`, { method: "POST", body: JSON.stringify({ media_ids: selected }) }))}>Retomar com mídias selecionadas</button>}
      {row.document && <FactoryReview key={`${row.id}-${row.revision}`} row={row} media={media} busy={busy} save={document => perform(() => api(`/content-factory/${project}/${row.id}`, { method: "PUT", body: JSON.stringify({ revision: row.revision, document }) }))} approve={() => perform(() => api(`/content-factory/${project}/${row.id}/approve`, { method: "POST", body: JSON.stringify({ digest: row.digest }) }))} />}
      {row.video_id && videos.find(v => v.id === row.video_id)?.status === "rendering" && <progress aria-label="Progresso real da renderização" max={100} value={videos.find(v => v.id === row.video_id)?.progress || 0} />}
      {!["completed", "failed", "cancelled"].includes(row.status) && <button type="button" className="button" disabled={busy} onClick={() => void perform(() => api(`/content-factory/${project}/${row.id}/cancel`, { method: "POST" }))}>Cancelar produção</button>}
      {row.status === "completed" && row.video_id && <a className="button primary" href={`/api/control/videos/${row.video_id}/download`} download>Baixar MP4 validado</a>}
    </article>)}
  </section>;
}

function FactoryReview({ row, media, busy, save, approve }: { row: Production; media: Media[]; busy: boolean; save: (document: StudioDocument) => Promise<void>; approve: () => Promise<void> }) {
  const [document, setDocument] = useState(row.document!);
  const [dirty, setDirty] = useState(false);
  const [consent, setConsent] = useState(false);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const editable = row.status === "awaiting_approval";
  function change(next: StudioDocument) { setDocument(next); setDirty(true); setConsent(false); }
  return <div className="factory-review"><VideoStudioPreview document={document} project={row.project_id} media={media} time={time} playing={playing} onTime={setTime} onPlaying={setPlaying} /><fieldset disabled={!editable || busy}><legend>Revise o roteiro antes de renderizar</legend><label>Título da produção<input maxLength={120} value={document.title} onChange={e => change({ ...document, title: e.target.value })} /></label>{document.scenes.map((scene, index) => <div key={index}><label>Texto automático da cena {index + 1}<textarea maxLength={240} value={scene.text} onChange={e => change({ ...document, scenes: document.scenes.map((item, i) => i === index ? { ...item, text: e.target.value } : item) })} /></label><label>Duração da cena {index + 1}<input type="number" min={1} max={20} value={scene.duration} onChange={e => change({ ...document, scenes: document.scenes.map((item, i) => i === index ? { ...item, duration: Number(e.target.value) } : item) })} /></label></div>)}<button className="button" type="button" disabled={!dirty} onClick={() => void save(document)}>Salvar revisão do roteiro</button><code className="code-digest">{row.digest}</code><label className="consent-row"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />Revisei este roteiro e autorizo renderizar localmente este digest</label><button type="button" className="button primary" disabled={dirty || !consent} onClick={() => void approve()}>Aprovar e renderizar</button></fieldset></div>;
}
