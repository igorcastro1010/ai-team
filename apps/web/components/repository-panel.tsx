"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type Run, type Workspace } from "@/lib/api";

type RepositoryView = {
  run: Run; digest: string;
  state: {
    policy: { repository: string; base_sha: string; directory: string; write_paths: string[] };
    diff?: string; test_result?: { status: string; output: string };
    proposal?: { branch: string; title: string; published: boolean };
    reviewed_digest?: string; delivery?: { status: string; url?: string };
  };
};
const labels: Record<string, string> = { queued: "Na fila", running: "Executando", awaiting_approval: "Aguardando aprovação", completed: "Entrega revisada", failed: "Falha", cancelled: "Cancelada", blocked: "Executor indisponível" };
const roles = ["CEO · Planejando", "PESQUISADOR · Pesquisando", "DEV · Programando", "DESIGNER · Documentando", "QA · Escrevendo testes", "QA / CEO · Testes e revisão"];

export function RepositoryPanel({ data }: { data: Workspace }) {
  const [items, setItems] = useState<RepositoryView[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setItems(await api<RepositoryView[]>("/repository-runs")); }
    catch (err) { setError(err instanceof Error ? err.message : "Falha ao carregar execuções."); }
  }, []);
  useEffect(() => { const start = setTimeout(() => void load(), 0); const timer = setInterval(() => void load(), 5000); return () => { clearTimeout(start); clearInterval(timer); }; }, [load]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    const form = new FormData(event.currentTarget);
    const paths = (name: string) => String(form.get(name)).split(",").map(s => s.trim()).filter(Boolean);
    setBusy(true); setError("");
    try {
      await api("/repository-runs", { method: "POST", body: JSON.stringify({ project_id: form.get("project"), prompt: form.get("prompt"), executor: form.get("executor"), consent: form.get("consent") === "on", policy: { base_sha: form.get("sha"), base_branch: form.get("base"), max_tokens: Number(form.get("budget")), directory: form.get("directory"), read_paths: paths("reads"), write_paths: paths("writes") } }) });
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível criar a tarefa."); }
    finally { setBusy(false); }
  }
  async function act(item: RepositoryView, action: string, approve = true) {
    if (busy) return; setBusy(true); setError("");
    try { await api(`/repository-runs/${item.run.id}/${action}`, { method: "POST", body: JSON.stringify({ digest: item.digest, approve }) }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Operação não concluída."); }
    finally { setBusy(false); }
  }
  return <section className="repository-console" aria-labelledby="repository-heading">
    <div className="section-toolbar"><h2 id="repository-heading">Executor de repositório</h2><span className="tag">PYTHON · V0.6</span></div>
    <p>Alterações reais em igorcastro1010/ai-team. Autorize uma pasta, arquivos e orçamento específicos. Até 6 chamadas; testes sem rede, 1 CPU, 256 MiB e 30 segundos.</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    <details className="panel" open={!items.length}><summary>Nova tarefa com workspace isolado</summary>
      <form className="ceo-form" onSubmit={submit}>
        <label htmlFor="repo-project">Projeto do executor</label><select id="repo-project" name="project" required>{data.projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        <label htmlFor="repo-executor">Provedor do executor</label><select id="repo-executor" name="executor"><option value="codex">Codex próprio</option><option value="hermes">Hermes próprio</option></select>
        <label htmlFor="repo-prompt">Pedido para o repositório</label><textarea id="repo-prompt" name="prompt" minLength={5} maxLength={5000} required />
        <label htmlFor="repo-base">Branch de origem</label><input id="repo-base" name="base" defaultValue="main" required />
        <label htmlFor="repo-sha">SHA de origem</label><input id="repo-sha" name="sha" pattern="[a-f0-9]{40}" maxLength={40} required />
        <label htmlFor="repo-budget">Limite de tokens autorizado</label><input id="repo-budget" type="number" name="budget" defaultValue={100000} min={16000} max={100000} required /><p>O contexto inicial do provedor conta no consumo. O limite impede novas chamadas; uma resposta em andamento pode ultrapassá-lo. A homologação de seis etapas consumiu 82.689 tokens; revise o orçamento antes de autorizar.</p>
        <label htmlFor="repo-directory">Pasta autorizada</label><input id="repo-directory" name="directory" placeholder="tools" required />
        <label htmlFor="repo-reads">Arquivos para leitura</label><input id="repo-reads" name="reads" placeholder="budget.py" required />
        <label htmlFor="repo-writes">Arquivos para escrita</label><input id="repo-writes" name="writes" placeholder="budget.py, test_budget.py, guide.md" required />
        <p>Separe nomes por vírgula. Fonte .py, test_*.py e documentação .md são obrigatórios. Sem subpastas, dependências ou arquivos sensíveis. Pesquisa limitada ao snapshot.</p>
        <label className="consent-row"><input type="checkbox" name="consent" required /> Autorizo estes caminhos e o envio do código aos agentes pelo provedor próprio. Revisarei os artefatos antes de executar testes e publicar.</label>
        <button className="button primary" disabled={busy || !data.projects.length}>Criar tarefa isolada</button>
      </form>
    </details>
    <div className="run-list">{items.map(item => <article className="panel run-card" data-testid="repository-card" key={item.run.id}>
      <span className="tag">{labels[item.run.status] || item.run.status}</span><h3>{item.run.prompt}</h3>
      <p>{item.run.stage}/6 etapas · {item.run.calls}/6 chamadas · {item.run.input_tokens + item.run.output_tokens} tokens</p>
      <p>{item.run.stage < 6 ? roles[item.run.stage] : "CEO · Proposta de entrega"} · {item.run.executor}</p>
      <p className="repository-binding">{item.state.policy.directory} @ {item.state.policy.base_sha}</p>
      {item.run.error && <p className="notice error">{item.run.error}</p>}
      {item.run.steps.map(s => <details key={s.stage}><summary>{s.agent}: {s.summary}</summary><pre>{s.deliverable}</pre></details>)}
      {item.state.diff && <details><summary>Revisar diff Git e arquivos</summary><pre>{item.state.diff}</pre><a className="button" href={`/api/control/repository-runs/${item.run.id}/artifacts`}>Baixar arquivos e diff</a></details>}
      {item.state.test_result && <details open><summary>Testes isolados: {item.state.test_result.status}</summary><pre>{item.state.test_result.output}</pre></details>}
      {item.state.proposal && <details><summary>Proposta de pull request</summary><p>{item.state.proposal.title}</p><code>{item.state.proposal.branch}</code><p>{item.state.proposal.published ? "Publicada" : "Preparada para revisão"}. Nenhum merge ou deploy.</p></details>}
      {item.run.status === "awaiting_approval" && <div className="run-approval"><p className="repository-binding">Checkpoint revisado: {item.digest}</p><button className="button" disabled={busy} onClick={() => void act(item, "decision", false)}>Rejeitar tarefa</button><button className="button primary" disabled={busy || (item.run.stage === 6 && item.state.test_result?.status !== "passed")} onClick={() => void act(item, "decision")}>{item.run.stage === 5 ? "Autorizar testes deste conteúdo" : item.run.stage === 6 ? "Aprovar entrega revisada" : "Autorizar próxima etapa"}</button></div>}
      {["queued", "running", "blocked"].includes(item.run.status) && <button className="button" disabled={busy} onClick={() => void act(item, "cancel")}>Cancelar tarefa isolada</button>}
      {item.run.status === "completed" && !item.state.delivery && <details><summary>Publicar branch e PR rascunho</summary><p>A publicação cria uma branch e um PR somente com estes arquivos e SHA revisados.</p><button className="button" disabled={busy} onClick={() => void act(item, "publish")}>Autorizar publicação deste PR</button></details>}
      {item.state.delivery && <p>GitHub: {item.state.delivery.status} {item.state.delivery.url && <a href={item.state.delivery.url} target="_blank" rel="noreferrer">Abrir PR</a>}</p>}
    </article>)}</div>
    <style jsx>{`.repository-console { margin-top: 32px; } .repository-console form { padding: 20px 0; } .repository-console pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 360px; overflow: auto; padding: 16px; background: var(--surface, #161b18); font-size: 12px; } .repository-binding, .repository-console code { overflow-wrap: anywhere; word-break: break-word; } .repository-console details { margin: 12px 0; } .repository-console summary { cursor: pointer; min-height: 44px; padding: 12px 0; } .repository-console input, .repository-console textarea, .repository-console select { max-width: 100%; min-width: 0; }`}</style>
  </section>;
}
