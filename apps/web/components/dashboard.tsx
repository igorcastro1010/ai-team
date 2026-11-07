"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Activity, ArrowRight, ArrowUpRight, Bot, CheckCheck,
  ChevronRight, CircleDashed, FileText, Folder, Grid2X2, History,
  Layers3, ListTodo, LogOut, Menu, MessageSquare, Plug, Plus, RefreshCw,
  ShieldCheck, Sparkles, Terminal, Users, X, type LucideIcon,
} from "lucide-react";
import { api, ApiError, dateTime, modes, statusLabel, type Task, type TaskStatus, type Workspace } from "@/lib/api";
import { CreationDialog } from "./creation-dialog";
import { CeoConsole, RunList } from "./run-panel";
import { GitHubPanel } from "./github-panel";
import { VercelPanel } from "./vercel-panel";
import { SchedulePanel } from "./schedule-panel";
import { ReportsPanel } from "./reports-panel";
import { HermesPanel } from "./hermes-panel";
import { PixelOffice } from "./pixel-office";
import { RepositoryPanel } from "./repository-panel";
import { KnowledgePanel } from "./knowledge-panel";
import { ModelsPanel } from "./models-panel";
import { VideoPanel } from "./video-panel";
import { OfficeWindow } from "./office-window";

import { views, type View } from "@/lib/navigation";

const navigation: { view: View; icon: LucideIcon; group: string }[] = [
  { view: "overview", icon: Grid2X2, group: "WORKSPACE" },
  { view: "resumo", icon: Grid2X2, group: "" },
  { view: "escritorio", icon: Bot, group: "" },
  { view: "ceo", icon: MessageSquare, group: "" },
  { view: "memoria", icon: Layers3, group: "" },
  { view: "modelos", icon: Bot, group: "" },
  { view: "videos", icon: Layers3, group: "" },
  { view: "projetos", icon: Folder, group: "" },
  { view: "tarefas", icon: ListTodo, group: "" },
  { view: "agentes", icon: Users, group: "OPERAÇÃO" },
  { view: "execucoes", icon: Activity, group: "" },
  { view: "agendamentos", icon: History, group: "" },
  { view: "aprovacoes", icon: ShieldCheck, group: "" },
  { view: "historico", icon: History, group: "" },
  { view: "relatorios", icon: FileText, group: "SISTEMA" },
  { view: "integracoes", icon: Plug, group: "" },
];
const href = (view: View) => view === "overview" ? "/" : `/${view}`;

