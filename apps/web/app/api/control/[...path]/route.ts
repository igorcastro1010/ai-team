import { NextRequest, NextResponse } from "next/server";

const allowed = /^(auth\/(login|logout|me)|workspace|reports|projects|tasks(?:\/[a-zA-Z0-9-]+)?|events|integrations|runs(?:\/[a-zA-Z0-9-]+(?:\/(decision|cancel|resume|artifacts))?)?|github(?:\/verify|\/proposals(?:\/[a-zA-Z0-9-]+\/decision)?)?|hermes(?:\/jobs(?:\/inspect|\/[a-f0-9]{12}\/pause)?|\/inspect|\/executions(?:\/[a-zA-Z0-9-]+\/(?:refresh|stop))?)?|vercel(?:\/inspect)?|schedules(?:\/[a-zA-Z0-9-]+\/cancel)?)$/;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const targetPath = path.join("/");
  if (!allowed.test(targetPath)) return NextResponse.json({ detail: "Rota não encontrada" }, { status: 404 });
  const hasBody = !["GET", "HEAD"].includes(request.method);
  if (hasBody && request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Origem não autorizada" }, { status: 403 });
  }
  const bodyLimit = targetPath === "github/proposals" ? 131072 : 32768;
  if (Number(request.headers.get("content-length") || 0) > bodyLimit) {
    return NextResponse.json({ detail: "Solicitação muito grande" }, { status: 413 });
  }
  const body = hasBody ? await request.text() : undefined;
  if (body && Buffer.byteLength(body) > bodyLimit) {
    return NextResponse.json({ detail: "Solicitação muito grande" }, { status: 413 });
  }
  try {
    const base = process.env.AI_TEAM_API_URL || "http://127.0.0.1:8000";
    const url = new URL(`/${targetPath}`, base);
    if (["reports", "hermes/executions"].includes(targetPath)) url.search = request.nextUrl.search;
    const upstream = await fetch(url, {
      method: request.method, body, redirect: "error", cache: "no-store",
      signal: AbortSignal.timeout(12000),
      headers: {
        "content-type": "application/json",
        cookie: request.headers.get("cookie") || "",
        origin: request.headers.get("origin") || "",
      },
    });
    const headers = new Headers({ "cache-control": "no-store", "content-type": "application/json" });
    const binary = targetPath.endsWith("/artifacts") && upstream.ok && upstream.headers.get("content-type") === "application/zip";
    if (binary) {
      headers.set("content-type", "application/zip");
      headers.set("content-disposition", 'attachment; filename="ai-team-python.zip"');
    }
    for (const cookie of upstream.headers.getSetCookie()) headers.append("set-cookie", cookie);
    const retry = upstream.headers.get("retry-after");
    if (retry) headers.set("retry-after", retry);
    return new Response(upstream.status === 204 ? null : binary ? await upstream.arrayBuffer() : await upstream.text(), { status: upstream.status, headers });
  } catch {
    return NextResponse.json({ detail: "API indisponível. Verifique se o serviço FastAPI está em execução." }, { status: 503 });
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH };
