import Link from "next/link";
export default function NotFound() {
  return <main className="login-shell"><div className="login-card"><p className="eyebrow">404</p><h1>Esse espaço não existe.</h1><Link className="button primary" href="/">Voltar ao workspace</Link></div></main>;
}
