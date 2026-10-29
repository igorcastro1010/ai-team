"use client";
import { useRef, useState, type FormEvent } from "react";
import { api, dateTime, type GitHubAction, type Workspace } from "@/lib/api";

const operations: Record<string, string> = { branch: "Criar branch", commit: "Commit de documento", issue: "Criar issue", pull_request: "Abrir pull request" };
const statuses: Record<string, string> = { pending: "Revisão pendente", approved: "Autorizada · na fila", running: "Executando", succeeded: "Concluída", failed: "Bloqueada ou falhou", uncertain: "Conferência necessária", rejected: "Recusada" };

function ProposalPreview({ action, data }: { action: GitHubAction; data: Workspace }) {
  const payload = action.payload;
  return <div className="proposal-preview"><dl>
    <dt>Projeto</dt><dd>{data.projects.find(project => project.id === action.project_id)?.name || "Projeto vinculado"}</dd>
    <dt>Operação</dt><dd>{operations[payload.operation]}</dd><dt>Título</dt><dd>{payload.title}</dd>
    {payload.branch && <><dt>Branch</dt><dd>{payload.branch}</dd></>}
    {payload.expected_sha && <><dt>SHA revisado</dt><dd><code>{payload.expected_sha}</code></dd></>}
    {payload.path && <><dt>Arquivo</dt><dd>{payload.path}</dd></>}
    {payload.operation === "pull_request" && <><dt>Destino</dt><dd>main · {payload.draft ? "Rascunho" : "PR aberto para revisão"}</dd></>}
  </dl>{payload.body && <><h3>Descrição</h3><pre className="artifact-content">{payload.body}</pre></>}
  {payload.content && <><h3>Conteúdo completo</h3><pre className="artifact-content">{payload.content}</pre></>}</div>;
}

