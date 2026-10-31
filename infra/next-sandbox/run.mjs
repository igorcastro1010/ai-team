// Trusted supervisor: never imports generated application code into this process.
import { readFile, writeFile, mkdir, symlink, access } from "node:fs/promises";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { readHtml } from "./read-html.mjs";

const source = /^(app\/page\.tsx|app\/globals\.css|components\/[a-z][a-z0-9-]{0,50}\.tsx|tests\/acceptance\.json)$/;
const fixed = ["package.json", "package-lock.json", "tsconfig.json", "next-env.d.ts", "next.config.mjs", "app/layout.tsx"];
let server;
const children = new Set();
const deadline = setTimeout(() => {
  for (const child of children) child.kill("SIGKILL");
  process.exit(124);
}, 115000);
const environment = { ...process.env, NEXT_TELEMETRY_DISABLED: "1", NODE_OPTIONS: "--max-old-space-size=640", TMPDIR: "/work/tmp", CI: "1" };

function start(args) {
  const child = spawn(process.execPath, args, { cwd: "/work", env: environment, stdio: ["ignore", "inherit", "inherit"] });
  children.add(child);
  child.on("error", () => { process.exitCode = 1; });
  child.on("exit", () => children.delete(child));
  return child;
}
function exited(child) {
  return new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", code => resolve(code));
  });
}

try {
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
    if (Buffer.byteLength(input) > 600000) throw new Error("input limit");
  }
  const { files } = JSON.parse(input);
  if (!Array.isArray(files) || files.length > 18) throw new Error("file limit");
  const entries = new Map();
  for (const file of files) {
    if (typeof file.path !== "string" || file.path.trim() !== file.path || typeof file.content !== "string" || entries.has(file.path)) throw new Error("file contract");
    if (!source.test(file.path) && !fixed.includes(file.path)) throw new Error("path policy");
    entries.set(file.path, file.content);
  }
  for (const path of fixed) {
    const expected = (await readFile(join("/opt/runner/scaffold", path), "utf8")).replaceAll("\r\n", "\n");
    if (entries.get(path) !== expected) throw new Error("scaffold policy");
  }
  // Snapshot QA in memory before executing any untrusted source/build code.
  const { checks } = JSON.parse(entries.get("tests/acceptance.json"));
  if (!Array.isArray(checks) || checks.length < 1 || checks.length > 12) throw new Error("QA contract");
  for (const check of checks) {
    if (typeof check.name !== "string" || typeof check.contains !== "string" || !check.contains.length) throw new Error("QA contract");
    if (Object.keys(check).some(key => !["name", "contains", "not_contains", "status"].includes(key))) throw new Error("QA policy");
  }
  for (const [path, content] of entries) {
    await mkdir(dirname(join("/work", path)), { recursive: true });
    await writeFile(join("/work", path), content, { flag: "wx" });
  }
  await mkdir("/work/tmp");
  await symlink("/opt/runtime/node_modules", "/work/node_modules");
  const next = "/opt/runtime/node_modules/next/dist/bin/next";
  const build = start([next, "build", "--webpack"]);
  if (await exited(build) !== 0) throw new Error("build failed");
  // A premature process.exit(0) during the build does not produce a usable build.
  await access("/work/.next/BUILD_ID");
  server = start([next, "start", "--hostname", "127.0.0.1", "--port", "3000"]);
  let response;
  for (let i = 0; i < 60; i++) {
    if (server.exitCode !== null) throw new Error("server exited");
    try { response = await fetch("http://127.0.0.1:3000/", { signal: AbortSignal.timeout(1000), redirect: "error" }); break; }
    catch { await new Promise(resolve => setTimeout(resolve, 100)); }
  }
  if (!response) throw new Error("server unavailable");
  const bodyDeadline = setTimeout(() => { process.exit(124); }, 10000);
  const html = await readHtml(response.body);
  clearTimeout(bodyDeadline);
  let failures = 0;
  for (const check of checks) {
    const passed = response.status === (check.status ?? 200) && html.includes(check.contains) &&
      (!check.not_contains || !html.includes(check.not_contains));
    console.log(JSON.stringify({ check: check.name, passed }));
    if (!passed) failures++;
  }
  console.log(JSON.stringify({ build: "passed", checks: checks.length, failures }));
  process.exitCode = failures ? 1 : 0;
} catch {
  console.error("Next.js build/QA nao confirmou conclusao. Confira a saida limitada.");
  process.exitCode = 1;
} finally {
  clearTimeout(deadline);
  for (const child of children) child.kill("SIGKILL");
}
