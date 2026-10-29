"use client";
import { useRef, useState } from "react";
import { api, dateTime, type VercelObservation, type Workspace } from "@/lib/api";

const labels: Record<string, string> = { QUEUED: "Na fila", INITIALIZING: "Inicializando", BUILDING: "Construindo", READY: "Pronto", ERROR: "Falhou", CANCELED: "Cancelado" };

export function VercelPanel({ data, reload }: { data: Workspace; reload: () => Promise<void> }) {
  const [observed, setObserved] = useState<VercelObservation | null>(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState("");
  const connection = observed || data.vercel?.connection;
  async function inspect() {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      setObserved(await api<VercelObservation>("/vercel/inspect", { method: "POST" }));
      await reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível consultar a Vercel."); }
    finally { lock.current = false; setBusy(false); }
  }
  return <section id="vercel-console" className="github-section" aria-label="Consultas Vercel">
    <div className="panel run-card"><div className="run-head"><h2>Vercel, somente consulta.</h2><button className="button secondary" disabled={busy} onClick={() => void inspect()}>{busy ? "Consultando…" : "Consultar Vercel"}</button></div>
      <p>Consulte o projeto ai-team e seus últimos deploys com a credencial própria do executor. Publicação, domínio e variáveis de ambiente não são alterados.</p>
      {error && <p className="notice error" role="alert">{error}</p>}
      {!connection ? <p className="field-help">Nenhuma consulta registrada. Configure a credencial no cofre do executor e use o botão acima.</p> : <>
        <p className="field-help">Última consulta: {dateTime(connection.verified_at)}. Este resultado não representa monitoramento contínuo.</p>
        {connection.project ? <><h3>Projeto {connection.project.name}</h3>
          {connection.deployments.length ? <div className="run-list">{connection.deployments.map((deployment, index) => <article className="run-artifact artifact-content" key={deployment.id || index}><strong>{labels[deployment.state || ""] || "Estado não reconhecido"}</strong>{deployment.created_at && <span> · {dateTime(deployment.created_at / 1000)}</span>}<p>{deployment.id || "Identificação não informada"}</p></article>)}</div> : <p>Sem deploys neste projeto. Nenhuma publicação foi realizada pela plataforma.</p>}
        </> : <p>Nenhum projeto ai-team foi encontrado no escopo dessa credencial. A consulta não cria projetos automaticamente.</p>}
      </>}
    </div>
  </section>;
}