export function GitHubPanel({ data, reload }: { data: Workspace; reload: () => Promise<void> }) {
  const [operation, setOperation] = useState("branch");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<GitHubAction | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const connection = data.github.connection;
  async function perform(task: () => Promise<unknown>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try { await task(); await reload(); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível concluir."); }
    finally { lock.current = false; setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = { operation };
    for (const key of ["project_id", "title", "branch", "expected_sha", "path", "content", "body"]) {
      if (values.has(key)) payload[key] = values.get(key);
    }
    if (operation === "pull_request") payload.draft = values.get("draft") === "on";
    void perform(() => api("/github/proposals", { method: "POST", body: JSON.stringify(payload) }));
  }
  function decide(action: GitHubAction, approve: boolean) {
    void perform(async () => {
      await api(`/github/proposals/${action.id}/decision`, { method: "POST", body: JSON.stringify({ digest: action.digest, approve }) });
      dialog.current?.close(); setSelected(null);
    });
  }
  return <section className="github-section" aria-label="Desenvolvimento no GitHub">
    <div className="panel run-card"><div className="run-head"><h2>GitHub, com revisão antes de agir.</h2><button className="button secondary" disabled={busy} onClick={() => void perform(() => api("/github/verify", { method: "POST" }))}>{busy ? "Aguarde…" : "Verificar GitHub App"}</button></div>
      <p>Somente <strong>igorcastro1010/ai-team</strong>. Branches em codex/ai-team/, documentos em docs/agent-output/. Cada proposta exige sua aprovação, inclusive no modo automático.</p>
      {connection ? <p className="field-help">Verificada em {dateTime(connection.verified_at)} · base {connection.default_branch}{connection.head_sha && <> · SHA <code>{connection.head_sha}</code></>}</p> : <p className="field-help">Verifique a App para consultar a instalação e o SHA atual da branch principal.</p>}
      {error && <p className="notice error" role="alert">{error}</p>}
    </div>
    <section className="panel ceo-compose"><div className="panel-title"><h2>Preparar proposta</h2><span className="tag">AINDA NÃO EXECUTA</span></div>
      {data.projects.length ? <form className="ceo-form" onSubmit={submit}>
        <label htmlFor="gh-project">Projeto da proposta</label><select id="gh-project" name="project_id" required>{data.projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
        <label htmlFor="gh-operation">Operação GitHub</label><select id="gh-operation" value={operation} onChange={event => setOperation(event.target.value)}>{Object.entries(operations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <label htmlFor="gh-title">Título ou mensagem de commit</label><input id="gh-title" name="title" required minLength={5} maxLength={180} placeholder={operation === "commit" ? "docs: descreva a alteração" : "Descreva o objetivo da proposta"} />
        {operation !== "issue" && <><label htmlFor="gh-branch">Branch de trabalho</label><input id="gh-branch" name="branch" required pattern="codex/ai-team/[a-z0-9][a-z0-9-]{0,60}" placeholder="codex/ai-team/minha-tarefa" /></>}
        {operation !== "issue" && <><label htmlFor="gh-sha">SHA revisado da base</label><input key={operation + (connection?.head_sha || "")} id="gh-sha" name="expected_sha" required pattern="[a-f0-9]{40}" defaultValue={operation === "branch" ? connection?.head_sha || "" : ""} /><p className="field-help">Para branch, use o SHA da main acima. Para commit ou PR, use o SHA atual da sua branch, disponível no resultado da criação ou do último commit.</p></>}
        {operation === "commit" && <><label htmlFor="gh-path">Caminho do documento</label><input id="gh-path" name="path" required placeholder="docs/agent-output/proposta.md" /><label htmlFor="gh-content">Conteúdo completo do documento</label><textarea id="gh-content" name="content" rows={8} required maxLength={20000} /><p className="field-help">O conteúdo informado substitui o documento desse caminho na branch de trabalho.</p></>}
        {["issue", "pull_request"].includes(operation) && <><label htmlFor="gh-body">Descrição</label><textarea id="gh-body" name="body" rows={5} maxLength={8000} /></>}
        {operation === "pull_request" && <label className="consent-field"><input name="draft" type="checkbox" defaultChecked /><span>Abrir como rascunho. Depende da disponibilidade no plano GitHub do repositório.</span></label>}
        <label className="consent-field"><input type="checkbox" required /><span>Revisei o conteúdo e não incluí credenciais ou dados sensíveis. Esta etapa somente registra a proposta; a execução depende de aprovação separada.</span></label>
        <button className="button" disabled={busy}>Registrar proposta</button>
      </form> : <p className="empty-state">Crie um projeto no workspace para preparar propostas.</p>}
    </section>
    <div className="run-section-title"><h2>Propostas e resultados do GitHub</h2></div>
    <div className="run-list">{data.github.actions.map(action => <article className="panel run-card" key={action.id} data-testid="github-action">
      <div className="run-head"><span className="tag">{statuses[action.status] || action.status}</span><small>{dateTime(action.created_at)}</small></div>
      <h3>{action.payload.title}</h3><p>{operations[action.payload.operation]} · igorcastro1010/ai-team</p>
      <details className="run-artifact"><summary>Revisar todo o conteúdo</summary><ProposalPreview action={action} data={data} /></details>
      {action.error && <p className="notice error">{action.error}</p>}
      {action.result.url && <p><a href={action.result.url} target="_blank" rel="noopener noreferrer">Ver resultado no GitHub</a></p>}
      {action.result.sha && <p className="field-help">SHA do resultado: <code>{action.result.sha}</code></p>}
      {action.status === "pending" && <div className="compose-actions"><button className="button secondary" disabled={busy} onClick={() => decide(action, false)}>Recusar proposta</button><button className="button" disabled={busy} onClick={() => { setSelected(action); dialog.current?.showModal(); }}>Revisar aprovação</button></div>}
    </article>)}</div>
    <dialog ref={dialog} className="creation-dialog" aria-labelledby="gh-confirm-title" onCancel={event => { if (busy) event.preventDefault(); else setSelected(null); }}>
      <div className="dialog-heading"><h2 id="gh-confirm-title">Autorizar ação no GitHub?</h2></div>
      <div className="dialog-body"><p>A autorização permite ao worker executar esta proposta uma vez no repositório ai-team. Revise o conteúdo antes de confirmar.</p>{selected && <ProposalPreview action={selected} data={data} />}{error && <p className="notice error" role="alert">{error}</p>}</div>
      <div className="dialog-actions"><button className="button secondary" disabled={busy} onClick={() => { dialog.current?.close(); setSelected(null); }}>Voltar à revisão</button><button className="button" disabled={busy || !selected} onClick={() => selected && decide(selected, true)}>{busy ? "Autorizando…" : "Autorizar execução"}</button></div>
    </dialog>
  </section>;
}
