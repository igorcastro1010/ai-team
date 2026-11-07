"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowUpRight, Check, ChevronRight, CircleDashed, ShieldCheck, X } from "lucide-react";
import { api, dateTime, modes, type Run, type Workspace } from "@/lib/api";
import { CodeArtifacts } from "./code-artifacts";

const runLabels: Record<string, string> = {
  queued: "Na fila", running: "Executando", awaiting_approval: "Aguarda aprovação",
  completed: "Relatório entregue", cancelled: "Cancelada", failed: "Falha", blocked: "Bloqueada",
  waiting_model: "Aguarda modelo autorizado", waiting_quota: "Aguarda cota", awaiting_codex: "Aguarda Codex supervisionado",
};
const codeScopes = new Set(["python_code", "nextjs_code"]);
const stages = ["CEO · Planejamento", "DEV · Proposta técnica", "DESIGNER · Interface", "QA · Revisão", "CEO · Relatório"];

export function CeoConsole({ data, reload }: { data: Workspace; reload: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [projectId, setProjectId] = useState(data.projects[0]?.id || "");
  const [executor, setExecutor] = useState("codex");
  const [scope, setScope] = useState("draft_only");
  const mode = data.projects.find(project => project.id === projectId)?.mode || "supervised";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true); setError(""); setSuccess("");
    try {
      await api("/runs", { method: "POST", body: JSON.stringify({ project_id: projectId, prompt: values.get("prompt"), executor, scope, consent: values.get("consent") === "on" }) });
      form.reset(); setSuccess("Solicitação registrada. Acompanhe o plano e as próximas etapas abaixo.");
      await reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível registrar a solicitação."); }
    finally { setBusy(false); }
  }
  return <>
    <div className="principle-strip"><ShieldCheck size={18} aria-hidden="true" /><span>O CEO coordena o time. A entrega de código gera arquivos e executa testes isolados após sua revisão e aprovação.</span></div>
    <section className="panel ceo-compose"><div className="panel-title"><h2>Converse com o CEO</h2><span className="tag">{data.usage.worker_online ? "WORKER ONLINE" : "WORKER OFFLINE"}</span></div>
      {data.projects.length ? <form onSubmit={submit} className="ceo-form"><div className="compose-project"><div><label htmlFor="request-project">Projeto da solicitação</label><select id="request-project" value={projectId} onChange={event => setProjectId(event.target.value)} required>{data.projects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}</select></div><div className="compose-mode"><span className="tag">{modes[mode]}</span><p>{mode === "manual" ? "Você autoriza cada próxima etapa." : mode === "supervised" ? "O time continua após sua aprovação do plano." : "As cinco etapas textuais estão incluídas na autorização abaixo."}</p></div></div>
        <label htmlFor="request-executor">Executor da solicitação</label><select id="request-executor" value={executor} onChange={event => { setExecutor(event.target.value); const consent = event.target.form?.elements.namedItem("consent"); if (consent instanceof HTMLInputElement) consent.checked = false; }}><option value="codex">Codex · executor existente</option><option value="hermes">Hermes · gateway privado</option></select>
        <label htmlFor="ceo-request">O que você quer construir?</label><textarea id="ceo-request" name="prompt" rows={5} minLength={5} maxLength={5000} required placeholder="Descreva objetivo, contexto e o resultado esperado…" />
        <label htmlFor="request-scope">Tipo de entrega</label><select id="request-scope" value={scope} onChange={event => { setScope(event.target.value); const consent = event.target.form?.elements.namedItem("consent"); if (consent instanceof HTMLInputElement) consent.checked = false; }}><option value="draft_only">Planejamento e pareceres</option><option value="python_code">Código Python com testes isolados</option><option value="nextjs_code">Projeto Next.js com build e testes</option></select>
        {scope === "nextjs_code" && <p className="field-help">DEV gera TSX, DESIGNER cria CSS e QA define verificações do HTML. Você aprova o projeto antes do build isolado. Sem pacotes adicionais ou publicação.</p>}
        {scope === "python_code" && <p className="field-help">DEV gera arquivos e QA prepara testes. Você revisa os arquivos antes de autorizar a execução, mesmo no modo automático. Python sem dependências externas.</p>}
        <label className="consent-field"><input type="checkbox" name="consent" required /><span>Autorizo enviar esta solicitação ao {executor === "hermes" ? "Hermes" : "Codex"} e {codeScopes.has(scope) ? "gerar código e testes para revisão" : "gerar planos e pareceres"}: até 5 chamadas, 120 segundos por chamada. Nenhum dado sensível deve ser incluído. O consumo usa os limites da minha conta.</span></label>
        {!data.usage.worker_online && <p className="field-help">O worker está offline. A solicitação ficará na fila até o processo ser iniciado.</p>}
        {error && <p className="notice error" role="alert">{error}</p>}{success && <p className="notice success" role="status">{success}</p>}
        <div className="compose-actions"><small>{codeScopes.has(scope) ? "Geração de código; testes exigem aprovação dos arquivos." : "Escopo autorizado: elaboração textual."} Custo monetário não disponível.</small><button className="button primary" disabled={busy}>{busy ? "Registrando…" : "Enviar ao CEO"}<ArrowUpRight size={17} aria-hidden="true" /></button></div>
      </form> : <div className="empty-state"><h3>Primeiro, dê um lugar à ideia.</h3><p>Crie um projeto para vincular a conversa, as tarefas e o histórico.</p><Link href="/projetos" className="button">Abrir projetos <ArrowUpRight size={17} aria-hidden="true" /></Link></div>}
    </section>
    <div className="section-toolbar run-section-title"><h2>Solicitações e respostas</h2><span>{data.runs.length} registradas</span></div><RunList data={data} runs={data.runs} reload={reload} />
  </>;
}

