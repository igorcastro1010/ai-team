import type { Run } from "@/lib/api";

export function CodeArtifacts({ run }: { run: Run }) {
  if (!["python_code", "nextjs_code"].includes(run.scope)) return null;
  const next = run.scope === "nextjs_code";
  const files: { path: string; content: string }[] = [];
  for (const step of run.steps) {
    if (!(next ? ["DEV", "DESIGNER", "QA"] : ["DEV", "QA"]).includes(step.agent)) continue;
    try {
      const bundle = JSON.parse(step.deliverable);
      if (Array.isArray(bundle.files)) {
        for (const file of bundle.files) {
          if (typeof file.path === "string" && typeof file.content === "string") files.push(file);
        }
      }
    } catch { /* A failed/incomplete generation remains visible in its step. */ }
  }
  const result = run.steps[3]?.test_result;
  const labels: Record<string, string> = { passed: next ? "passou" : "passaram", failed: next ? "falhou" : "falharam", timeout: "tempo esgotado", output_limit: "limite de saída atingido" };
  return <section className="code-delivery" aria-label={next ? "Entrega Next.js" : "Entrega Python"}>
    <h3>{next ? "Projeto Next.js para revisão" : "Arquivos Python para revisão"}</h3>
    <p>{next ? "TSX, CSS e critérios do QA. O ZIP inclui configurações e dependências fixas; o identificador cobre o projeto completo." : "Arquivos novos, sem dependências externas. Seus repositórios permanecem preservados."}</p>
    {files.map(file => <details className="run-artifact" key={file.path}>
      <summary>{file.path}</summary><pre className="artifact-content">{file.content}</pre>
    </details>)}
    {run.artifact_digest && <>
      <p className="field-help">Identificação dos arquivos revisados:</p>
      <code className="code-digest">{run.artifact_digest}</code>
      <a className="button" href={`/api/control/runs/${run.id}/artifacts`} download>{next ? "Baixar projeto Next.js" : "Baixar arquivos Python"}</a>
    </>}
    {result && <div className={`notice ${result.status === "passed" ? "success" : "error"}`}>
      <strong>{next ? "Validação Next.js" : "Testes Python"}: {labels[result.status] || "resultado indisponível"}</strong>
      <p>Código de saída: {result.exit_code ?? "indisponível"}. Resultado do executor isolado.</p>
      <details><summary>Ver saída dos testes</summary><pre className="artifact-content">{result.output}</pre></details>
    </div>}
  </section>;
}
