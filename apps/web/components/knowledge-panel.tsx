"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, dateTime, type Project } from "@/lib/api";
import "@/styles/knowledge.css";

type Note = { id: string; title: string; content: string; source: string; version: number; digest: string; quarantined: boolean; updated_at: number };
type Revision = { version: number; content: string; created_at: number };
type ExportReview = { id: string; filename: string; exists: boolean; content: string; digest: string | null; note_content: string; note_version: number };
type Issue = { id: string; request_id: string; agent: string; priority: string; status: string; remote_state: string; action: { id: string; status: string; digest: string; payload: { title: string; body: string }; result: { url?: string } } };
type Preview = { estimated_before: number; estimated_after: number; cache_hit: boolean; mandatory_over_budget: boolean; context: Record<string, unknown>; discarded_optional?: number; selected_memories?: string[] };
type Budget = { scope: string; scope_id: string; limit: number; used: number; reserved: number; over_budget: boolean };
type Summary = { usage_by_agent_task?: {agent:string;task_id:string;input_tokens:number;output_tokens:number}[]; budgets: Budget[]; measured_input_tokens: number; measured_output_tokens: number; in_flight: number; cache_hits?: number; cache_misses?: number; records: Omit<Preview, "context">[] };
type Graph = { nodes: { id: string; label: string; kind: string; provenance: string }[]; links: { source: string; target: string; relation: string }[]; truncated: boolean };

export function KnowledgePanel({ projects }: { projects: Project[] }) {
  const [selected, setSelected] = useState("");
  const project = selected || projects[0]?.id || "";
  return <section className="knowledge-panel" aria-label="Conhecimento e consumo">
    <div className="knowledge-toolbar"><label>Projeto do conhecimento<select value={project} onChange={event => setSelected(event.target.value)}>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><p>Memória compartilhada no projeto.<br />Permissões e aprovações continuam com você.</p></div>
    {project ? <ProjectKnowledge key={project} project={project} /> : <p>Crie um projeto para organizar o conhecimento do time.</p>}
  </section>;
}

