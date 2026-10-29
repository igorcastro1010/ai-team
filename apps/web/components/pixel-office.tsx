"use client";
import Link from "next/link";
import { useEffect, useState, type CSSProperties } from "react";
import { ArrowUpRight, Radio, ShieldCheck } from "lucide-react";
import { dateTime, type Workspace } from "@/lib/api";
import "@/styles/office.css";

const labels = {
  available: "Disponível", working: "Trabalhando", awaiting_approval: "Aguardando aprovação",
  completed: "Concluído", error: "Erro",
};
const colors = ["#b6ec81", "#83c6ff", "#dbabff", "#ffd185", "#81d8c8", "#ffa9be", "#b8bdff"];

function Workstation({ variant }: { variant: number }) {
  return <svg viewBox="0 0 128 110" aria-hidden="true" className="pixel-desk" shapeRendering="crispEdges">
    <ellipse cx="64" cy="98" rx="46" ry="7" fill="#101e2d" />
    <path d="M21 58h86v9H21zM26 67h7v28h-7zM95 67h7v28h-7z" fill="#a17e59" />
    <path d="M21 58h86v4H21z" fill="#d6b98d" />
    <path d="M40 19h49v32H40z" fill="#0a1423" />
    <path d="M44 23h41v23H44z" fill="#213c50" />
    <path className="pixel-screen" d="M49 28h20v3H49zM49 35h29v2H49zM49 40h13v2H49z" fill="currentColor" />
    <path d="M60 51h9v5H60zM52 55h25v3H52z" fill="#657e8e" />
    <path d="M87 52h8v7h-8zM95 53h3v4h-3z" fill="#e8d8b4" />
    <path d="M35 56h27v4H35z" fill="#546f7e" />
    <path d="M52 71h26v28H52zM49 95h32v5H49z" fill="#22384e" />
    <g className="pixel-person">
      <path d="M52 44h24v7H52zM48 51h32v18H48z" fill="currentColor" />
      <path d="M55 34h18v15H55zM52 37h4v8h-4zM72 37h4v8h-4z" fill={variant % 3 === 0 ? "#c88b64" : "#f0bb92"} />
      <path d={variant % 2 === 0 ? "M53 30h22v9H53zM51 34h5v10h-5z" : "M53 30h21v8H53zM70 37h6v11h-6z"} fill={variant % 3 === 1 ? "#ddd1a4" : "#312c37"} />
      <path d="M56 40h3v3h-3zM67 40h3v3h-3z" fill="#172133" />
      {variant === 0 && <path d="M52 39h11v6H52zM65 39h11v6H65zM63 40h2v2h-2z" fill="#647e8c" />}
      <path className="pixel-hands" d="M44 58h8v7h-8zM76 58h8v7h-8z" fill="#f0bb92" />
      <path d="M55 69h8v15h-8zM67 69h8v15h-8z" fill="#13283b" />
      <path d="M53 82h11v5H53zM67 82h11v5H67z" fill="#0d1927" />
    </g>
  </svg>;
}

export function PixelOffice({ data, connected }: { data: Workspace; connected: boolean }) {
  const [selected, setSelected] = useState("CEO");
  const [now, setNow] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const fresh = connected && now > 0 && Math.abs(now - data.office_observed_at) < 15;
  const agents = data.office || [];
  const current = agents.find(agent => agent.id === selected) || agents[0];
  const active = fresh ? agents.filter(agent => agent.animate).length : 0;
  return <>
    <div className="office-topline"><div><span className="office-live"><Radio size={15} aria-hidden="true" />{fresh ? "Eventos do workspace" : "Aguardando atualização"}</span><p>Estado persistido, atualizado a cada 5 segundos.</p></div><span className="tag">{active} EM ATIVIDADE CONFIRMADA</span></div>
    <div className="office-layout">
      <section className="pixel-room" aria-label="Sala do escritório virtual">
        <div className="pixel-wall" aria-hidden="true"><div className="pixel-window"><span /><span /><span /><span /></div><div className="pixel-sign">ai<span>TEAM</span><small>IDEIAS EM MOVIMENTO</small></div><div className="pixel-clock"><i /></div></div>
        <div className="office-room-label" aria-hidden="true">ESTÚDIO 01 <span>•</span> FORTALEZA / BR</div>
        <div className="pixel-floor">
          {agents.map((agent, index) => <button key={agent.id} type="button"
            className={`pixel-station ${index === 0 ? "station-ceo" : ""} ${agent.animate && fresh ? "is-working" : ""} ${selected === agent.id ? "is-selected" : ""}`}
            style={{ "--agent-color": colors[index % colors.length] } as CSSProperties}
            onClick={() => setSelected(agent.id)} aria-pressed={selected === agent.id}
            aria-label={`Abrir detalhes de ${agent.name}: ${agent.enabled ? labels[agent.status] : "Papel preparado"}`}>
            <span className={`station-indicator state-${agent.status}`} aria-hidden="true" />
            <Workstation variant={index} />
            <strong>{agent.name}</strong><span className="station-status">{agent.enabled ? labels[agent.status] : "Papel preparado"}</span>
          </button>)}
        </div>
        <div className="pixel-room-footer"><span className="pixel-plant" aria-hidden="true" /><p>Um espaço para cada especialidade.<br /><strong>Você continua no comando.</strong></p><span className="pixel-plant" aria-hidden="true" /></div>
      </section>
      {current && <section className="panel office-detail" aria-labelledby="office-agent-title">
        <p className="eyebrow">NA MESA DE {current.name}</p>
        <h2 id="office-agent-title">{current.role}</h2>
        <span className={`office-state state-${current.status}`}>{current.enabled ? labels[current.status] : "Papel preparado"}</span>
        {!current.enabled && <p>Perfil Hermes ainda não provisionado.</p>}
        {current.status === "working" && (!current.animate || !fresh) && <p className="notice">Execução registrada, sem sinal recente suficiente para animar atividade.</p>}
        {current.run_status === "queued" && <p>Solicitação na fila, aguardando o worker.</p>}
        {current.executor && <p className="field-help">Executor autorizado: {current.executor === "hermes" ? "Hermes" : "Codex"}.</p>}
        {current.error && <p className="notice error">{current.error}</p>}
        <h3>Histórico e resultados</h3>
        {!current.history.length && <p className="office-empty">Nenhum resultado registrado para este papel.</p>}
        {current.history.map((step, index) => <details key={`${step.run_id}-${index}`} className="office-result"><summary>{step.summary}</summary><small>{dateTime(step.created_at)} · {step.executor}</small><pre>{step.deliverable}</pre></details>)}
        <p className="field-help">Até 10 resultados nas últimas 200 solicitações. Papéis representam etapas do workflow; bots nativos exigem configuração própria.</p>
        <Link href={current.status === "awaiting_approval" ? "/aprovacoes" : "/execucoes"} className="button">{current.status === "awaiting_approval" ? "Revisar aprovação" : "Abrir execuções"}<ArrowUpRight size={16} aria-hidden="true" /></Link>
      </section>}
    </div>
    <div className="office-legend" aria-label="Estados dos agentes">{Object.entries(labels).map(([status, label]) => <span key={status}><i className={`state-${status}`} />{label}</span>)}</div>
    <div className="principle-strip"><ShieldCheck size={19} aria-hidden="true" /><span>As animações exigem execução ativa, lease válida e sinal recente do worker. Aprovações, merges e publicação continuam sob seu controle.</span></div>
  </>;
}
