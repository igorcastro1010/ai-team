"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowUpRight, X } from "lucide-react";
import { api, type Project } from "@/lib/api";

export function CreationDialog({ kind, projects, close, created }: {
  kind: "project" | "task"; projects: Project[]; close: () => void; created: () => Promise<void>;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { ref.current?.showModal(); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true); setError("");
    try {
      await api(kind === "project" ? "/projects" : "/tasks", { method: "POST", body: JSON.stringify(data) });
      await created(); close();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível salvar."); }
    finally { setBusy(false); }
  }
  return <dialog ref={ref} className="creation-dialog" aria-labelledby="dialog-title" onCancel={event => {
    if (busy) event.preventDefault(); else close();
  }}>
    <div className="dialog-head"><p className="eyebrow">NOVO PONTO DE PARTIDA</p><button className="icon-button" type="button" onClick={close} disabled={busy} aria-label="Fechar formulário"><X size={20} aria-hidden="true" /></button></div>
    <h2 id="dialog-title">{kind === "project" ? "O que vamos construir?" : "Um passo de cada vez."}</h2>
    <p>{kind === "project" ? "Dê um nome e uma direção ao próximo projeto." : "Defina a entrega e quem deve acompanhá-la."}</p>
    <form onSubmit={submit}>
      {kind === "project" ? <>
        <label htmlFor="project-name">Nome do projeto</label><input id="project-name" name="name" maxLength={120} required autoFocus />
        <label htmlFor="project-mode">Modo de autonomia</label><select id="project-mode" name="mode" defaultValue="supervised"><option value="manual">Manual</option><option value="supervised">Supervisionado</option><option value="automatic">Automático</option></select>
        <p className="field-help">Modo registrado como preferência. Execução automática será habilitada após validar o executor e as permissões.</p>
      </> : <>
        <label htmlFor="task-project">Projeto</label><select id="task-project" name="project_id" required>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
        <label htmlFor="task-title">Título da tarefa</label><input id="task-title" name="title" maxLength={200} required autoFocus />
        <label htmlFor="task-agent">Agente responsável</label><select id="task-agent" name="agent" defaultValue="DEV">{["CEO", "DEV", "DESIGNER", "QA"].map(agent => <option key={agent}>{agent}</option>)}</select>
      </>}
      <label htmlFor="description">Descrição</label><textarea id="description" name="description" rows={3} maxLength={5000} />
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button" onClick={close} disabled={busy}>Cancelar</button><button className="button primary" disabled={busy}>{busy ? "Salvando…" : kind === "project" ? "Criar projeto" : "Criar tarefa"}<ArrowUpRight size={17} aria-hidden="true" /></button></div>
    </form>
  </dialog>;
}
