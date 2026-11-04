"use client";
import Link from "next/link";
import { useEffect, useState, type CSSProperties } from "react";
import { ArrowUpRight, Radio, ShieldCheck, Pause, Play, Plus, Minus, Search, Activity, MapPin, Coffee } from "lucide-react";
import { dateTime, type OfficeAgent, type Workspace } from "@/lib/api";
import { AgentSprite, OfficeMap, agentPlaces } from "./office-map";
import "@/styles/office.css";

const labels = { available: "Disponível", working: "Trabalhando", awaiting_approval: "Aguardando aprovação", completed: "Concluído", error: "Erro" };
const colors = ["#b6ec81", "#83c6ff", "#dbabff", "#ffd185", "#81d8c8", "#ffa9be", "#b8bdff"];

function actorStyle(index: number): CSSProperties {
  const place = agentPlaces[index % agentPlaces.length];
  // Orthogonal route: home → own doorway → corridor → lounge doorway → lounge.
  return {
    "--agent-color": colors[index % colors.length], left: `${place.x}%`, top: `${place.y}%`,
    "--door-x": `${place.door - place.x}cqw`, "--hall-y": `${49 - place.y}cqh`,
    "--lounge-x": `${49.8 - place.x}cqw`, "--lounge-y": `${73 - place.y}cqh`,
    "--walk-delay": `${-index * 4}s`, "--walk-time": `${38 + index * 3}s`,
  } as CSSProperties;
}

