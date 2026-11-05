import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import path from "node:path";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  await page.goto("/escritorio");
}

for (const width of [360, 390, 430, 1440]) {
  test(`escritório acessível com estados reais em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await login(page);
    await expect(page.getByRole("heading", { name: "Um escritório. Sete especialidades." })).toBeVisible();
    await expect(page.getByRole("button", { name: /Abrir detalhes de/ })).toHaveCount(7);
    await expect(page.locator(".pixel-station.is-working")).toHaveCount(0);
    await page.getByRole("button", { name: /Abrir detalhes de PESQUISADOR/ }).click();
    await expect(page.getByRole("heading", { name: "Pesquisa e fontes", exact: true })).toBeVisible();
    await expect(page.getByText("Perfil Hermes ainda não provisionado.", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
    await page.getByRole("heading", { name: "Um escritório. Sete especialidades." }).click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `../../artifacts/office-${width}.png`, fullPage: true });
    if (width === 1440) await page.locator(".office-campus").screenshot({ path: "../../artifacts/office-campus-1440.png" });
  });
}

test("Hermes diagnóstico e consentimento por executor", async ({ page }) => {
  await login(page);
  await page.goto("/integracoes");
  await page.getByRole("button", { name: "Verificar Hermes" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Diagnóstico registrado" })).toBeVisible();
  await expect(page.getByText("Inferência ainda não homologada.", { exact: true })).toBeVisible();
  const project = await page.request.post("/api/control/projects", {
    headers: { origin: "http://localhost:3100" }, data: { name: "Hermes E2E" },
  });
  expect(project.status()).toBe(201);
  await page.goto("/ceo");
  await page.getByLabel("Projeto da solicitação").selectOption({ label: "Hermes E2E" });
  await page.getByLabel("Executor da solicitação").selectOption("hermes");
  await page.getByLabel("O que você quer construir?").fill("Proponha um plano de revisão da interface.");
  await page.getByRole("checkbox", { name: /Autorizo enviar esta solicitação ao Hermes/ }).check();
  await page.getByRole("button", { name: "Enviar ao CEO" }).click();
  await expect(page.getByRole("status")).toContainText("Solicitação registrada");
  const runs = await (await page.request.get("/api/control/runs")).json();
  const run = runs.find((r: { prompt: string }) => r.prompt.includes("revisão da interface"));
  expect(run?.executor).toBe("hermes");
  expect((await page.request.post(`/api/control/runs/${run.id}/cancel`, {
    headers: { origin: "http://localhost:3100" },
  })).status()).toBe(200);
});

test("escritório acompanha checkpoints e aprovações reais do backend", async ({ page }) => {
  test.setTimeout(60000);
  await login(page);
  const headers = { origin: "http://localhost:3100" };
  const project = await (await page.request.post("/api/control/projects", {
    headers, data: { name: "Escritório E2E", mode: "manual" },
  })).json();
  const run = await (await page.request.post("/api/control/runs", {
    headers, data: { project_id: project.id, prompt: "Plano sintético para validar eventos visuais.", consent: true },
  })).json();
  const root = path.resolve(__dirname, "../../..");
  const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  function checkpoint() {
    // Contract provider in the disposable E2E DB; no model or native delegation claim.
    execFileSync(python, ["-c", "import sys; sys.path.insert(0, 'services/api/tests'); from test_workflow import TestProvider; from ai_team.worker import Worker; from ai_team.db import Database; from ai_team.config import Settings; s=Settings(); assert Worker(Database(s),s,TestProvider()).once()"], {
      cwd: root, env: { ...process.env, AI_TEAM_DATABASE_URL: process.env.AI_TEAM_E2E_DB, AI_TEAM_ENVIRONMENT: "test" },
    });
  }
  checkpoint();
  await expect(page.getByRole("button", { name: "Abrir detalhes de CEO: Aguardando aprovação", exact: true })).toBeVisible({ timeout: 12000 });
  await page.getByRole("button", { name: /Abrir detalhes de CEO:/ }).click();
  const result = page.locator(".office-result").filter({ hasText: "Proposta textual, sem execução externa." });
  await result.getByText("Parecer CEO", { exact: true }).click();
  await expect(result.getByText("Proposta textual, sem execução externa.", { exact: true })).toBeVisible();
  expect((await page.request.post(`/api/control/runs/${run.id}/decision`, {
    headers, data: { stage: 1, approve: true },
  })).status()).toBe(200);
  checkpoint();
  await expect(page.getByRole("button", { name: "Abrir detalhes de DEV: Aguardando aprovação", exact: true })).toBeVisible({ timeout: 12000 });
  expect((await page.request.post(`/api/control/runs/${run.id}/cancel`, { headers })).status()).toBe(200);
});
