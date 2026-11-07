"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, api } from "@/lib/api";
import { contentUrl, duration, newDocument, newScene, type Media, type Scene, type StudioDocument, type Template } from "@/lib/video-studio";
import { VideoStudioPreview } from "./video-studio-preview";

type Draft = { revision: number; document: StudioDocument | null };
export function VideoStudio({ project, supports1080p, busy, onRender }: { project: string; supports1080p: boolean; busy: boolean; onRender: (document: StudioDocument, requestId: string) => Promise<boolean> }) {
  const [document, setDocument] = useState<StudioDocument>(newDocument);
  const [media, setMedia] = useState<Media[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [active, setActive] = useState(0);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [saveStatus, setSaveStatus] = useState("Carregando rascunho…");
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [consent, setConsent] = useState(false);
  const requestId = useRef("");
  const properties = useRef<HTMLElement>(null);
  const lifecycle = useRef<AbortController | null>(null);
  const revision = useRef(0);
  const pending = useRef<StudioDocument | null>(null);
  const saving = useRef(false);
  const blocked = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const total = duration(document);
  const scene = document.scenes[active];
  const base = `/video-studio/${project}`;
  useEffect(() => {
    const controller = new AbortController(); lifecycle.current = controller;
    void Promise.all([api<Draft>(`${base}/draft`, { signal: controller.signal }), api<{ items: Media[] }>(`${base}/media`, { signal: controller.signal }), api<{ items: Template[] }>(`${base}/templates`, { signal: controller.signal })]).then(([draft, library, presets]) => {
      if (controller.signal.aborted) return;
      revision.current = draft.revision; setDocument(draft.document || newDocument()); setMedia(library.items); setTemplates(presets.items); setReady(true); setSaveStatus(draft.document ? "Rascunho salvo" : "Novo rascunho");
    }).catch(err => { if (!controller.signal.aborted) { setError(err instanceof Error ? err.message : "Falha ao carregar estúdio"); setSaveStatus("Não foi possível carregar o rascunho"); } });
    return () => { controller.abort(); if (timer.current) clearTimeout(timer.current); pending.current = null; };
  }, [base]);
  async function flush() {
    if (saving.current || blocked.current || !pending.current || lifecycle.current?.signal.aborted) return;
    const next = pending.current;
    if (!next.title.trim()) { setSaveStatus("Informe o título para salvar"); return; }
    pending.current = null; saving.current = true; setSaveStatus("Salvando…");
    try {
      const result = await api<Draft>(`${base}/draft`, { method: "PUT", signal: lifecycle.current?.signal, body: JSON.stringify({ revision: revision.current, document: next }) });
      if (lifecycle.current?.signal.aborted) return;
      revision.current = result.revision; setSaveStatus(pending.current ? "Alterações pendentes" : "Rascunho salvo");
    } catch (err) {
      if (lifecycle.current?.signal.aborted) return;
      pending.current ??= next;
      blocked.current = true;
      if (err instanceof ApiError && err.status === 409) { setConflict(true); setSaveStatus("Conflito de revisão"); }
      else { setSaveStatus("Falha ao salvar"); setError(err instanceof Error ? err.message : "Falha ao salvar"); }
    } finally {
      saving.current = false;
      if (pending.current && !blocked.current && !lifecycle.current?.signal.aborted) void flush();
    }
  }
  function edit(next: StudioDocument) {
    setDocument(next); setPlaying(false); setTime(current => Math.min(current, duration(next))); requestId.current = ""; pending.current = next; setSaveStatus("Alterações pendentes");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void flush(), 700);
  }
  function patchScene(patch: Partial<Scene>) { edit({ ...document, scenes: document.scenes.map((item, index) => index === active ? { ...item, ...patch } : item) }); }
  function select(index: number) { if (properties.current) properties.current.scrollTop = 0; setActive(index); setPlaying(false); setTime(document.scenes.slice(0, index).reduce((sum, item) => sum + item.duration, 0)); }
  function move(delta: number) {
    const scenes = [...document.scenes]; [scenes[active], scenes[active + delta]] = [scenes[active + delta], scenes[active]]; edit({ ...document, scenes }); setActive(active + delta); setTime(scenes.slice(0, active + delta).reduce((sum, item) => sum + item.duration, 0));
  }
  async function reloadDraft() {
    try {
      const draft = await api<Draft>(`${base}/draft`, { signal: lifecycle.current?.signal });
      if (lifecycle.current?.signal.aborted) return;
      if (timer.current) clearTimeout(timer.current);
      revision.current = draft.revision; pending.current = null; blocked.current = false; setConflict(false); setDocument(draft.document || newDocument()); setActive(0); setTime(0); setPlaying(false); setSaveStatus("Rascunho salvo");
    } catch (err) { if (!lifecycle.current?.signal.aborted) setError(err instanceof Error ? err.message : "Falha ao recarregar"); }
  }
  async function upload(file: File | undefined) {
    if (!file || uploading) return;
    if (file.size > 25 * 1024 * 1024) { setError("Cada arquivo deve ter até 25 MB."); return; }
    setUploading(true); setError("");
    try {
      const response = await fetch(`/api/control${base}/media?name=${encodeURIComponent(file.name)}`, { method: "POST", credentials: "same-origin", headers: { "content-type": file.type || "application/octet-stream" }, body: file, signal: lifecycle.current?.signal });
      if (!response.ok) { const result = await response.json().catch(() => ({})); throw new Error(typeof result.detail === "string" ? result.detail : "Não foi possível importar esta mídia."); }
      const library = await api<{ items: Media[] }>(`${base}/media`, { signal: lifecycle.current?.signal });
      if (!lifecycle.current?.signal.aborted) setMedia(library.items);
    } catch (err) { if (!lifecycle.current?.signal.aborted) setError(err instanceof Error ? err.message : "Falha no upload"); }
    finally { if (!lifecycle.current?.signal.aborted) setUploading(false); }
  }
  async function saveTemplate() {
    try { await api(`${base}/templates`, { method: "POST", body: JSON.stringify({ name: templateName, document }), signal: lifecycle.current?.signal }); const result = await api<{ items: Template[] }>(`${base}/templates`, { signal: lifecycle.current?.signal }); if (!lifecycle.current?.signal.aborted) { setTemplates(result.items); setTemplateName(""); } }
    catch (err) { if (!lifecycle.current?.signal.aborted) setError(err instanceof Error ? err.message : "Falha ao salvar template"); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!consent || !ready || busy) return;
    if (!requestId.current) requestId.current = crypto.randomUUID();
    if (await onRender(document, requestId.current)) requestId.current = "";
  }
  return <div className="studio-shell">
    <div className="studio-heading"><div><span className="video-eyebrow">ESTÚDIO LOCAL · 2.0</span><h2>Uma ideia. Cena por cena.</h2><p>Monte sua história com imagens, clipes e áudio. Revise antes de gerar o MP4.</p></div><span className="studio-save" aria-live="polite">{saveStatus}</span></div>
    {error && <p role="alert" className="video-error">{error}</p>}
    {conflict && <aside className="video-notice"><strong>Este rascunho mudou em outra janela.</strong><p>Suas alterações continuam no editor. Recarregar substitui as alterações locais pela versão salva; copie seu texto antes de continuar.</p><button className="button" type="button" onClick={() => void reloadDraft()}>Recarregar versão salva</button></aside>}
    {!conflict && saveStatus === "Falha ao salvar" && <button className="button" type="button" onClick={() => { blocked.current = false; setError(""); void flush(); }}>Tentar salvar novamente</button>}
    <form onSubmit={event => void submit(event)}>
      <fieldset className="studio-workspace" disabled={!ready || busy}>
        <aside className="studio-scenes panel"><div className="video-scene-heading"><h3>Suas cenas</h3><span>{document.scenes.length}/6</span></div><ol className="studio-scene-list">{document.scenes.map((item, index) => <li key={index}><button className={`studio-scene-tile ${index === active ? "selected" : ""}`} type="button" aria-label={`Selecionar cena ${index + 1}`} aria-pressed={index === active} onClick={() => select(index)}><span className="studio-scene-number">{String(index + 1).padStart(2, "0")}</span><span><strong>{item.text || "Nova cena"}</strong><small>{item.duration}s · {item.media_id ? "Com mídia" : "Fundo gráfico"}</small></span></button></li>)}</ol><button className="button" type="button" disabled={document.scenes.length >= 6 || total >= 60} onClick={() => { const scenes = [...document.scenes, { ...newScene(), duration: Math.min(5, 60 - total) }]; edit({ ...document, scenes }); setActive(scenes.length - 1); setTime(total); }}>Adicionar cena</button><p className="studio-limit">{total} / 60 segundos</p></aside>
        <div className="studio-center"><VideoStudioPreview document={document} project={project} media={media} time={time} playing={playing} onTime={setTime} onPlaying={setPlaying} /><div className="studio-timeline" aria-label="Timeline">{document.scenes.map((item, index) => <button type="button" key={index} style={{ flexGrow: item.duration }} className={active === index ? "selected" : ""} onClick={() => select(index)} aria-label={`Ir para cena ${index + 1}`}>{index + 1}<small>{item.duration}s</small></button>)}</div></div>
        <aside ref={properties} className="studio-properties panel"><div className="video-scene-heading"><h3>Cena {active + 1}</h3><span>Propriedades</span></div>
          <label>Texto da cena {active + 1}<textarea aria-label={`Texto da cena ${active + 1}`} maxLength={240} rows={3} value={scene.text} onChange={event => patchScene({ text: event.target.value })} /></label>
          <label>Duração da cena {active + 1} (segundos)<input type="number" min={1} max={Math.min(20, 60 - total + scene.duration)} required value={scene.duration} onChange={event => { const value = Number(event.target.value); if (Number.isInteger(value) && value >= 1 && value <= Math.min(20, 60 - total + scene.duration)) patchScene({ duration: value }); }} /></label>
          <label>Mídia da cena<select value={scene.media_id || ""} onChange={event => patchScene({ media_id: event.target.value || null })}><option value="">Apenas fundo gráfico</option>{media.filter(item => item.kind !== "audio").map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <div className="studio-field-pair"><label>Fonte<select value={scene.font} onChange={event => patchScene({ font: event.target.value as Scene["font"] })}><option value="sans">Sans</option><option value="serif">Serif</option><option value="mono">Mono</option></select></label><label>Tamanho do texto<input type="number" min={18} max={96} required value={scene.font_size} onChange={event => { const value = Number(event.target.value); if (value >= 18 && value <= 96 && Number.isInteger(value)) patchScene({ font_size: value }); }} /></label></div>
          <div className="studio-field-pair"><label>Cor do texto<input type="color" value={scene.color} onChange={event => patchScene({ color: event.target.value })} /></label><label>Cor do fundo<input type="color" value={scene.background} onChange={event => patchScene({ background: event.target.value })} /></label></div>
          <label>Posição horizontal · {scene.x}%<input aria-label="Posição horizontal" type="range" min={0} max={100} value={scene.x} onChange={event => patchScene({ x: Number(event.target.value) })} /></label><label>Posição vertical · {scene.y}%<input aria-label="Posição vertical" type="range" min={0} max={100} value={scene.y} onChange={event => patchScene({ y: Number(event.target.value) })} /></label>
          <label>Animação da cena<select value={scene.animation} onChange={event => patchScene({ animation: event.target.value as Scene["animation"] })}><option value="none">Sem animação</option><option value="fade">Fade</option><option value="zoom">Zoom suave</option><option value="pan">Panorâmica</option></select></label><label>Animação do texto<select value={scene.text_animation} onChange={event => patchScene({ text_animation: event.target.value as Scene["text_animation"] })}><option value="none">Sem animação</option><option value="fade">Fade</option><option value="slide">Deslizar</option></select></label><label>Transição<select value={scene.transition} onChange={event => patchScene({ transition: event.target.value as Scene["transition"] })}><option value="cut">Corte</option><option value="fade">Fade através de preto</option></select></label>
          <div className="studio-scene-tools"><button type="button" className="button" aria-label="Mover cena para cima" disabled={active === 0} onClick={() => move(-1)}>↑</button><button type="button" className="button" aria-label="Mover cena para baixo" disabled={active === document.scenes.length - 1} onClick={() => move(1)}>↓</button><button type="button" className="button" disabled={document.scenes.length >= 6 || total + scene.duration > 60} onClick={() => { const scenes = [...document.scenes]; scenes.splice(active + 1, 0, { ...scene }); edit({ ...document, scenes }); setActive(active + 1); setTime(document.scenes.slice(0, active + 1).reduce((sum, item) => sum + item.duration, 0)); }}>Duplicar cena</button><button type="button" className="button" disabled={document.scenes.length === 1} onClick={() => { edit({ ...document, scenes: document.scenes.filter((_, index) => index !== active) }); setActive(Math.max(0, active - 1)); }}>Remover cena {active + 1}</button></div>
        </aside>
      </fieldset>
      <fieldset className="studio-export panel" disabled={!ready || busy}><div className="studio-export-fields"><label>Título do vídeo<input required maxLength={120} value={document.title} onChange={event => edit({ ...document, title: event.target.value })} /></label><label>Formato do vídeo<select value={document.format} onChange={event => edit({ ...document, format: event.target.value as StudioDocument["format"] })}><option value="vertical">Vertical · 9:16</option><option value="square">Quadrado · 1:1</option><option value="horizontal">Horizontal · 16:9</option></select></label><label>Resolução<select value={document.resolution} onChange={event => edit({ ...document, resolution: event.target.value as StudioDocument["resolution"] })}><option value="720p">720p</option><option value="1080p" disabled={!supports1080p}>1080p{!supports1080p ? " · indisponível" : ""}</option></select></label></div><label className="video-consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />Autorizo gerar este vídeo localmente após revisar o roteiro</label><button className="button primary" disabled={!consent || busy || !ready || total > 60}>Preparar revisão</button><p>O roteiro será salvo para sua aprovação. A geração acontece no worker local.</p></fieldset>
    </form>
    <section className="studio-resources"><div className="panel"><div className="video-scene-heading"><h3>Biblioteca do projeto</h3><span>{media.length} arquivos</span></div><p>Imagens, vídeos e áudio privados · até 25 MB por arquivo.</p><label className="studio-upload">{uploading ? "Importando mídia…" : "Importar mídia local"}<input aria-label="Importar mídia local" type="file" accept="image/png,image/jpeg,image/webp,video/mp4,video/webm,audio/mpeg,audio/wav,audio/ogg,audio/mp4" disabled={!ready || uploading} onChange={event => { void upload(event.target.files?.[0]); event.target.value = ""; }} /></label><ul className="studio-media-list">{media.map(item => <li key={item.id}><span>{item.name}<small>{item.kind} · {(item.bytes / 1024 / 1024).toFixed(1)} MB</small></span>{item.kind !== "audio" && <button className="button" type="button" disabled={!ready || busy} onClick={() => patchScene({ media_id: item.id })}>Usar na cena {active + 1}</button>}<a href={contentUrl(project, item.id)} target="_blank" rel="noreferrer" className="studio-media-link">Abrir<span className="sr-only"> {item.name}</span></a></li>)}</ul>{!media.length && <p>Nenhuma mídia importada. Você também pode criar usando apenas texto e cores.</p>}<label>Áudio de fundo<select disabled={!ready || busy} value={document.audio?.media_id || ""} onChange={event => edit({ ...document, audio: event.target.value ? { media_id: event.target.value, volume: .5, fade_in: .4, fade_out: .4 } : null })}><option value="">Sem áudio</option>{media.filter(item => item.kind === "audio").map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{document.audio && <div className="studio-audio-fields"><label>Volume<input type="range" min={0} max={1} step={.05} value={document.audio.volume} onChange={event => edit({ ...document, audio: { ...document.audio!, volume: Number(event.target.value) } })} /></label>{(["fade_in", "fade_out"] as const).map(key => <label key={key}>{key === "fade_in" ? "Entrada do áudio (s)" : "Saída do áudio (s)"}<input type="number" min={0} max={3} step={.1} value={document.audio![key]} onChange={event => { const value = Number(event.target.value); if (value >= 0 && value <= 3) edit({ ...document, audio: { ...document.audio!, [key]: value } }); }} /></label>)}</div>}</div>
      <div className="panel"><h3>Comece com um template</h3><p>Escolha uma estrutura e personalize. Aplicar um template substitui o conteúdo atual do editor.</p><div className="studio-template-list">{templates.map(item => <button className="button" key={item.id} type="button" disabled={!ready || busy} onClick={() => { edit(structuredClone(item.document)); setActive(0); setTime(0); }}>{item.name}<small>{item.document.scenes.length} cenas · {duration(item.document)}s</small></button>)}</div><div className="studio-template-save"><label>Nome do seu template<input disabled={!ready || busy} maxLength={80} value={templateName} onChange={event => setTemplateName(event.target.value)} /></label><button className="button" type="button" disabled={!ready || busy || !templateName.trim() || !document.title.trim()} onClick={() => void saveTemplate()}>Salvar como template</button></div></div></section>
  </div>;
}
