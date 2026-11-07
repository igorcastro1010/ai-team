"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Project } from "@/lib/api";
import "@/styles/models.css";

type Preference = { agent: string; mode: "automatic" | "manual"; provider: "gemini" | "codex"; model: "gemini-2.5-flash-lite" | "codex-supervised"; enabled: boolean; quotas_confirmed: boolean; rpm: number; rpd: number; tpm: number; authorized_until: number };
type Snapshot = {
  catalog: { provider: string; model: string; capabilities: string[]; cost: string; dispatch: string }[];
  preferences: Preference[];
  providers: { id: string; configured?: boolean; status?: string; observation?: unknown }[];
  history: { id: string; run_id: string; agent: string; provider: string; model: string; status: string; reason: string; admitted: boolean; input_tokens: number | null; output_tokens: number | null; latency_ms: number | null }[];
  waiting: { id: string; stage: number; status: string; reason: string }[];
  local_caps: { rpm: number; rpd: number; tpm: number };
  measured_savings: null;
};
type Handoff = { digest: string; instructions: string; context: unknown; role: string; stage: number; run_id: string };
type Observation = { status?: string; verified_at?: string; expires_at?: string };
type Action = (signal: AbortSignal) => Promise<unknown>;
const statusLabels: Record<string, string> = { not_configured: "Não configurado", unavailable: "Indisponível", verified_free: "Elegibilidade gratuita verificada", waiting_model: "Aguardando modelo", waiting_quota: "Aguardando cota", awaiting_codex: "Aguardando Codex supervisionado", supervised_only: "Somente supervisionado", existing_executor_preserved: "Executor existente preservado", completed: "Concluído", succeeded: "Resposta concluída", failed: "Falhou", rejected: "Recusado", admitted: "Admitido", started: "Admissão reservada", uncertain: "Resultado incerto; revisão necessária", running: "Em execução", verified: "Verificação registrada" };
const statusText = (status: string) => statusLabels[status] || "Estado requer revisão";

