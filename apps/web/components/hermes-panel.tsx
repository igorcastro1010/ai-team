"use client";
import { useState } from "react";
import { api, dateTime, type Workspace } from "@/lib/api";
import { HermesExecutions } from "./hermes-executions";

const labels = {
  not_configured: "Não configurado", unavailable: "Indisponível",
  unsafe_configuration: "Bloqueado: ferramentas habilitadas", reachable: "API privada alcançável",
};

export function HermesPanel({ data, reload }: { data: Workspace; reload: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const observation = data.hermes?.connection;
  async function inspect() {
    setBusy(true); setMessage(""); setError("");
    try {
      await api("/hermes/inspect", { method: "POST" });
      await reload(); setMessage("Diagnóstico registrado. Nenhuma inferência foi solicitada.");
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível verificar o Hermes."); }
    finally { setBusy(false); }
  }
  return <section className="panel hermes-panel" aria-labelledby="hermes-title">
    <div className="panel-title"><h2 id="hermes-title">Hermes Agent</h2><span className="tag">GATEWAY PRIVADO</span></div>
    <p>Executor adicional com consentimento por solicitação. Nesta etapa, produz planos e pareceres sem ferramentas.</p>
    <p><strong>{observation ? labels[observation.status] : "Sem diagnóstico registrado"}</strong></p>
    <p>Inferência ainda não homologada.</p>
    {observation?.checked_at && <p className="field-help">Última inspeção: {dateTime(observation.checked_at)}. A disponibilidade pode mudar.</p>}
    <p className="field-help">Configure modelo e credenciais no servidor conforme docs/hermes-setup.md. Telegram e delegação nativa exigem homologação própria.</p>
    {message && <p role="status" className="notice success">{message}</p>}
    {error && <p role="alert" className="notice error">{error}</p>}
    <button className="button" disabled={busy} onClick={() => void inspect()}>{busy ? "Verificando…" : "Verificar Hermes"}</button>
    <HermesExecutions first={data.hermes?.executions} reload={reload} />
  </section>;
}