function ProjectKnowledge({ project }: { project: string }) {
  const [tab, setTab] = useState("Memórias");
  const [notes, setNotes] = useState<Note[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [vault, setVault] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState<Note | null>(null);
  const [history, setHistory] = useState<Revision[]>([]);
  const [query, setQuery] = useState("");
  const [issueTitle, setIssueTitle] = useState("");
  const [issueBody, setIssueBody] = useState("");
  const [issueAgent, setIssueAgent] = useState("DEV");
  const [issuePriority, setIssuePriority] = useState("medium");
  const [issueFilter, setIssueFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [requestId, setRequestId] = useState("");
  const [request, setRequest] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [limit, setLimit] = useState("500000");
  const [scope, setScope] = useState("project");
  const [scopeId, setScopeId] = useState("");
  const generation = useRef(0);
  const [exportReview, setExportReview] = useState<ExportReview | null>(null);
  const reviewRegion = useRef<HTMLElement>(null);
  useEffect(() => { if (exportReview) reviewRegion.current?.focus(); }, [exportReview]);

  async function refresh(signal?: AbortSignal) {
    const current = ++generation.current;
    const [memory, issueData, usage, relations] = await Promise.all([
      api<{ items: Note[]; vault_configured: boolean }>(`/memory/${project}`, { signal }),
      api<{ issues: Issue[] }>(`/issues?project_id=${project}`, { signal }),
      api<Summary>(`/projects/${project}/optimizer`, { signal }),
      api<Graph>(`/knowledge/${project}/graph`, { signal }),
    ]);
    if (signal?.aborted || current !== generation.current) return false;
    setNotes(memory.items); setVault(memory.vault_configured); setIssues(issueData.issues); setSummary(usage); setGraph(relations);
    return true;
  }
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => { const pendingGeneration = generation.current + 1; void refresh(controller.signal).then(updated => { if (updated && !controller.signal.aborted) setStatus("Conhecimento atualizado"); }).catch(err => { if (!controller.signal.aborted && generation.current === pendingGeneration) setError(err instanceof Error ? err.message : "Falha ao carregar"); }); }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
    // The parent remounts this component on project changes, clearing all scoped state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project]);

  async function perform(action: () => Promise<void>, message: string, reload = true) {
    if (busy) return;
    generation.current += 1;
    setBusy(true); setError(""); setStatus("");
    try { await action(); if (reload) await refresh(); setStatus(message); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível concluir."); }
    finally { setBusy(false); }
  }

  return <>
    <div className="knowledge-tabs" aria-label="Seções do conhecimento">{["Memórias", "Issues", "Otimizador", "Relações"].map(item => <button type="button" key={item} className={tab === item ? "button primary" : "button"} aria-pressed={tab === item} onClick={() => setTab(item)}>{item}</button>)}<button className="button" disabled={busy} onClick={() => void perform(async () => {}, "Conhecimento atualizado")}>Atualizar</button></div>
    <p role="status" className="knowledge-status">{status}</p>{error && <p role="alert" className="knowledge-error">{error}</p>}
    {exportReview && <section ref={reviewRegion} tabIndex={-1} className="panel knowledge-note" role="region" aria-label="Revisão da exportação Markdown">
      <h2>Revise antes de exportar</h2><p>{exportReview.filename} · Versão {exportReview.note_version}</p>
      <h3>Arquivo atual no vault</h3><pre className="knowledge-prose">{exportReview.exists ? exportReview.content : "Arquivo novo"}</pre>
      <h3>Conteúdo que será gravado</h3><pre className="knowledge-prose">{exportReview.note_content}</pre>
      <small>Digest revisado: {exportReview.digest || "arquivo ainda não existe"}</small>
      <p>Conclua edições no Obsidian antes de confirmar. Se o arquivo mudar, revise novamente.</p>
      <div className="knowledge-actions"><button className="button primary" disabled={busy} onClick={() => void perform(async () => { await api(`/memory/${project}/${exportReview.id}/export`, { method: "POST", body: JSON.stringify({ expected_digest: exportReview.digest, expected_version: exportReview.note_version }) }); setExportReview(null); }, "Markdown exportado")}>Confirmar exportação revisada</button><button className="button" disabled={busy} onClick={() => setExportReview(null)}>Cancelar exportação</button></div>
    </section>}
    {tab === "Memórias" && <div className="knowledge-columns">
      <form className="panel knowledge-form" onSubmit={event => { event.preventDefault(); void perform(async () => { await api(`/memory/${project}${editing ? `/${editing.id}` : ""}`, { method: editing ? "PUT" : "POST", body: JSON.stringify({ title, content, ...(editing ? { expected_version: editing.version } : {}) }) }); setTitle(""); setContent(""); setEditing(null); }, "Memória salva"); }}>
        <h2>{editing ? "Revisar conhecimento" : "Uma decisão para o time lembrar"}</h2><p>Registre fatos, decisões e referências. Não inclua senhas ou tokens.</p>
        <label>Título da memória<input disabled={busy} value={title} onChange={event => setTitle(event.target.value)} maxLength={180} required /></label>
        <label>Conteúdo da memória<textarea disabled={busy} value={content} onChange={event => setContent(event.target.value)} rows={8} maxLength={64000} required /></label>
        <button className="button primary" disabled={busy}>{editing ? "Salvar revisão" : "Salvar memória"}</button>
        {editing && <button type="button" className="button" onClick={() => { setEditing(null); setTitle(""); setContent(""); }}>Cancelar edição</button>}
        <p>{vault ? "Vault Obsidian configurado no servidor." : "Obsidian: configure AI_TEAM_MEMORY_VAULT no servidor para sincronizar Markdown."}</p>
        <button type="button" className="button" disabled={busy || !vault} onClick={() => void perform(async () => { const result = await api<{ imported: number; rejected: number }>(`/memory/${project}/sync`, { method: "POST" }); if (result.rejected) throw new Error(`${result.rejected} arquivo(s) recusado(s); revise o vault. ${result.imported} importado(s).`); }, "Vault sincronizado")}>Sincronizar Obsidian</button>
      </form>
      <div><form className="knowledge-search" onSubmit={event => { event.preventDefault(); void perform(async () => { setNotes((await api<{ items: Note[] }>(query.trim() ? `/memory/${project}/search?q=${encodeURIComponent(query)}` : `/memory/${project}`)).items); }, "Busca concluída", false); }}><label>Buscar memórias<input value={query} onChange={event => setQuery(event.target.value)} maxLength={1000} /></label><button className="button" disabled={busy}>Buscar</button></form>
        {!notes.length && <p>Nenhuma memória neste projeto.</p>}
        {notes.map(note => <article className="panel knowledge-note" key={note.id}><div className="knowledge-note-heading"><h2>{note.title}</h2><span className="tag">Versão {note.version}</span></div><p className="knowledge-prose">{note.content}</p><small>{note.source} · {dateTime(note.updated_at)}{note.quarantined && " · Quarentena: não enviada aos agentes"}</small><div className="knowledge-actions"><button className="button" disabled={busy} onClick={() => void perform(async () => { const current = await api<Note>(`/memory/${project}/${note.id}`); setEditing(current); setTitle(current.title); setContent(current.content); }, "Memória carregada para edição", false)}>Editar memória</button><button className="button" disabled={busy} onClick={() => void perform(async () => { setHistory((await api<{ items: Revision[] }>(`/memory/${project}/${note.id}/history`)).items); }, "Histórico carregado")}>Ver histórico</button>{vault && <button className="button" disabled={busy || note.quarantined} onClick={() => void perform(async () => { const review = await api<Omit<ExportReview, "id">>(`/memory/${project}/${note.id}/export`); setExportReview({ ...review, id: note.id }); }, "Exportação pronta para revisão", false)}>Exportar Markdown</button>}</div></article>)}
        {!!history.length && <section className="panel" aria-label="Histórico da memória"><h2>Histórico da memória</h2>{history.map(item => <details key={item.version}><summary>Versão {item.version} · {dateTime(item.created_at)}</summary><p className="knowledge-prose">{item.content}</p></details>)}</section>}
      </div>
    </div>}
    {tab === "Issues" && <div className="knowledge-columns"><form className="panel knowledge-form" onSubmit={event => { event.preventDefault(); void perform(async () => { const id = requestId || crypto.randomUUID(); setRequestId(id); await api("/issues", { method: "POST", body: JSON.stringify({ project_id: project, request_id: id, title: issueTitle, body: issueBody, agent: issueAgent, priority: issuePriority }) }); setIssueTitle(""); setIssueBody(""); setRequestId(""); }, "Proposta preparada sem publicação remota"); }}><h2>Da solicitação à proposta</h2><p>O CEO prepara tarefas locais. Publicar exige revisar o conteúdo e aprovar seu digest em Integrações.</p><label>Título da issue<input minLength={5} maxLength={180} required value={issueTitle} onChange={event => setIssueTitle(event.target.value)} /></label><label>Descrição da issue<textarea rows={7} maxLength={8000} value={issueBody} onChange={event => setIssueBody(event.target.value)} /></label><label>Agente responsável<select value={issueAgent} onChange={event => setIssueAgent(event.target.value)}>{["CEO", "DEV", "DESIGNER", "QA", "PESQUISADOR"].map(item => <option key={item}>{item}</option>)}</select></label><label>Prioridade<select value={issuePriority} onChange={event => setIssuePriority(event.target.value)}><option value="low">Baixa</option><option value="medium">Média</option><option value="high">Alta</option></select></label><button className="button primary" disabled={busy}>Preparar proposta local</button></form><div><div className="knowledge-actions"><label>Filtrar agente<select value={agentFilter} onChange={event => setAgentFilter(event.target.value)}><option value="">Todos</option>{["CEO", "DEV", "DESIGNER", "QA", "PESQUISADOR"].map(item => <option key={item}>{item}</option>)}</select></label><label>Filtrar prioridade<select value={priorityFilter} onChange={event => setPriorityFilter(event.target.value)}><option value="">Todas</option><option value="low">Baixa</option><option value="medium">Média</option><option value="high">Alta</option><option value="critical">Crítica</option></select></label></div><label>Filtrar situação<select value={issueFilter} onChange={event => setIssueFilter(event.target.value)}><option value="">Todas</option><option value="todo">A fazer</option><option value="in_progress">Em execução</option><option value="done">Concluídas</option></select></label>{issues.filter(issue => (!issueFilter || issue.status === issueFilter) && (!agentFilter || issue.agent === agentFilter) && (!priorityFilter || issue.priority === priorityFilter)).map(issue => <article className="panel knowledge-note" key={issue.id}><h2>{issue.action.payload.title}</h2><p className="knowledge-prose">{issue.action.payload.body}</p><p>{issue.agent} · {issue.priority} · {issue.status}</p><p>{issue.action.status === "pending" ? "Aguardando revisão" : issue.action.status}</p><small>ID persistente: {issue.request_id}</small><details><summary>Conteúdo vinculado à aprovação</summary><code className="knowledge-prose">{issue.action.digest}</code><p>Uma alteração remota exige aprovação deste conteúdo exato.</p></details><Link className="button" href="/integracoes">Revisar aprovação GitHub</Link>{issue.action.result.url && <><a className="button" href={issue.action.result.url} target="_blank" rel="noreferrer">Abrir issue</a><button className="button" disabled={busy} onClick={() => void perform(async () => { await api(`/issues/${issue.id}/sync`, { method: "POST" }); }, "Estado remoto consultado")}>Consultar status remoto</button><p>GitHub: {issue.remote_state}</p></>}</article>)}{!issues.length && <p>Nenhuma proposta neste projeto.</p>}</div></div>}
    {tab === "Otimizador" && <><div className="knowledge-metrics"><article className="panel"><h2>Uso reportado</h2><strong>{(summary?.measured_input_tokens || 0) + (summary?.measured_output_tokens || 0)}</strong><p>Tokens de entrada e saída do provedor</p></article><article className="panel"><h2>Cache de contexto</h2><strong>{summary?.cache_hits || 0} / {summary?.cache_misses || 0}</strong><p>Acertos / consultas novas · {summary?.in_flight || 0} reservas pendentes</p></article></div><section aria-label="Uso por agente e execução">{summary?.usage_by_agent_task?.map(item => <p className="knowledge-prose" key={`${item.agent}:${item.task_id}`}>{item.agent} · {item.task_id}: {item.input_tokens} entrada + {item.output_tokens} saída</p>)}</section><p>Economia medida: indisponível sem comparação autorizada no provedor.</p><div className="knowledge-columns"><form className="panel knowledge-form" onSubmit={event => { event.preventDefault(); void perform(async () => { setPreview(await api<Preview>(`/projects/${project}/optimizer/preview`, { method: "POST", body: JSON.stringify({ context: { request }, budget: 50000 }) })); }, "Prévia local calculada sem inferência"); }}><h2>Contexto antes da chamada</h2><label>Solicitação para prévia<textarea rows={6} required value={request} onChange={event => setRequest(event.target.value)} maxLength={5000} /></label><button className="button primary" disabled={busy}>Calcular prévia local</button>{preview && <section aria-label="Resultado da prévia"><h3>Estimativa de contexto</h3><p>{preview.estimated_before} → {preview.estimated_after} unidades conservadoras (bytes UTF-8). Não é consumo medido.</p><p>{preview.cache_hit ? "Cache reutilizado" : "Cache novo"}</p>{preview.mandatory_over_budget && <p role="alert">Contexto obrigatório acima do limite; requisitos foram preservados.</p>}<p>{preview.discarded_optional || 0} trechos opcionais descartados · {preview.selected_memories?.length || 0} memórias selecionadas</p><details><summary>Contexto selecionado</summary><pre className="knowledge-prose">{JSON.stringify(preview.context, null, 2)}</pre></details></section>}</form><form className="panel knowledge-form" onSubmit={event => { event.preventDefault(); void perform(async () => { await api(`/projects/${project}/optimizer/budgets`, { method: "PUT", body: JSON.stringify({ scope, scope_id: scope === "project" ? "" : scopeId, limit: Number(limit) }) }); }, "Orçamento atualizado"); }}><h2>Limites de admissão</h2><p>Uma chamada em andamento pode superar a estimativa. Falhas incertas mantêm a reserva.</p><label>Escopo do orçamento<select value={scope} onChange={event => { setScope(event.target.value); setScopeId(""); }}><option value="project">Projeto</option><option value="agent">Agente</option><option value="task">Execução</option></select></label>{scope !== "project" && <label>Identificador do escopo<input value={scopeId} onChange={event => setScopeId(event.target.value)} required placeholder={scope === "agent" ? "DEV" : "ID da execução"} /></label>}<label>Limite do orçamento<input type="number" min={1} max={100000000} required value={limit} onChange={event => setLimit(event.target.value)} /></label><button className="button" disabled={busy}>Salvar limite</button>{summary?.budgets.map(item => <p key={`${item.scope}:${item.scope_id}`}>{item.scope} {item.scope_id}: {item.used} usados + {item.reserved} reservados / {item.limit}{item.over_budget && " · LIMITE EXCEDIDO"}</p>)}</form></div></>}
    {tab === "Relações" && <section className="panel"><h2>Relações do projeto</h2><p>Relações derivadas dos registros persistidos. Propostas não representam recursos remotos publicados.</p><p>{graph?.nodes.length || 0} nós · {graph?.links.length || 0} relações{graph?.truncated && " · Exibição limitada"}</p><ul className="knowledge-graph">{graph?.nodes.map(node => <li key={node.id}><strong>{node.label}</strong><small>{node.kind} · {node.provenance}</small></li>)}</ul><details><summary>Ver relações registradas</summary>{graph?.links.map((edge, index) => <p className="knowledge-prose" key={index}>{edge.source} → {edge.relation} → {edge.target}</p>)}</details><p>Graphify: intercâmbio local validado; análise semântica externa não executada.</p></section>}
  </>;
}