export function ModelsPanel({ projects }: { projects: Project[] }) {
  const [selected, setSelected] = useState("");
  const project = projects.some(item => item.id === selected) ? selected : projects[0]?.id || "";
  return <section className="models-panel" aria-label="Central de IA">
    <header className="models-toolbar"><label>Projeto da central de IA<select value={project} onChange={event => setSelected(event.target.value)}>{projects.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><p>Escolha o modelo de cada agente.<br />Chamadas gratuitas exigem autorização e elegibilidade verificadas.</p></header>
    {project ? <ProjectModels key={project} project={project} /> : <div className="panel"><h2>Uma central para cada projeto.</h2><p>Crie um projeto para configurar sua equipe.</p></div>}
  </section>;
}

function ProjectModels({ project }: { project: string }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [agent, setAgent] = useState("CEO");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [prompt, setPrompt] = useState("");
  const [consent, setConsent] = useState(false);
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const [resumeConsent, setResumeConsent] = useState<Record<string, boolean>>({});
  const controllers = useRef(new Set<AbortController>());
  const actionLock = useRef(false);
  const requestId = useRef("");
  const endpoint = `/model-center/${encodeURIComponent(project)}`;

  useEffect(() => {
    const controller = new AbortController();
    const activeControllers = controllers.current;
    activeControllers.add(controller);
    void api<Snapshot>(endpoint, { signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) { setSnapshot(result); setMessage("Central atualizada"); }
    }).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Falha ao carregar a central"); });
    return () => { activeControllers.forEach(item => item.abort()); activeControllers.clear(); };
  }, [endpoint]);

  async function perform(action: Action, success: string) {
    if (actionLock.current) return;
    actionLock.current = true; setBusy(true); setError("");
    const controller = new AbortController();
    controllers.current.add(controller);
    try {
      await action(controller.signal);
      const result = await api<Snapshot>(endpoint, { signal: controller.signal });
      if (!controller.signal.aborted) { setSnapshot(result); setMessage(success); }
    } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Não foi possível concluir"); }
    finally { controllers.current.delete(controller); actionLock.current = false; if (!controller.signal.aborted) setBusy(false); }
  }
  const preference = snapshot?.preferences.find(item => item.agent === agent);

  return <>
    <div className="models-statusbar"><p role="status">{message || "Carregando central…"}</p><div className="models-actions"><button className="button" disabled={busy || !snapshot} onClick={() => void perform(async () => {}, "Central atualizada")}>Atualizar central</button><button className="button" disabled={busy || !snapshot} onClick={() => void perform(signal => api(`${endpoint}/check`, { method: "POST", signal, body: "{}" }), "Verificação enfileirada; nenhuma inferência executada")}>Verificar sem inferência</button></div></div>
    {error && <p role="alert" className="models-error">{error}</p>}
    <aside className="models-notice"><strong>Seu controle vem antes da execução.</strong><p>Sem fallback pago. Verificação consulta apenas metadados externos. Configuração não confirma conexão, gratuidade ou cota. Os limites de assinatura do Codex permanecem desconhecidos.</p></aside>
    {snapshot && <>
      <div className="models-metrics"><article className="panel"><span>LIMITES LOCAIS MÁXIMOS</span><strong>{snapshot.local_caps.rpm} / minuto · {snapshot.local_caps.rpd} / dia</strong><small>{snapshot.local_caps.tpm.toLocaleString("pt-BR")} tokens por minuto. Não representam a cota real do provedor.</small></article><article className="panel"><span>ECONOMIA REAL MEDIDA</span><strong>Não medida</strong><small>Contexto estimado e tokens reportados são informações diferentes de economia financeira.</small></article></div>
      <section className="models-section" aria-label="Provedores e catálogo"><div className="models-section-heading"><h2>Modelos disponíveis</h2><span>Disponibilidade com evidência</span></div><div className="models-catalog">{snapshot.catalog.map(model => {
        const provider = snapshot.providers.find(item => item.id === model.provider);
        const observation = provider?.observation && typeof provider.observation === "object" ? provider.observation as Observation : null;
        return <article className="panel" key={model.model}><div className="models-card-heading"><h3>{model.provider === "gemini" ? "Gemini" : "Codex"}</h3><span className="models-badge">{provider?.status ? statusText(provider.status) : observation?.status ? statusText(observation.status) : provider?.configured ? "Configurado; verificação pendente" : "Não configurado"}</span></div><p className="models-model-name">{model.model}</p><p>{model.provider === "gemini" ? "Texto e respostas estruturadas. Execução apenas com elegibilidade gratuita verificada." : "Código e revisão por encaminhamento supervisionado. A central não afirma execução automática."}</p><small>{model.provider === "gemini" ? "Custo exige elegibilidade gratuita" : "Limites de assinatura desconhecidos"}</small>{observation?.verified_at && <p className="models-helper">Verificação registrada: {new Date(observation.verified_at).toLocaleString("pt-BR")}. {observation.expires_at && `Validade até ${new Date(observation.expires_at).toLocaleString("pt-BR")}.`} Revalidada pelo executor antes da chamada.</p>}</article>;
      })}</div></section>
      <div className="models-columns"><section className="panel models-preferences" aria-label="Preferências por agente"><span className="models-eyebrow">ROTEAMENTO DO PROJETO</span><h2>Quem usa qual modelo.</h2><label>Agente da preferência<select value={agent} disabled={busy} onChange={event => setAgent(event.target.value)}>{snapshot.preferences.map(item => <option value={item.agent} key={item.agent}>{item.agent}</option>)}</select></label>{preference && <PreferenceForm key={JSON.stringify(preference)} preference={preference} busy={busy} save={policy => perform(signal => api(`${endpoint}/preferences/${agent}`, { method: "PUT", signal, body: JSON.stringify(policy) }), `Preferência de ${agent} salva`)} />}</section>
        <form aria-label="Pedido à central" className="panel models-request" onSubmit={event => { event.preventDefault(); if (!consent || !prompt.trim()) return; if (!requestId.current) requestId.current = crypto.randomUUID(); void perform(signal => api(`${endpoint}/requests`, { method: "POST", signal, body: JSON.stringify({ prompt, request_id: requestId.current, consent: true }) }), "Pedido na fila supervisionada. Acompanhe a execução no CEO."); }}><span className="models-eyebrow">FILA SUPERVISIONADA</span><h2>Um pedido para a equipe.</h2><p>O worker revalida autorização, elegibilidade e cotas antes de cada chamada. Criar o pedido não confirma inferência.</p><label>Pedido para a equipe<textarea required rows={7} minLength={3} maxLength={5000} disabled={busy} value={prompt} onChange={event => { setPrompt(event.target.value); requestId.current = ""; setConsent(false); }} /></label><label className="models-check"><input type="checkbox" checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} />Autorizo colocar este pedido na fila supervisionada</label><button className="button primary" disabled={busy || !consent || !prompt.trim()}>Enviar para a fila</button></form></div>
      <section className="models-section" aria-label="Execuções aguardando"><div className="models-section-heading"><h2>Em espera</h2><span>{snapshot.waiting.length} execução(ões)</span></div>{!snapshot.waiting.length && <p>Nenhuma execução aguardando modelo ou cota neste projeto.</p>}<div className="models-waiting">{snapshot.waiting.map(item => <article className="panel" key={item.id}><div className="models-card-heading"><h3>Etapa {item.stage + 1}</h3><span className="models-badge">{statusText(item.status)}</span></div><small className="models-id">{item.id}</small><p>{item.reason || "Revise a autorização e a disponibilidade antes de retomar."}</p>{item.status === "awaiting_codex" && <button className="button" disabled={busy} onClick={() => void perform(async signal => { const result = await api<Handoff>(`${endpoint}/handoff/${item.id}`, { signal }); if (!signal.aborted) setHandoff(result); }, "Contexto preparado para encaminhamento manual")}>Ver contexto para Codex</button>}<label className="models-check"><input type="checkbox" disabled={busy} checked={!!resumeConsent[item.id]} onChange={event => setResumeConsent(current => ({ ...current, [item.id]: event.target.checked }))} />Autorizo retomar esta execução após revisar os limites</label><button className="button" disabled={busy || !resumeConsent[item.id]} onClick={() => void perform(signal => api(`${endpoint}/resume/${item.id}`, { method: "POST", signal, body: JSON.stringify({ consent: true }) }), "Retomada solicitada; política será revalidada")}>Solicitar retomada</button></article>)}</div></section>
      {handoff && <section className="panel models-handoff" aria-label="Encaminhamento manual"><div className="models-card-heading"><h2>Contexto para Codex</h2><button className="button" onClick={() => setHandoff(null)}>Fechar contexto</button></div><p>Conteúdo para revisão e encaminhamento manual. Nenhuma execução do Codex foi confirmada.</p><pre tabIndex={0}>{JSON.stringify(handoff, null, 2)}</pre></section>}
      <section className="models-section" aria-label="Histórico de roteamento"><h2>Histórico e uso reportado</h2><p>Um registro admitido indica decisão de política; tokens e latência só aparecem quando reportados.</p>{!snapshot.history.length && <div className="panel"><p>Nenhuma chamada registrada neste projeto.</p></div>}<div className="models-history">{snapshot.history.map(item => <article className="panel" key={item.id}><div className="models-card-heading"><h3>{item.agent} · {item.provider}</h3><span className="models-badge">{statusText(item.status)}</span></div><p className="models-model-name">{item.model}</p><p>{item.reason}</p><dl><div><dt>Admissão</dt><dd>{item.admitted ? "Admitida pela política" : "Não admitida"}</dd></div><div><dt>Tokens de entrada / saída</dt><dd>{item.input_tokens ?? "Não reportado"} / {item.output_tokens ?? "Não reportado"}</dd></div><div><dt>Latência</dt><dd>{item.latency_ms === null ? "Não reportada" : `${item.latency_ms} ms`}</dd></div></dl></article>)}</div></section>
    </>}
  </>;
}

