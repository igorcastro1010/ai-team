"use client";

import { useEffect, useRef, useState } from "react";
import { api, dateTime, type HermesJob, type HermesJobsSnapshot, type HermesJobPause } from "@/lib/api";

const states: Record<HermesJob["state"], string> = {
  scheduled: "Agendado", paused: "Pausado", completed: "Concluído", error: "Erro", unknown: "Desconhecido",
};

export function HermesJobs({ first, reload }: {
  first?: HermesJobsSnapshot; reload: () => Promise<void>;
}) {
  const [observed, setObserved] = useState<{
    snapshot: HermesJobsSnapshot; base: HermesJobsSnapshot | undefined;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<HermesJob | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  // A parent poll/reload replaces first by identity, even within the same second.
  // Local action feedback must never permanently shadow a newer cached observation.
  const snapshot = observed && observed.base === first ? observed.snapshot : first;

  async function inspect() {
    if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api<HermesJobsSnapshot>("/hermes/jobs/inspect", { method: "POST" });
      setObserved({ snapshot: result, base: first });
      await reload();
      setMessage(result.status === "reachable" ? "Inventário consultado. Nenhuma execução iniciada."
        : "Gateway indisponível. Os dados anteriores podem estar desatualizados.");
    } catch {
      setError("Não foi possível consultar os jobs do Hermes.");
    } finally { setBusy(false); }
  }

  async function pause() {
    if (busy || !pending) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api<HermesJobPause>(`/hermes/jobs/${pending.id}/pause`, {
        method: "POST", body: JSON.stringify({ confirm: true }),
      });
      const current = await api<HermesJobsSnapshot>("/hermes/jobs");
      setObserved({ snapshot: current, base: first });
      await reload();
      setPending(null);
      setMessage(result.status === "confirmed" ? "Pausa do agendamento confirmada no Hermes."
        : "Pausa ainda não confirmada. Confira o gateway.");
    } catch {
      setError("Pausa não confirmada. Confira o gateway antes de tentar novamente.");
      // Refresh only the local cache. A failure never retries the remote mutation.
      try {
        setObserved({ snapshot: await api<HermesJobsSnapshot>("/hermes/jobs"), base: first });
      } catch { /* Keep prior state. */ }
      try { await reload(); } catch { /* Keep the explicit uncertainty visible. */ }
    } finally { setBusy(false); }
  }

  return <section className="hermes-executions" aria-labelledby="hermes-jobs-title">
    <h3 id="hermes-jobs-title">Jobs nativos do Hermes</h3>
    <p className="field-help">Consulte os agendamentos e pause um job específico. Pausar impede novos disparos;
      uma execução que já começou pode continuar e consumir uso.</p>
    <button className="button" disabled={busy} onClick={() => void inspect()}>
      {busy && !pending ? "Consultando jobs…" : "Consultar jobs no Hermes"}
    </button>
    {message && <p className="notice" role="status">{message}</p>}
    {error && !pending && <p className="notice error" role="alert">{error}</p>}
    {snapshot?.checked_at && <p className="field-help">Última consulta: {dateTime(snapshot.checked_at)}.</p>}
    {snapshot?.status === "not_configured" && <p>Gateway ainda não configurado.</p>}
    {snapshot?.status === "unavailable" && <p className="notice">Consulta indisponível; dados exibidos podem estar desatualizados.</p>}
    {snapshot?.last_pause?.status === "uncertain" && <p className="notice error" role="status">
      A última solicitação de pausa não foi confirmada. Confira o gateway; nenhuma repetição foi enviada automaticamente.
    </p>}
    {snapshot?.truncated && <p className="notice">Exibindo os primeiros 100 jobs. Consulte os demais diretamente no Hermes.</p>}
    {!snapshot?.items.length && <p>{snapshot?.status === "reachable"
      ? "Nenhum job nativo encontrado, incluindo pausados." : "Nenhum inventário de jobs disponível."}</p>}
    {snapshot?.items.map(job => <article key={job.id} className="hermes-attempt"
      aria-labelledby={`hermes-job-${job.id}`} style={{ overflowWrap: "anywhere" }}>
      <h4 id={`hermes-job-${job.id}`}>{job.name}</h4>
      <p>Estado observado: <strong>{states[job.state]}</strong> · {job.enabled ? "Habilitado" : "Desabilitado"}</p>
      <p className="field-help">ID: <code>{job.id}</code></p>
      <p>Próximo disparo: {job.next_run_at === null ? "não informado" : dateTime(job.next_run_at)}.</p>
      <p className="field-help">Disparos contabilizados: {job.repeat_completed}. Limite: {job.repeat_times === null
        ? "não informado" : job.repeat_times}.</p>
      {job.enabled && job.state === "scheduled" && <button className="button" disabled={busy}
        onClick={() => { setPending(job); setError(""); setMessage(""); }}>Pausar este job</button>}
    </article>)}
    {pending && <PauseConfirmation job={pending} busy={busy} error={error}
      close={() => { if (!busy) { setPending(null); setError(""); } }} confirm={() => void pause()} />}
  </section>;
}

function PauseConfirmation({ job, busy, error, close, confirm }: {
  job: HermesJob; busy: boolean; error: string; close: () => void; confirm: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="creation-dialog" aria-labelledby="hermes-job-pause-title"
    onCancel={event => { if (busy) event.preventDefault(); else close(); }}>
    <h2 id="hermes-job-pause-title">Pausar este agendamento?</h2>
    <p style={{ overflowWrap: "anywhere" }}>A confirmação vale somente para <strong>{job.name}</strong>,
      job <code>{job.id}</code>. Execuções em andamento continuam. A pausa será conferida novamente no gateway.</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    <div className="dialog-actions">
      <button className="button" disabled={busy} onClick={close}>Voltar</button>
      <button className="button primary" disabled={busy} onClick={confirm}>
        {busy ? "Conferindo pausa…" : "Confirmar pausa deste job"}
      </button>
    </div>
  </dialog>;
}