export function Dashboard() {
  const pathname = usePathname();
  const route = pathname.split("/")[1] || "overview";
  const view: View = Object.hasOwn(views, route) ? route as View : "overview";
  const toolOpen = view !== "overview" && view !== "escritorio";
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"project" | "task" | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [updating, setUpdating] = useState(false);
  const router = useRouter();
  const load = useCallback(async () => {
    try { setWorkspace(await api<Workspace>("/workspace")); setError(""); }
    catch (err) {
      if (err instanceof ApiError && err.status === 401) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : "Não foi possível carregar o workspace.");
    }
  }, [router]);
  useEffect(() => {
    const initial = window.setTimeout(() => { void load(); }, 0);
    const interval = window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, 5000);
    return () => { window.clearTimeout(initial); window.clearInterval(interval); };
  }, [load]);
  async function logout() {
    if (updating) return;
    setUpdating(true);
    try { await api("/auth/logout", { method: "POST" }); router.replace("/login"); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível sair."); }
    finally { setUpdating(false); }
  }
  async function move(task: Task, status: TaskStatus) {
    if (updating) return;
    setUpdating(true);
    try { await api(`/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ status }) }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível atualizar a tarefa."); }
    finally { setUpdating(false); }
  }
  function newTask() { setDialog(workspace?.projects.length ? "task" : "project"); }
  const meta = views[view];
  return <div className={`workspace-shell office-shell integrated-office ${menuOpen ? "navigation-open" : ""}`}>
    <a className="skip-link" href="#main-content">Pular para o conteúdo</a>
    <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
      <Link href="/" className="brand" aria-label="AI TEAM início"><span className="brand-mark">ai</span><span>AI TEAM<small>INTELIGÊNCIA EM EQUIPE</small></span></Link>
      <div className="workspace-tag"><span className="workspace-avatar">I</span><div>Workspace pessoal<small>Proprietário único</small></div><ChevronRight size={15} aria-hidden="true" /></div>
      <nav aria-label="Navegação principal">{navigation.map(({ view: item, icon: Icon, group }) => <div key={item}>
        {group && <p className="nav-group">{group}</p>}
        <Link className={`nav-link ${view === item ? "active" : ""}`} href={href(item)} aria-current={view === item ? "page" : undefined} onClick={() => setMenuOpen(false)}><Icon size={18} aria-hidden="true" /><span>{views[item].label}</span>{item === "aprovacoes" && !!workspace?.approvals.length && <span className="nav-count">{workspace.approvals.length}</span>}</Link>
      </div>)}</nav>
      <div className="sidebar-foot"><div className="local-state"><span className="dot" /> {workspace ? "Workspace conectado" : "Conectando…"}</div><span className="version">V{workspace?.version || "0.1.0"} · OPERAÇÃO COM CONTROLE</span>
        <button className="logout" onClick={logout} disabled={updating} aria-label="Sair do workspace"><span className="owner-avatar">{workspace?.owner.slice(0, 1).toUpperCase() || "·"}</span><span>{workspace?.owner || "Proprietário"}<small>Conta privada</small></span><LogOut size={16} aria-hidden="true" /></button>
      </div>
    </aside>
    <div className="workspace-body">
      <header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" aria-label={menuOpen ? "Fechar navegação" : "Abrir navegação"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={20} /> : <Menu size={20} />}</button><span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><strong>Escritório</strong></div><div className="topbar-right"><span className="private-badge"><ShieldCheck size={14} aria-hidden="true" /> AMBIENTE PRIVADO</span><button className="icon-button" aria-label="Atualizar workspace" onClick={() => void load()}><RefreshCw size={16} aria-hidden="true" /></button></div></header>
      <main id="main-content" className="main-content">
        <div className="page-heading"><div><p className="eyebrow"><span className="tiny-square" /> SEU ESCRITÓRIO INTERATIVO</p><h1>{view === "escritorio" ? views.escritorio.title : views.overview.title}</h1><p className="page-description">Clique no time ou em uma sala para começar.</p></div><button className="button primary" onClick={() => setDialog("project")} disabled={!workspace}><Plus size={17} aria-hidden="true" /> Novo projeto</button></div>
        {error && <div className="notice error" role="alert">{error}<button className="text-button" onClick={() => void load()}>Tentar novamente</button></div>}
        {!workspace ? <div className="loading-state" role="status"><CircleDashed className="spin" size={24} aria-hidden="true" /><p>{error ? "Aguardando conexão com o serviço." : "Preparando sua sala de operações…"}</p></div> : <>
          <PixelOffice data={workspace} connected={!error} openTool={target => router.push(href(target))} />
          {toolOpen && <OfficeWindow label={meta.label} close={() => router.push("/")} back={() => router.back()}>
          <div className="page-heading"><div><h2>{meta.title}</h2><p>{meta.description}</p></div></div>
          {view === "resumo" && <Overview data={workspace} create={() => setDialog("project")} newTask={newTask} />}
          {view === "projetos" && <Projects data={workspace} create={() => setDialog("project")} />}
          {view === "tarefas" && <TaskBoard data={workspace} create={newTask} move={move} busy={updating} />}
          {view === "agentes" && <Agents data={workspace} />}
          {view === "memoria" && <KnowledgePanel projects={workspace.projects} />}
          {view === "modelos" && <ModelsPanel projects={workspace.projects} />}
          {view === "videos" && <VideoPanel projects={workspace.projects} />}
          {view === "historico" && <HistoryPanel data={workspace} />}
          {view === "integracoes" && <><Integrations data={workspace} /><HermesPanel data={workspace} reload={load} /><VercelPanel data={workspace} reload={load} /><GitHubPanel data={workspace} reload={load} /></>}
          {view === "relatorios" && <ReportsPanel />}
          {view === "ceo" && <><CeoConsole data={workspace} reload={load} /><RepositoryPanel data={workspace} /></>}
          {view === "execucoes" && <><RunList data={workspace} runs={workspace.runs} reload={load} /><RepositoryPanel data={workspace} /></>}
          {view === "agendamentos" && <SchedulePanel data={workspace} reload={load} />}
          {view === "aprovacoes" && <><div className="principle-strip"><ShieldCheck size={18} aria-hidden="true" /><span>Revise os artefatos e o digest antes de autorizar testes ou publicação. Cada decisão vale somente para o conteúdo exibido.</span></div><RunList data={workspace} runs={workspace.approvals} reload={load} /><RepositoryPanel data={workspace} /></>}
          </OfficeWindow>}
        </>}
        <footer className="content-footer"><span>AI TEAM <span className="muted">/</span> Pense grande. Construa com direção.</span><span>Controle em cada etapa.</span></footer>
      </main>
    </div>
    {dialog && workspace && <CreationDialog kind={dialog} projects={workspace.projects} close={() => setDialog(null)} created={load} />}
  </div>;
}

function EmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description: string; action?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-symbol"><Icon size={28} strokeWidth={1.4} aria-hidden="true" /></div><h2>{title}</h2><p>{description}</p>{action}</div>;
}

function Overview({ data, create, newTask }: { data: Workspace; create: () => void; newTask: () => void }) {
  const done = data.tasks.filter(task => task.status === "done").length;
  return <>
    <section className="welcome-banner"><div><p className="eyebrow">SEU TIME TEM UM NOVO ENDEREÇO</p><h2>Você dá a direção.<br />O time encontra <em>o caminho.</em></h2><p>Reúna suas ideias, organize o trabalho e acompanhe<br className="desktop-break" /> cada passo com clareza.</p><button className="button light" onClick={create}>{data.projects.length ? "Começar outro projeto" : "Começar primeiro projeto"}<ArrowUpRight size={17} aria-hidden="true" /></button></div><div className="team-constellation" aria-hidden="true"><div className="orbit-ring" /><div className="constellation-center">ai<span>TEAM</span></div><span className="orbit-agent orbit-ceo">C<small>CEO</small></span><span className="orbit-agent orbit-dev">D<small>DEV</small></span><span className="orbit-agent orbit-design">D<small>DESIGN</small></span><span className="orbit-agent orbit-qa">Q<small>QA</small></span><span className="orbit-note">QUATRO PERSPECTIVAS.<br />UMA DIREÇÃO.</span></div></section>
    <section className="metrics" aria-label="Indicadores do workspace">{[
      { label: "Projetos no workspace", value: data.projects.length.toString().padStart(2, "0"), caption: "Ideias em construção", icon: Folder },
      { label: "Tarefas em andamento", value: data.tasks.filter(task => task.status === "in_progress").length.toString().padStart(2, "0"), caption: "Foco no próximo passo", icon: Layers3 },
      { label: "Entregas concluídas", value: done.toString().padStart(2, "0"), caption: "Atualizadas por você", icon: CheckCheck },
      { label: "Aprovações pendentes", value: data.approvals.length.toString().padStart(2, "0"), caption: "Decisões nas suas mãos", icon: ShieldCheck },
    ].map(({ label, value, caption, icon: Icon }) => <div className="metric" key={label}><div><span>{label}</span><Icon size={17} aria-hidden="true" /></div><strong>{value}</strong><small>{caption}</small></div>)}</section>
    <div className="overview-columns"><section className="panel"><div className="panel-title"><h2>Seus projetos <span>{data.projects.length.toString().padStart(2, "0")}</span></h2><Link href="/projetos" className="text-link">Ver todos <ArrowUpRight size={15} aria-hidden="true" /></Link></div>{data.projects.length ? <div className="project-list">{data.projects.slice(0, 3).map((project, index) => <Link className="project-row" href="/tarefas" key={project.id}><span className="project-number">{String(index + 1).padStart(2, "0")}</span><div><strong>{project.name}</strong><small>{modes[project.mode]} · {data.tasks.filter(task => task.project_id === project.id).length} tarefas</small></div><ArrowUpRight size={18} aria-hidden="true" /></Link>)}</div> : <EmptyState icon={Folder} title="Uma ideia já é um começo." description="Crie seu primeiro projeto e dê espaço para o trabalho acontecer." action={<button className="text-link button-reset" onClick={create}>Criar um projeto <ArrowRight size={16} aria-hidden="true" /></button>} />}</section>
      <section className="panel team-panel"><div className="panel-title"><h2>O seu time</h2><span className="tag">QUATRO ESPECIALISTAS</span></div><div className="agent-mini-list">{data.agents.map((agent, index) => <div className="agent-mini" key={agent.id}><span className={`agent-avatar color-${index}`}>{agent.name.slice(0, 1)}</span><div><strong>{agent.name}</strong><small>{agent.role}</small></div><span className="mini-status" title="Preparado para as próximas versões">Definido</span></div>)}</div><Link href="/agentes" className="team-more">Conhecer papéis e limites <ArrowRight size={16} aria-hidden="true" /></Link></section></div>
    <section className="next-step"><div className="next-step-icon"><ListTodo size={23} aria-hidden="true" /></div><div><h2>Deixe o próximo passo pronto.</h2><p>Organize uma tarefa e escolha o especialista responsável.</p></div><button className="button" onClick={newTask}>Nova tarefa <Plus size={16} aria-hidden="true" /></button></section>
    <section className="activity-preview"><div className="panel-title"><h2>Últimos movimentos</h2><Link href="/historico" className="text-link">Histórico completo <ArrowUpRight size={15} aria-hidden="true" /></Link></div>{data.events.slice(0, 3).map(event => <div className="activity-row" key={event.id}><span className="activity-dot" /><p>{event.summary}</p><time>{dateTime(event.created_at)}</time></div>)}</section>
  </>;
}

function Projects({ data, create }: { data: Workspace; create: () => void }) {
  return data.projects.length ? <div className="project-grid">{data.projects.map((project, index) => {
    const tasks = data.tasks.filter(task => task.project_id === project.id);
    const complete = tasks.filter(task => task.status === "done").length;
    return <article className="project-card panel" key={project.id}><div className="project-card-top"><span className="project-number">P / {String(index + 1).padStart(2, "0")}</span><span className="tag">{modes[project.mode]}</span></div><h2>{project.name}</h2><p>{project.description || "Uma nova direção para o seu time."}</p><div className="project-progress"><span>{complete} de {tasks.length} tarefas concluídas</span><progress value={complete} max={tasks.length || 1} aria-label={`Tarefas concluídas de ${project.name}`} /></div><div className="project-card-foot"><small>Criado em {dateTime(project.created_at)}</small><Link href="/tarefas" className="icon-button" aria-label={`Abrir tarefas de ${project.name}`}><ArrowUpRight size={19} aria-hidden="true" /></Link></div></article>;
  })}<button className="add-project" onClick={create}><Plus size={27} aria-hidden="true" /><span>Mais uma ideia?</span><small>Criar novo projeto</small></button></div> : <section className="panel"><EmptyState icon={Folder} title="Dê um lugar à sua próxima ideia." description="Crie um projeto para reunir objetivos, tarefas e histórico." action={<button className="button primary" onClick={create}><Plus size={17} aria-hidden="true" /> Novo projeto</button>} /></section>;
}

const nextStatus: Partial<Record<TaskStatus, { status: TaskStatus; label: string }>> = {
  backlog: { status: "in_progress", label: "Iniciar tarefa" }, in_progress: { status: "review", label: "Enviar para revisão" }, review: { status: "done", label: "Marcar como concluída" }, done: { status: "backlog", label: "Reabrir tarefa" },
};
function TaskBoard({ data, create, move, busy }: { data: Workspace; create: () => void; move: (task: Task, status: TaskStatus) => Promise<void>; busy: boolean }) {
  return <><div className="section-toolbar"><span>{data.tasks.length} tarefas no workspace</span><button className="button" onClick={create}><Plus size={16} aria-hidden="true" /> Nova tarefa</button></div><div className="kanban">{(Object.entries(statusLabel) as [TaskStatus, string][]).map(([status, label]) => <section className={`kanban-column column-${status}`} key={status} aria-label={label}><div className="column-heading"><span className="column-dot" /><h2>{label}</h2><span>{data.tasks.filter(task => task.status === status).length}</span></div><div className="column-body">{data.tasks.filter(task => task.status === status).map(task => <article className="task-card" data-testid="task-card" key={task.id}><small>{data.projects.find(project => project.id === task.project_id)?.name}</small><h3>{task.title}</h3>{task.description && <p>{task.description}</p>}<div className="task-card-meta"><span className="tag">{task.agent}</span><span>Manual</span></div><button className="task-action" onClick={() => void move(task, nextStatus[status]!.status)} disabled={busy}>{nextStatus[status]!.label}<ArrowRight size={15} aria-hidden="true" /></button></article>)}{!data.tasks.some(task => task.status === status) && <div className="column-empty"><CircleDashed size={22} aria-hidden="true" /><span>Nenhuma tarefa por aqui.</span></div>}</div></section>)}</div></>;
}

function Agents({ data }: { data: Workspace }) {
  return <><div className="principle-strip"><Bot size={19} aria-hidden="true" /><span>O time produz planos e pareceres pelo Codex próprio. Cada papel mantém o escopo de elaboração textual.</span></div><div className="agent-grid">{data.agents.map((agent, index) => <article className="agent-card panel" key={agent.id}><div className="agent-card-head"><span className={`agent-avatar large color-${index}`}>{agent.name.slice(0, 1)}</span><span className="tag">ESCOPO TEXTUAL</span></div><p className="eyebrow">{agent.name}</p><h2>{agent.role}</h2><p>{agent.description}</p><h3>Capacidades textuais</h3><div className="tool-tags">{agent.tools.map(tool => <span className="tag" key={tool}>{tool}</span>)}</div><div className="agent-limit"><ShieldCheck size={15} aria-hidden="true" /><small>{agent.limit}</small></div></article>)}</div><div className="expansion-note"><Sparkles size={19} aria-hidden="true" /><span>Um time que pode crescer: marketing, pesquisa, finanças e análise fazem parte da evolução da arquitetura.</span></div></>;
}

function HistoryPanel({ data }: { data: Workspace }) {
  return <section className="panel history-panel"><div className="panel-title"><h2>Trilha de auditoria</h2><span className="tag">ÚLTIMOS 200 EVENTOS</span></div>{data.events.length ? data.events.map(event => <article className="history-event" key={event.id}><span className="history-icon">{event.kind.startsWith("auth") ? <ShieldCheck size={18} aria-hidden="true" /> : <Activity size={18} aria-hidden="true" />}</span><div><h3>{event.summary}</h3><small>{event.actor} <span aria-hidden="true">·</span> {event.kind}</small></div><time>{dateTime(event.created_at)}</time></article>) : <EmptyState icon={History} title="O começo de uma história." description="As ações do workspace serão registradas aqui." />}</section>;
}

function Integrations({ data }: { data: Workspace }) {
  const icons: Record<string, LucideIcon> = { github: Folder, codex: Terminal, vercel: ArrowUpRight, supabase: Layers3, skills: Sparkles };
  return <><div className="principle-strip"><ShieldCheck size={18} aria-hidden="true" /><span>Credenciais são configuradas no ambiente privado do servidor. Este painel nunca solicita ou exibe chaves.</span></div><div className="integration-list">{data.integrations.map(integration => { const Icon = icons[integration.id] || Plug; return <article className="integration-card panel" key={integration.id}><div className="integration-icon"><Icon size={25} aria-hidden="true" /></div><div><h2>{integration.name}</h2><p>{integration.description}</p></div><span className="tag">{integration.status === "verified" ? "VERIFICAÇÃO REGISTRADA" : integration.status === "configured" ? "CONFIGURADA · NÃO HOMOLOGADA" : integration.status === "available" ? "ADAPTADOR DISPONÍVEL" : integration.status === "not_configured" ? "NÃO CONFIGURADA" : "PRÓXIMAS VERSÕES"}</span></article>; })}</div></>;
}