function PreferenceForm({ preference, busy, save }: { preference: Preference; busy: boolean; save: (value: Omit<Preference, "agent" | "authorized_until">) => Promise<void> }) {
  const { agent, authorized_until, ...initial } = preference;
  const [draft, setDraft] = useState(initial);
  return <form aria-label={`Preferência de ${agent}`} className="models-policy" onSubmit={event => { event.preventDefault(); void save(draft); }}>
    <fieldset disabled={busy}><legend>Preferência de {agent}</legend><label>Modo de seleção<select value={draft.mode} onChange={event => setDraft(current => ({ ...current, mode: event.target.value as Preference["mode"] }))}><option value="automatic">Automático com política gratuita</option><option value="manual">Manual por agente</option></select></label><label>Provedor e modelo<select value={draft.provider} onChange={event => { const provider = event.target.value as Preference["provider"]; setDraft(current => ({ ...current, provider, model: provider === "gemini" ? "gemini-2.5-flash-lite" : "codex-supervised", enabled: false, quotas_confirmed: false })); }}><option value="gemini">Gemini · 2.5 Flash Lite</option><option value="codex">Codex · supervisionado</option></select></label>
      {draft.provider === "codex" && <p className="models-notice">Somente encaminhamento supervisionado. Nenhum limite da assinatura é presumido.</p>}
      <div className="models-rates">{(["rpm", "rpd", "tpm"] as const).map(key => <label key={key}>{({ rpm: "Chamadas / minuto", rpd: "Chamadas / dia", tpm: "Tokens / minuto" })[key]}<input type="number" required min={key === "tpm" ? 1000 : 1} max={key === "rpm" ? 2 : key === "rpd" ? 10 : 40000} step={1} value={draft[key]} onChange={event => setDraft(current => ({ ...current, [key]: Number(event.target.value) }))} /></label>)}</div>
      <label className="models-check"><input type="checkbox" disabled={draft.provider !== "gemini"} checked={draft.quotas_confirmed} onChange={event => setDraft(current => ({ ...current, quotas_confirmed: event.target.checked, enabled: false }))} />Confirmei as cotas reais deste projeto no AI Studio</label><label className="models-check"><input type="checkbox" disabled={draft.provider !== "gemini" || !draft.quotas_confirmed} checked={draft.enabled} onChange={event => setDraft(current => ({ ...current, enabled: event.target.checked }))} />Autorizo chamadas gratuitas por 24 horas</label><p className="models-helper">A autorização não libera serviços pagos. Ao salvar com a autorização marcada, a janela de 24 horas é renovada e o executor verifica a gratuidade novamente.</p>{authorized_until > 0 && <p className="models-helper">Autorização salva até {new Date(authorized_until * 1000).toLocaleString("pt-BR")}.</p>}<button className="button primary">Salvar preferência de {agent}</button></fieldset>
  </form>;
}
