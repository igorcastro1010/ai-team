"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, dateTime, type HermesAttempt, type HermesPage } from "@/lib/api";

const states: Record<string, string> = {
  not_admitted: "Sem resposta de admissão", started: "Iniciada", queued: "Na fila",
  running: "Em andamento", completed: "Concluída", failed: "Falha", cancelled: "Cancelada",
  interrupted: "Interrompida", unknown: "Incerta", awaiting_approval: "Aguardando aprovação",
  admitting: "Admissão registrada", succeeded: "Resultado validado", uncertain: "Resultado incerto",
  timed_out: "Tempo esgotado", blocked: "Bloqueada",
};
const roles = ["CEO", "DEV", "DESIGNER", "QA", "CEO"];
const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);
const number = (value: number | null) => value === null ? "não informado" : value.toLocaleString("pt-BR");

export function HermesExecutions({ first, reload }: { first?: HermesPage; reload: () => Promise<void> }) {
  const [older, setOlder] = useState<HermesAttempt[]>([]);
  const [page, setPage] = useState<HermesPage | null>(null);
  const [snapshot, setSnapshot] = useState<HermesPage | null>(null);
  const [changed, setChanged] = useState<Record<string, HermesAttempt>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<HermesAttempt | null>(null);
  const latestIds = new Set((first?.items || []).map(row => row.id));
  const head = snapshot?.items || first?.items || [];
  const headIds = new Set(head.map(row => row.id));
  const current = new Map((first?.items || []).map(row => [row.id, row]));
  const entries = [...head, ...new Map(older.filter(row => !headIds.has(row.id))
    .map(row => [row.id, row])).values()]
    .map(row => latestIds.has(row.id) ? current.get(row.id)! : changed[row.id] || row);
  const cursor = page ? page.next_cursor : first?.next_cursor;

  async function action(row: HermesAttempt, operation: "refresh" | "stop") {
    if (busy) return;
    setBusy(row.id); setError(""); setMessage("");
    try {
      const updated = await api<HermesAttempt>(`/hermes/executions/${row.id}/${operation}`, {
        method: "POST", body: operation === "stop" ? JSON.stringify({ confirm: true }) : undefined,
      });
      setChanged(previous => ({ ...previous, [updated.id]: updated }));
      await reload(); setPending(null);
      setMessage(operation === "refresh" ? "Estado remoto consultado. Nenhuma nova execução foi criada."
        : "Solicitação de interrupção enviada. Confira a confirmação observada abaixo.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível consultar o Hermes.");
      await reload();
    } finally { setBusy(""); }
  }
  async function more() {
    if (!cursor || busy) return;
    setBusy("page"); setError("");
    try {
      const result = await api<HermesPage>(`/hermes/executions?before=${encodeURIComponent(cursor)}`);
      setSnapshot(previous => previous || first || { items: [], next_cursor: null });
      setOlder(previous => [...previous, ...result.items]); setPage(result);
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível carregar o histórico."); }
    finally { setBusy(""); }
  }
  return <div className="hermes-executions">
    <h3>Execuções remotas do Hermes</h3>
    <p className="field-help">Histórico persistente das tentativas. Consultar estado não inicia inferência nem repete uma solicitação.</p>
    {message && <p role="status" className="notice success">{message}</p>}
    {error && !pending && <p role="alert" className="notice error">{error}</p>}
    {snapshot && <p className="field-help">Histórico paginado mantido estável. Novas tentativas aparecem ao voltar às mais recentes.</p>}
    {snapshot && <button className="button" disabled={!!busy} onClick={() => {
      setSnapshot(null); setOlder([]); setPage(null); setChanged({});
    }}>Voltar às tentativas mais recentes</button>}
    {!entries.length && <p>Nenhuma tentativa remota registrada.</p>}
    {entries.map(row => <article key={row.id} className="hermes-attempt" aria-labelledby={`attempt-${row.id}`}>
      <h4 id={`attempt-${row.id}`}>Etapa {row.stage + 1} · {roles[row.stage] || "Agente"}</h4>
      <p>AI TEAM: <strong>{states[row.local_status] || row.local_status}</strong> · Hermes: <strong>{states[row.remote_status] || "Estado desconhecido"}</strong></p>
      <p className="field-help">{states[row.bridge_status] || "Sem resultado validado"} · {dateTime(row.updated_at)}</p>
      {row.remote_id ? <p className="field-help">ID no Hermes: <code>{row.remote_id}</code></p>
        : <p className="notice">A resposta de admissão não foi confirmada. Confira o gateway antes de enviar outro pedido.</p>}
      <p>Tokens de entrada: {number(row.input_tokens)} · saída: {number(row.output_tokens)}.</p>
      {row.stop_status === "requested" && <p className="notice">Interrupção solicitada; aguardando confirmação no Hermes.</p>}
      {row.stop_status === "uncertain" && <p className="notice error">Interrupção não confirmada. A execução remota pode continuar e consumir uso.</p>}
      {row.stop_status === "confirmed" && <p className="notice success">Interrupção confirmada pelo Hermes.</p>}
      {row.stop_status === "already_finished" && <p>A execução remota já havia terminado; não foi confirmada como cancelada.</p>}
      <div className="hermes-actions">
        {row.remote_id && <button className="button" disabled={!!busy} onClick={() => void action(row, "refresh")}>Consultar estado remoto</button>}
        {!!row.remote_id && !terminal.has(row.remote_status) && (["cancelled", "failed"].includes(row.local_status)
          ? <button className="button" disabled={!!busy} onClick={() => { setError(""); setPending(row); }}>Interromper no Hermes</button>
          : <Link className="button" href="/execucoes">Cancelar primeiro no AI TEAM</Link>)}
      </div>
    </article>)}
    {cursor && <button className="button" disabled={!!busy} onClick={() => void more()}>Carregar tentativas anteriores</button>}
    {pending && <StopConfirmation attempt={pending} busy={!!busy} error={error}
      close={() => { if (!busy) { setPending(null); setError(""); } }} confirm={() => void action(pending, "stop")} />}
  </div>;
}

function StopConfirmation({ attempt, busy, error, close, confirm }: {
  attempt: HermesAttempt; busy: boolean; error: string; close: () => void; confirm: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="creation-dialog" aria-labelledby="hermes-stop-title"
    onCancel={event => { if (busy) event.preventDefault(); else close(); }}>
    <h2 id="hermes-stop-title">Interromper esta execução no Hermes?</h2>
    <p>A decisão vale somente para a etapa {attempt.stage + 1}, execução <code>{attempt.remote_id}</code>.
      O resultado continuará incerto até a confirmação do gateway. Uma chamada já enviada pode consumir uso.</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    <div className="dialog-actions"><button className="button" disabled={busy} onClick={close}>Voltar</button>
      <button className="button primary" disabled={busy} onClick={confirm}>{busy ? "Solicitando…" : "Confirmar interrupção remota"}</button></div>
  </dialog>;
}
