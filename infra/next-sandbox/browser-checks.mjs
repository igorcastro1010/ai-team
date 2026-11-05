// Trusted declarative QA interpreter. Never evaluates model code or selectors.
const ORIGIN = "http://127.0.0.1:3000";

function keys(object, allowed) {
  return object && typeof object === "object" && !Array.isArray(object) &&
    Object.keys(object).every(key => allowed.includes(key));
}
function text(value, max, empty = false) {
  return typeof value === "string" && (empty || value.length > 0) && value.length <= max;
}
export function validateBrowserChecks(checks) {
  if (!Array.isArray(checks) || checks.length > 6) throw new Error("browser checks limit");
  for (const check of checks) {
    if (!keys(check, ["name", "actions", "expect_text"]) || !text(check.name, 100) ||
        !text(check.expect_text, 1000) || !Array.isArray(check.actions) ||
        check.actions.length < 1 || check.actions.length > 6) throw new Error("browser contract");
    for (const action of check.actions) {
      if (action?.action === "click" && keys(action, ["action", "role", "name"]) &&
          ["button", "link", "checkbox"].includes(action.role) && text(action.name, 200)) continue;
      if (action?.action === "fill" && keys(action, ["action", "label", "value"]) &&
          text(action.label, 200) && text(action.value, 500, true)) continue;
      throw new Error("browser action policy");
    }
  }
  return checks;
}

export async function runBrowserChecks(checks) {
  if (!checks.length) return { browser_checks: 0, browser_failures: 0, blocked_requests: 0 };
  const started = performance.now();
  let browser, deadline;
  let expired = false;
  let failures = 0, blocked = 0;
  try {
    deadline = setTimeout(() => { expired = true; if (browser) void browser.close(); }, 30000);
    const { chromium, expect } = await import("/opt/browser/node_modules/@playwright/test/index.mjs");
    if (expired) throw new Error("browser deadline");
    // Isolation is the restricted offline Docker envelope; never grant SYS_ADMIN or host IPC.
    browser = await chromium.launch({ headless: true,
      timeout: Math.max(1, Math.min(10000, 30000 - (performance.now() - started))),
      args: ["--disable-dev-shm-usage"], chromiumSandbox: false });
    if (expired) throw new Error("browser deadline");
    for (const check of checks) {
      if (expired) throw new Error("browser deadline");
      let context;
      const blockedBefore = blocked;
      try {
        context = await browser.newContext({ viewport: { width: 390, height: 844 },
          serviceWorkers: "block", acceptDownloads: false, permissions: [] });
        context.setDefaultTimeout(4000);
        await context.route("**/*", route => {
          const url = new URL(route.request().url());
          if (url.origin === ORIGIN) return route.continue();
          blocked++;
          return route.abort("blockedbyclient");
        });
        await context.routeWebSocket(/.*/, socket => { blocked++; socket.close(); });
        const page = await context.newPage();
        page.on("popup", popup => { blocked++; void popup.close(); });
        page.on("download", download => { blocked++; void download.cancel(); });
        await page.goto(ORIGIN + "/", { waitUntil: "load", timeout: 5000 });
        for (const action of check.actions) {
          if (action.action === "fill") await page.getByLabel(action.label, { exact: true }).fill(action.value);
          else await page.getByRole(action.role, { name: action.name, exact: true }).click();
        }
        await expect(page.getByText(check.expect_text, { exact: true })).toBeVisible({ timeout: 4000 });
        if (new URL(page.url()).origin !== ORIGIN) throw new Error("navigation policy");
        if (blocked !== blockedBefore) throw new Error("blocked browser operation");
        console.log(JSON.stringify({ browser_check: check.name, passed: true }));
      } catch {
        failures++;
        console.log(JSON.stringify({ browser_check: check.name, passed: false }));
      } finally {
        if (context) await context.close();
      }
    }
    if (expired) throw new Error("browser deadline");
    return { browser_checks: checks.length, browser_failures: failures, blocked_requests: blocked };
  } finally {
    clearTimeout(deadline);
    if (browser) await browser.close();
  }
}
