"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, dateTime, modes, type Schedule, type Workspace } from "@/lib/api";

const labels: Record<string, string> = {
  active: "Ativo", cancelled: "Cancelado", completed: "Limite atingido", expired: "Expirado",
};

export function SchedulePanel({ data, reload }: { data: Workspace; reload: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selected, setSelected] = useState<Schedule | null>(null);
  const lock = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (selected) dialog.current?.showModal();
    else { dialog.current?.close(); returnFocus.current?.focus(); }
  }, [selected]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const startsAt = Date.parse(`${values.get("starts_at")}:00-03:00`) / 1000;
    if (!Number.isFinite(startsAt)) { setError("Informe um horário válido em Fortaleza."); return; }
    lock.current = true; setBusy(true); setError(""); setSuccess("");
    try {
      await api("/schedules", {method:"POST", body:JSON.stringify({
        project_id:values.get("project_id"), prompt:values.get("prompt"), mode:values.get("mode"),
        starts_at:startsAt, interval_seconds:Number(values.get("interval_seconds")),
        max_runs:Number(values.get("max_runs")), consent:values.get("consent") === "on",
      })});
      form.reset(); setSuccess("Agendamento autorizado. Acompanhe as ocorrências abaixo.");
      await reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível autorizar."); }
    finally { lock.current = false; setBusy(false); }
  }

  async function cancel() {
    if (!selected || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      await api(`/schedules/${selected.id}/cancel`, {method:"POST"});
      setSelected(null); setSuccess("Recorrência cancelada. Execuções já criadas foram preservadas.");
      await reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível cancelar."); }
    finally { lock.current = false; setBusy(false); }
  }

  return <>
    <div className="principle-strip"><span>O Windows, o scheduler e o worker precisam permanecer ativos. Após uma parada, apenas uma ocorrência atrasada entra na fila. Sem sobreposição por agendamento.</span></div>
    {error && !selected && <p className="notice error" role="alert">{error}</p>}
    {success && <p className="notice success" role="status">{success}</p>}
    <section className="panel ceo-compose" aria-label="Novo agendamento">
      <div className="panel-title"><h2>Defina a próxima rotina</h2><span className="tag">SOMENTE TEXTO</span></div>
      {data.projects.length ? <form className="ceo-form" onSubmit={submit}>
        <label htmlFor="schedule-project">Projeto do agendamento</label>
        <select id="schedule-project" name="project_id" required>{data.projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
        <label htmlFor="schedule-prompt">Solicitação recorrente</label>
        <textarea id="schedule-prompt" name="prompt" minLength={5} maxLength={5000} required rows={4} />
        <div className="schedule-fields">
          <div><label htmlFor="schedule-start">Primeiro horário</label><input id="schedule-start" name="starts_at" type="datetime-local" required /><p className="field-help">Fortaleza (UTC−3), nos próximos sete dias.</p></div>
          <div><label htmlFor="schedule-interval">Intervalo</label><select id="schedule-interval" name="interval_seconds" defaultValue="86400"><option value="3600">A cada hora</option><option value="86400">A cada 24 horas</option><option value="604800">A cada 7 dias</option></select></div>
          <div><label htmlFor="schedule-count">Número de ocorrências</label><input id="schedule-count" type="number" name="max_runs" min={1} max={5} defaultValue={2} required /></div>
          <div><label htmlFor="schedule-mode">Modo das ocorrências</label><select id="schedule-mode" name="mode" defaultValue="supervised">{Object.entries(modes).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
        </div>
        <p className="field-help">Manual: aprovações entre etapas. Supervisionado: aprovação após o plano CEO. Automático: cinco etapas textuais autorizadas por ocorrência. A autorização expira em 30 dias; ocorrências já criadas mantêm sua autorização.</p>
        <label className="consent-field"><input type="checkbox" name="consent" required /><span>Autorizo esta recorrência com o projeto, solicitação, modo e limites acima. Cada ocorrência pode consumir até cinco chamadas Codex, com 120 segundos por chamada e limiar de 50 mil tokens antes de reservar outra chamada. O último retorno pode exceder esse limiar; não há teto monetário. Apenas planos e pareceres, sem ações GitHub ou publicação.</span></label>
        <div className="compose-actions"><small>Consumo vinculado à sua conta Codex.</small><button className="button primary" disabled={busy}>{busy ? "Salvando…" : "Autorizar agendamento"}</button></div>
      </form> : <div className="empty-state"><p>Crie um projeto antes de autorizar uma recorrência.</p><Link className="button" href="/projetos">Abrir projetos</Link></div>}
    </section>
    <div className="section-toolbar run-section-title"><h2>Rotinas autorizadas</h2><Link href="/execucoes" className="text-link">Acompanhar execuções</Link></div>
    <div className="run-list">{data.schedules.map(schedule => <article className="panel run-card" key={schedule.id}>
      <div className="run-head"><h3>{data.projects.find(project => project.id === schedule.project_id)?.name || "Projeto"}</h3><span className="tag">{labels[schedule.status] || schedule.status}</span></div>
      <p className="artifact-content">{schedule.prompt}</p><p>{schedule.emitted} de {schedule.max_runs} ocorrências · {modes[schedule.mode]}</p>
      <p className="field-help">Intervalo de {schedule.interval_seconds / 3600} horas. Validade: {dateTime(schedule.expires_at)}.</p>
      {schedule.status === "active" && <><p>Próximo horário: {dateTime(schedule.next_run_at)}. Aguarda a ocorrência anterior terminar.</p><button className="button secondary" disabled={busy} onClick={event => {returnFocus.current=event.currentTarget; setError(""); setSelected(schedule);}}>Cancelar recorrência</button></>}
    </article>)}</div>
    {!data.schedules.length && <div className="empty-state"><h3>Nenhuma rotina autorizada.</h3><p>Escolha o objetivo e a frequência no formulário acima.</p></div>}
    <dialog className="creation-dialog" ref={dialog} aria-labelledby="cancel-schedule-title" onCancel={event => {event.preventDefault(); if (!busy) setSelected(null);}}>
      <h2 id="cancel-schedule-title">Cancelar recorrência?</h2><p>Novas ocorrências serão impedidas. Execuções já criadas continuam disponíveis em Execuções e podem ser canceladas separadamente.</p>
      {error && selected && <p className="notice error" role="alert">{error}</p>}
      <div className="dialog-actions"><button className="button secondary" disabled={busy} onClick={() => setSelected(null)}>Manter agendamento</button><button className="button primary" disabled={busy} onClick={() => void cancel()}>Confirmar cancelamento</button></div>
    </dialog>
  </>;
}