export function RunList({ data, runs, reload }: { data: Workspace; runs: Run[]; reload: () => Promise<void> }) {
  runs = runs.filter(run => run.scope !== "repository_code");
  const [pending, setPending] = useState<{ run: Run; action: "approve" | "reject" | "cancel" | "resume" } | null>(null);
  return <>
    {!runs.length && <section className="panel"><div className="empty-state"><CircleDashed size={29} aria-hidden="true" /><h2>Nenhuma execução por aqui.</h2><p>Envie uma solicitação ao CEO para iniciar um plano com histórico persistente.</p><Link href="/ceo" className="button">Conversa com CEO <ArrowUpRight size={17} aria-hidden="true" /></Link></div></section>}
    <div className="run-list">{runs.map(run => <article className="panel run-card" key={run.id} data-testid="run-card"><div className="run-head"><span className={`tag run-status status-${run.status}`}>{runLabels[run.status] || run.status}</span><small>{dateTime(run.created_at)}</small></div><p className="eyebrow">{data.projects.find(project => project.id === run.project_id)?.name} <span aria-hidden="true">/</span> {modes[run.mode]}</p><h2>{run.prompt}</h2><div className="run-progress"><span>{run.stage}/5 etapas</span><span>{run.calls}/5 chamadas</span><span>{(run.input_tokens + run.output_tokens).toLocaleString("pt-BR")} tokens</span></div>
      {run.status === "running" && <p className="run-current" role="status"><span className="dot" />{codeScopes.has(run.scope) && run.stage === 4 && run.steps[3]?.execution_started && !run.steps[3]?.test_result ? "QA · Testes isolados" : stages[run.stage]} em andamento…</p>}
      {run.error && <p className="notice error">{run.error}</p>}
      {run.steps.map(step => <details className="run-artifact" key={step.stage} open={step.stage === 0 && run.status === "awaiting_approval"}><summary><span className="artifact-number">{String(step.stage + 1).padStart(2, "0")}</span><span><strong>{stages[step.stage]}</strong><small>{step.summary}</small></span><ChevronRight size={17} aria-hidden="true" /></summary><div className="artifact-content">{step.deliverable}</div></details>)}
      <CodeArtifacts run={run} />
      {run.status === "awaiting_approval" && <div className="run-approval"><p><ShieldCheck size={16} aria-hidden="true" />{codeScopes.has(run.scope) && run.stage === 4 ? "Revise os arquivos antes de autorizar os testes isolados desta versão." : "Revise o plano e os artefatos antes de autorizar a próxima etapa."}</p><div><button className="button" onClick={() => setPending({ run, action: "reject" })}>Rejeitar</button><button className="button primary" onClick={() => setPending({ run, action: "approve" })}><Check size={16} aria-hidden="true" />{codeScopes.has(run.scope) && run.stage === 4 ? (run.scope === "nextjs_code" ? "Aprovar build e testes" : "Aprovar execução dos testes") : "Aprovar próxima etapa"}</button></div></div>}
      {run.executor === "central" && <Link href="/modelos" className="button">Configuração, cotas e encaminhamento na Central de IA</Link>}
      {["queued", "running", "blocked", "waiting_model", "waiting_quota", "awaiting_codex"].includes(run.status) && <div className="run-controls"><button className="text-button" onClick={() => setPending({ run, action: "cancel" })}>Cancelar execução</button>{run.status === "blocked" && <button className="button" onClick={() => setPending({ run, action: "resume" })}>Tentar após configurar</button>}</div>}
      {run.status === "completed" && <p className="run-footnote">{codeScopes.has(run.scope) ? "Projeto e relatório entregues. Confira o resultado dos testes acima. Nenhum commit ou deploy foi realizado." : "Relatório textual entregue. Os artefatos são propostas e revisões; nenhuma alteração externa foi executada."}</p>}
    </article>)}</div>
    {pending && <RunConfirmation pending={pending} close={() => setPending(null)} reload={reload} />}
  </>;
}

