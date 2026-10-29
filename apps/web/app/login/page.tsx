"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

export default function Login() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await api("/auth/login", { method: "POST", body: JSON.stringify({ username: form.get("username"), password: form.get("password") }) });
      router.replace("/");
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível entrar."); }
    finally { setBusy(false); }
  }
  return <main className="login-shell">
    <div className="login-story"><div className="brand"><span className="brand-mark">ai</span> AI TEAM</div>
      <p className="eyebrow">UM ESPAÇO PARA CONSTRUIR</p><h1>Grandes ideias.<br />Trabalho em <em>equipe.</em></h1>
      <p>Da primeira intenção à última revisão. Seu time, seus projetos e cada decisão em um só lugar.</p>
      <div className="login-orbit" aria-hidden="true"><span>CEO</span><span>DEV</span><span>DESIGN</span><span>QA</span></div>
      <small>Inteligência com direção. Autonomia com controle.</small>
    </div>
    <section className="login-card"><div className="secure-label"><ShieldCheck size={16} aria-hidden="true" /> WORKSPACE PRIVADO</div>
      <h2>Bem-vindo ao time.</h2><p>Entre para abrir sua sala de operações.</p>
      <form onSubmit={submit}><label htmlFor="username">Usuário</label><input autoComplete="username" id="username" name="username" required maxLength={80} autoFocus />
        <label htmlFor="password">Senha</label><input type="password" autoComplete="current-password" id="password" name="password" required maxLength={256} />
        {error && <p className="notice error" role="alert">{error}</p>}
        <button className="button primary full" disabled={busy}>{busy ? "Entrando…" : "Entrar no workspace"}<ArrowUpRight size={18} aria-hidden="true" /></button>
      </form><p className="login-help">Primeiro acesso? Cadastre o proprietário pelo instalador local. O registro público está desativado.</p>
      <div className="login-foot"><span className="dot" /> Sua operação começa aqui.<span>V0.5</span></div>
    </section>
  </main>;
}