export function PixelOffice({ data, connected }: { data: Workspace; connected: boolean }) {
  const [selected, setSelected] = useState("CEO");
  const [now, setNow] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [visible, setVisible] = useState(true);
  const [zoom, setZoom] = useState(100);
  const [query, setQuery] = useState("");
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => { setReduced(preference.matches); setVisible(document.visibilityState === "visible"); setNow(Date.now() / 1000); };
    const initial = window.setTimeout(update, 0);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") setNow(Date.now() / 1000); }, 1000);
    preference.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); preference.removeEventListener("change", update); document.removeEventListener("visibilitychange", update); };
  }, []);
  const fresh = connected && now > 0 && Math.abs(now - data.office_observed_at) < 15;
  const motion = reduced ? "reduced" : paused || !fresh || !visible ? "paused" : "running";
  const agents = data.office || [];
  const current = agents.find(agent => agent.id === selected) || agents[0];
  const active = fresh ? agents.filter(agent => agent.animate).length : 0;
  const pending = agents.filter(agent => agent.status === "awaiting_approval").length;
  const filtered = agents.filter(agent => `${agent.name} ${agent.role}`.toLocaleLowerCase("pt-BR").includes(query.toLocaleLowerCase("pt-BR")));
  const events = [...data.events].sort((a, b) => b.created_at - a.created_at).slice(0, 5);
  return <>
    <div className="office-campus" data-motion={motion}>
      <div className="office-commandbar">
        <div className="office-campus-brand"><span className="office-brand-grid" aria-hidden="true"><i /><i /><i /><i /></span><strong>ai<span>TEAM</span></strong><small>ESCRITÓRIO</small></div>
        <div className="office-counters"><span><b>6</b> ambientes</span><span><b>{agents.length}</b> agentes</span><span className="office-counter-active"><b>{active}</b> em execução</span>{pending > 0 && <Link href="/aprovacoes" className="office-needs-you"><b>{pending}</b> precisa{pending > 1 ? "m" : ""} de você</Link>}</div>
        <span className={`office-connection ${fresh ? "connected" : ""}`}><Radio size={13} aria-hidden="true" />{fresh ? "Conectado" : "Sem sinal recente"}</span>
      </div>
      <div className="office-stage-layout">
        <aside className="office-roster" aria-label="Equipe do escritório">
          <div className="office-roster-heading"><h2>Sua equipe</h2><span>{agents.filter(a => a.enabled).length} perfis ativos</span></div>
          <div className="office-search"><Search size={14} aria-hidden="true" /><input aria-label="Buscar agente" value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar agente…" /></div>
          <div className="office-agent-list">{filtered.map(agent => {
            const index = agents.indexOf(agent);
            return <button type="button" key={agent.id} className={`office-roster-agent ${selected === agent.id ? "selected" : ""}`} style={{ "--agent-color": colors[index % colors.length] } as CSSProperties} onClick={() => setSelected(agent.id)} aria-pressed={selected === agent.id} aria-label={`Abrir detalhes de ${agent.name}: ${agent.enabled ? labels[agent.status] : "Papel preparado"}`}>
              <span className="office-roster-avatar"><AgentSprite variant={index} /></span><span><strong>{agent.name}</strong><small>{agent.enabled ? labels[agent.status] : "Em preparação"}</small></span><i className={`office-dot state-${agent.status}`} aria-hidden="true" />
            </button>;
          })}{!filtered.length && <p className="office-no-results">Nenhum agente encontrado.</p>}</div>
          <div className="office-project-list"><div className="office-roster-heading"><h3>Projetos</h3><Link href="/projetos" aria-label="Ver todos os projetos"><ArrowUpRight size={16} aria-hidden="true" /></Link></div>
            {!data.projects.length && <p>Seu próximo projeto começa com uma conversa.</p>}
            {data.projects.slice(0, 3).map(project => { const tasks = data.tasks.filter(task => task.project_id === project.id); const done = tasks.filter(task => task.status === "done").length; return <Link href="/projetos" className="office-project" key={project.id}><strong>{project.name}</strong><span><i style={{ width: `${tasks.length ? done / tasks.length * 100 : 0}%` }} /></span><small>{done}/{tasks.length} tarefas</small></Link>; })}
          </div>
          <div className="office-roster-footer"><Coffee size={15} aria-hidden="true" /><span>Boas ideias precisam<br />de um lugar para acontecer.</span></div>
        </aside>
        <div className="office-scene-column">
          <div className="office-scene-toolbar"><span><MapPin size={13} aria-hidden="true" /> Campus Fortaleza <small>/ 01</small></span><div className="office-map-controls"><button type="button" aria-label={paused ? "Retomar animações" : "Pausar animações"} aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? <Play size={15} /> : <Pause size={15} />}</button><span className="office-control-divider" /><button type="button" aria-label="Reduzir mapa" disabled={zoom <= 100} onClick={() => setZoom(Math.max(100, zoom - 15))}><Minus size={16} /></button><button type="button" className="office-zoom-value" aria-label="Restaurar zoom" onClick={() => setZoom(100)}>{zoom}%</button><button type="button" aria-label="Ampliar mapa" disabled={zoom >= 145} onClick={() => setZoom(Math.min(145, zoom + 15))}><Plus size={16} /></button></div></div>
          <section className="office-map-viewport" aria-label="Mapa do escritório virtual" tabIndex={0}>
            <div className="office-map-world" style={{ "--map-zoom": zoom / 100 } as CSSProperties}>
              <OfficeMap />
              {agents.map((agent, index) => {
                const working = fresh && agent.animate;
                const walking = agent.enabled && ["available", "completed"].includes(agent.status) && !working;
                return <span key={agent.id} className={`office-actor pixel-station ${working ? "is-working" : ""} ${walking ? "is-walking" : ""} ${!agent.enabled ? "is-prepared" : ""} ${selected === agent.id ? "is-selected" : ""}`} style={actorStyle(index)}>
                  <button type="button" className="actor-travel" onClick={() => setSelected(agent.id)} aria-label={`Selecionar ${agent.name} no mapa`} aria-pressed={selected === agent.id}>{agent.status === "awaiting_approval" && <span className="actor-bubble approval-bubble">Sua aprovação</span>}{working && <span className="actor-bubble work-bubble">Trabalhando<span aria-hidden="true">…</span></span>}{agent.status === "error" && <span className="actor-bubble error-bubble">Precisa de atenção</span>}<AgentSprite variant={index} /><span className="actor-name"><i className={`office-dot state-${agent.status}`} />{agent.name}</span></button>
                </span>;
              })}
            </div>
          </section>
          <div className="office-scene-caption"><span><span className="office-mini-dot" />{motion === "reduced" ? "Movimento reduzido" : motion === "paused" ? "Animações pausadas" : "Circulação ambiental"}</span><small>Deslize ou use as setas para explorar.</small></div>
          <section className="office-activity" aria-label="Atividade recente do escritório"><div><h2><Activity size={14} aria-hidden="true" />Atividade recente</h2><Link href="/historico">Ver histórico <ArrowUpRight size={13} aria-hidden="true" /></Link></div>
            {!events.length && <p>O escritório está pronto. Envie uma solicitação ao CEO para começar.</p>}
            {events.map(event => <div className="office-activity-line" key={event.id}><time dateTime={new Date(event.created_at * 1000).toISOString()}>{new Date(event.created_at * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</time><span>{event.actor}</span><p>{event.summary}</p></div>)}
          </section>
        </div>
      </div>
    </div>
    {current && <AgentDetail current={current} place={agentPlaces[Math.max(0, agents.indexOf(current)) % agentPlaces.length].room} fresh={fresh} />}
    <div className="office-legend" aria-label="Estados dos agentes">{Object.entries(labels).map(([status, label]) => <span key={status}><i className={`state-${status}`} />{label}</span>)}</div>
    <div className="principle-strip"><ShieldCheck size={19} aria-hidden="true" /><span>A circulação é ambiental. Trabalho nas mesas e contadores exigem execução confirmada e sinal recente do worker. Você continua no controle das aprovações.</span></div>
  </>;
}

function AgentDetail({ current, place, fresh }: { current: OfficeAgent; place: string; fresh: boolean }) {
  return <section className="panel office-detail" aria-labelledby="office-agent-title"><div className="office-detail-summary">
    <div><p className="eyebrow">NA MESA DE {current.name} <span aria-hidden="true">/</span> {place}</p><h2 id="office-agent-title">{current.role}</h2><span className={`office-state state-${current.status}`}>{current.enabled ? labels[current.status] : "Papel preparado"}</span></div>
    <Link href={current.status === "awaiting_approval" ? "/aprovacoes" : "/execucoes"} className="button">{current.status === "awaiting_approval" ? "Revisar aprovação" : "Abrir execuções"}<ArrowUpRight size={16} aria-hidden="true" /></Link></div>
    {!current.enabled && <p>Perfil Hermes ainda não provisionado.</p>}
    {current.status === "working" && (!current.animate || !fresh) && <p className="notice">Execução registrada, sem sinal recente suficiente para animar atividade.</p>}
    {current.run_status === "queued" && <p>Solicitação na fila, aguardando o worker.</p>}
    {current.executor && <p className="field-help">Executor autorizado: {current.executor === "hermes" ? "Hermes" : "Codex"}.</p>}
    {current.error && <p className="notice error">{current.error}</p>}
    <h3>Histórico e resultados</h3>{!current.history.length && <p className="office-empty">Nenhum resultado registrado para este papel.</p>}
    {current.history.map((step, index) => <details key={`${step.run_id}-${index}`} className="office-result"><summary>{step.summary}</summary><small>{dateTime(step.created_at)} · {step.executor}</small><pre>{step.deliverable}</pre></details>)}
    <p className="field-help">Até 10 resultados nas últimas 200 solicitações. Papéis representam etapas do workflow; bots nativos exigem configuração própria.</p>
  </section>;
}