function RunConfirmation({ pending, close, reload }: {
  pending: { run: Run; action: "approve" | "reject" | "cancel" | "resume" }; close: () => void; reload: () => Promise<void>;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { ref.current?.showModal(); }, []);
  const labels = { approve: "Autorizar elaboração", reject: "Rejeitar execução", cancel: "Cancelar execução", resume: "Retomar execução" };
  const approveCode = pending.action === "approve" && codeScopes.has(pending.run.scope) && pending.run.stage === 4;
  if (approveCode) labels.approve = pending.run.scope === "nextjs_code" ? "Autorizar validação Next.js" : "Autorizar testes Python";
  async function confirm() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const isDecision = ["approve", "reject"].includes(pending.action);
      await api(`/runs/${pending.run.id}/${isDecision ? "decision" : pending.action}`, {
        method: "POST", body: isDecision ? JSON.stringify({ stage: pending.run.stage, approve: pending.action === "approve", artifact_digest: approveCode ? pending.run.artifact_digest : "" }) : undefined,
      });
      await reload(); close();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível concluir."); }
    finally { setBusy(false); }
  }
  return <dialog ref={ref} className="creation-dialog" aria-labelledby="run-confirm-title" onCancel={event => { if (busy) event.preventDefault(); else close(); }}><div className="dialog-head"><p className="eyebrow">DECISÃO DO PROPRIETÁRIO</p><button className="icon-button" disabled={busy} onClick={close} aria-label="Fechar confirmação"><X size={19} aria-hidden="true" /></button></div><h2 id="run-confirm-title">{labels[pending.action]}?</h2>{approveCode ? <><p>Autorizar somente estes arquivos em Docker, sem rede nem acesso a seus diretórios: até {pending.run.scope === "nextjs_code" ? "120 segundos, 1 GiB e 2 CPUs" : "30 segundos, 256 MiB e 1 CPU"}. Depois o CEO consolida o resultado.</p><code className="code-digest">{pending.run.artifact_digest}</code></> : <p>{pending.action === "approve" || pending.action === "resume" ? `Esta autorização se refere à execução selecionada e à etapa ${pending.run.stage + 1}: ${stages[pending.run.stage]}. Dentro do limite de cinco chamadas. Testes Python exigem aprovação separada dos arquivos.` : "A execução será encerrada. Artefatos e histórico serão preservados. Uma chamada já enviada pode consumir os limites da conta até ser interrompida."}</p>}{error && <p className="notice error" role="alert">{error}</p>}<div className="dialog-actions"><button className="button" onClick={close} disabled={busy}>Voltar</button><button className="button primary" disabled={busy} onClick={() => void confirm()}>{busy ? "Confirmando…" : labels[pending.action]}</button></div></dialog>;
}
