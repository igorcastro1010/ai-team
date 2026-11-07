import { NextRequest, NextResponse } from "next/server";

const allowed = /^(auth\/(login|logout|me)|workspace|reports|projects|tasks(?:\/[a-zA-Z0-9-]+)?|events|integrations|runs(?:\/[a-zA-Z0-9-]+(?:\/(decision|cancel|resume|artifacts))?)?|github(?:\/verify|\/proposals(?:\/[a-zA-Z0-9-]+\/decision)?)?|hermes(?:\/jobs(?:\/inspect|\/[a-f0-9]{12}\/pause)?|\/inspect|\/executions(?:\/[a-zA-Z0-9-]+\/(?:refresh|stop))?)?|vercel(?:\/inspect)?|schedules(?:\/[a-zA-Z0-9-]+\/cancel)?)$/;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const targetPath = path.join("/");
  const repositoryAllowed = /^repository-runs(?:\/[a-f0-9-]{36}(?:\/(decision|cancel|artifacts|publish))?)?$/;
  const modelsAllowed = /^model-center\/[a-f0-9-]{36}(?:\/(?:check|requests|preferences\/(?:CEO|DEV|DESIGNER|QA|PESQUISADOR)|(?:resume|handoff)\/[a-f0-9-]{36}))?$/;
  const factoryAllowed = /^content-factory(?:\/[a-f0-9-]{36}(?:\/[a-f0-9-]{36}(?:\/(?:approve|cancel|resume))?)?)?$/;
  const videosAllowed = /^videos(?:\/[a-f0-9-]{36}\/(?:decision|cancel|download))?$/;
  const studioAllowed = /^video-studio\/(?:fonts\/(?:sans|serif|mono)|[a-f0-9-]{36}\/(?:media(?:\/[a-f0-9-]{36}\/content)?|draft|templates|render))$/;
  const knowledgeAllowed = /^(?:memory\/[a-f0-9-]{36}(?:\/(?:search|sync|[a-f0-9-]{36}(?:\/(?:history|export))?))?|knowledge\/[a-f0-9-]{36}\/graph|issues(?:\/[a-f0-9-]{36}(?:\/sync)?)?|projects\/[a-f0-9-]{36}\/optimizer(?:\/(?:budgets|preview))?)$/;
  if (!factoryAllowed.test(targetPath) && !allowed.test(targetPath) && !repositoryAllowed.test(targetPath) && !knowledgeAllowed.test(targetPath) && !modelsAllowed.test(targetPath) && !videosAllowed.test(targetPath) && !studioAllowed.test(targetPath)) return NextResponse.json({ detail: "Rota não encontrada" }, { status: 404 });
  const hasBody = !["GET", "HEAD"].includes(request.method);
  if (hasBody && request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Origem não autorizada" }, { status: 403 });
  }
  const upload = request.method === "POST" && /^video-studio\/[a-f0-9-]{36}\/media$/.test(targetPath);
  const bodyLimit = upload ? 25 * 1024 * 1024 : targetPath === "github/proposals" || targetPath.startsWith("memory/") ? 131072 : 32768;
  if (Number(request.headers.get("content-length") || 0) > bodyLimit) {
    return NextResponse.json({ detail: "Solicitação muito grande" }, { status: 413 });
  }
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  if (hasBody && request.body) {
    const reader = request.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > bodyLimit) {
        await reader.cancel();
        return NextResponse.json({ detail: "Solicitação muito grande" }, { status: 413 });
      }
      chunks.push(value);
    }
  }
  const body = hasBody ? Buffer.concat(chunks, bytes) : undefined;
  try {
    const base = process.env.AI_TEAM_API_URL || "http://127.0.0.1:8000";
    const url = new URL(`/${targetPath}`, base);
    if (["reports", "hermes/executions"].includes(targetPath)) url.search = request.nextUrl.search;
    if (knowledgeAllowed.test(targetPath) || videosAllowed.test(targetPath) || studioAllowed.test(targetPath)) {
      for (const key of ["project_id", "q", "agent", "status", "priority", "limit", "name"]) {
        const value = request.nextUrl.searchParams.get(key);
        if (value !== null) url.searchParams.set(key, value);
      }
    }
    const upstream = await fetch(url, {
      method: request.method, body, redirect: "error", cache: "no-store",
      signal: AbortSignal.timeout(studioAllowed.test(targetPath) ? 60000 : 12000),
      headers: {
        "content-type": upload ? request.headers.get("content-type") || "application/octet-stream" : "application/json",
        ...(request.headers.get("range")?.match(/^bytes=\d*-\d*$/) ? { range: request.headers.get("range")! } : {}),
        cookie: request.headers.get("cookie") || "",
        origin: request.headers.get("origin") || "",
      },
    });
    const headers = new Headers({ "cache-control": "no-store", "content-type": "application/json" });
    const video = videosAllowed.test(targetPath) && targetPath.endsWith("/download") && upstream.ok && upstream.headers.get("content-type") === "video/mp4";
    const asset = studioAllowed.test(targetPath) && (targetPath.endsWith("/content") || targetPath.startsWith("video-studio/fonts/")) && upstream.ok;
    const binary = video || asset || targetPath.endsWith("/artifacts") && upstream.ok && upstream.headers.get("content-type") === "application/zip";
    if (binary) {
      headers.set("content-type", video ? "video/mp4" : asset ? upstream.headers.get("content-type") || "application/octet-stream" : "application/zip");
      headers.set("x-content-type-options", "nosniff");
      const disposition = upstream.headers.get("content-disposition");
      if (!asset) headers.set("content-disposition", video ? 'attachment; filename="ai-team-video.mp4"' : [
        'attachment; filename="ai-team-nextjs.zip"',
        'attachment; filename="ai-team-repository.zip"',
      ].includes(disposition || "") ? disposition! : 'attachment; filename="ai-team-python.zip"');
      for (const key of ["content-range", "accept-ranges", "content-length"]) {
        const value = upstream.headers.get(key);
        if (value) headers.set(key, value);
      }
    }
    for (const cookie of upstream.headers.getSetCookie()) headers.append("set-cookie", cookie);
    const retry = upstream.headers.get("retry-after");
    if (retry) headers.set("retry-after", retry);
    return new Response(upstream.status === 204 ? null : binary ? upstream.body : await upstream.text(), { status: upstream.status, headers });
  } catch {
    return NextResponse.json({ detail: "API indisponível. Verifique se o serviço FastAPI está em execução." }, { status: 503 });
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT };
