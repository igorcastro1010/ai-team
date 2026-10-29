"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, dateTime, modes } from "@/lib/api";

type Report = {
  generated_at: number;
  summary: {
    projects: number; tasks: Record<string, number>; runs: Record<string, number>;
    github: Record<string, number>; schedules: Record<string, number>; occurrences: number;
    usage: {calls: number; input_tokens: number; output_tokens: number; cost_usd: null};
  };
  runs: {id: string; project_id: string; status: string; mode: string; calls: number;
    input_tokens: number; output_tokens: number; created_at: number;
    schedule_id: string | null; occurrence: number | null}[];
  next_cursor: {before_created_at: number; before_id: string} | null;
  note: string;
};
const labels: Record<string,string> = {
  queued:"Na fila", running:"Executando", completed:"Concluída", cancelled:"Cancelada",
  awaiting_approval:"Aguarda aprovação", failed:"Falhou", blocked:"Bloqueada",
};
const sum = (values: Record<string,number>) => Object.values(values).reduce((a,b) => a+b,0);

export function ReportsPanel() {
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [paged, setPaged] = useState(false);
  const lock = useRef(false);
  const load = useCallback(async (query = "") => {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try { setReport(await api<Report>(`/reports${query}`)); setPaged(!!query); }
    catch (err) { setError(err instanceof Error ? err.message : "Relatório indisponível."); }
    finally { lock.current = false; setBusy(false); }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => {void load();},0);
    return () => window.clearTimeout(timer);
  }, [load]);
  function download() {
    if (!report) return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:"application/json"}));
    const anchor=document.createElement("a");
    anchor.href=url; anchor.download="ai-team-relatorio.json"; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  return <>
    <div className="section-toolbar"><span>Totais de todo o banco · histórico em páginas de 50</span><button className="button secondary" disabled={busy} onClick={() => void load()}>{busy ? "Consultando…" : "Atualizar relatório"}</button></div>
    {error && <p role="alert" className="notice error">{error}</p>}
    {!report ? <p role="status">{busy ? "Preparando relatório…" : "Use Atualizar relatório para consultar os dados."}</p> : <>
      <p className="field-help">Consultado em {dateTime(report.generated_at)}. {sum(report.summary.runs)} execuções registradas</p>
      <div className="report-grid">
        <section className="panel report-card"><p className="eyebrow">ENTREGAS</p><strong>{report.summary.tasks.done || 0}<span> / {sum(report.summary.tasks)}</span></strong><h2>Tarefas concluídas</h2><p>{report.summary.projects} projetos. Status de tarefas atualizado pelo proprietário.</p></section>
        <section className="panel report-card"><p className="eyebrow">USO DO CODEX</p><strong>{report.summary.usage.calls}<span> chamadas</span></strong><h2>{(report.summary.usage.input_tokens + report.summary.usage.output_tokens).toLocaleString("pt-BR")} tokens registrados</h2><p>Chamadas reservadas pelo worker; tokens reportados nas etapas concluídas. Falhas podem ter consumo não reportado. Custo monetário indisponível.</p></section>
        <section className="panel report-card"><p className="eyebrow">RECORRÊNCIA</p><strong>{report.summary.occurrences}</strong><h2>Ocorrências enfileiradas</h2><p>{report.summary.schedules.active || 0} agendas ativas. {report.summary.runs.completed || 0} execuções concluídas. {sum(report.summary.github)} propostas GitHub registradas.</p></section>
      </div>
      <div className="section-toolbar run-section-title"><h2>Histórico de execuções</h2><button className="button" onClick={download} disabled={busy}>Exportar página JSON</button></div>
      <div className="run-list">{report.runs.map(run => <article className="panel run-card" key={run.id}>
        <div className="run-head"><h3>{labels[run.status] || run.status}</h3><span className="tag">{modes[run.mode] || run.mode}</span></div><p className="artifact-content">{run.id}</p>
        <p>{dateTime(run.created_at)} · {run.calls} chamadas · {(run.input_tokens + run.output_tokens).toLocaleString("pt-BR")} tokens</p>
        {run.schedule_id && <p className="field-help artifact-content">Ocorrência {run.occurrence} · agenda {run.schedule_id}</p>}
      </article>)}</div>
      {!report.runs.length && <div className="empty-state"><h3>Nenhuma execução nesta página.</h3></div>}
      <div className="section-toolbar run-section-title"><button className="button secondary" disabled={busy || !paged} onClick={() => void load()}>Voltar ao início</button><button className="button secondary" disabled={busy || !report.next_cursor} onClick={() => {if(report.next_cursor) void load(`?${new URLSearchParams({before_created_at:String(report.next_cursor.before_created_at),before_id:report.next_cursor.before_id})}`);}}>Página seguinte</button></div>
      <p className="field-help">A exportação contém os totais e esta página de metadados. Prompts, respostas, credenciais e sessões não são exportados. As próximas consultas podem refletir novas execuções.</p>
    </>}
  </>;
}
