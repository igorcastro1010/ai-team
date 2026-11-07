import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";

test("Python: revisar arquivos, aprovar hash, baixar ZIP e ver resultado persistido", async ({ page }) => {
  test.setTimeout(60000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const headers = { origin: "http://localhost:3100" };
  await page.request.post("/api/control/projects", { headers, data: { name: "Código Python E2E", mode: "automatic" } });
  await page.goto("/ceo");
  await page.getByLabel("Projeto da solicitação").selectOption({ label: "Código Python E2E" });
  await page.getByLabel("Tipo de entrega").selectOption("python_code");
  await page.getByLabel("O que você quer construir?").fill("Crie uma soma Python com testes para validar a entrega.");
  await page.getByRole("checkbox", { name: /Autorizo enviar esta solicitação/ }).check();
  await page.getByRole("button", { name: "Enviar ao CEO" }).click();
  await expect(page.getByRole("status")).toContainText("Solicitação registrada");
  const root = path.resolve(__dirname, "../../..");
  const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  function advance(count: number) {
    // Disposable DB and contract doubles; real Docker is tested separately.
    execFileSync(python, ["-c", `import sys; sys.path.insert(0,'services/api/tests'); from test_code_workflow import CodeProvider, Sandbox; from ai_team.worker import Worker; from ai_team.config import Settings; from ai_team.db import Database; s=Settings(); w=Worker(Database(s),s,CodeProvider(),sandbox=Sandbox()); [w.once() for _ in range(${count})]`], {
      cwd: root, env: { ...process.env, AI_TEAM_DATABASE_URL: process.env.AI_TEAM_E2E_DB, AI_TEAM_ENVIRONMENT: "test" },
    });
  }
  advance(4);
  const card = page.getByTestId("run-card").filter({ hasText: "Crie uma soma Python com testes" });
  await expect(card.getByText("Aguarda aprovação", { exact: true })).toBeVisible({ timeout: 12000 });
  await expect(card.getByText("main.py", { exact: true })).toBeVisible();
  await expect(card.getByText("test_main.py", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await card.getByRole("link", { name: "Baixar arquivos Python" }).click();
  expect((await download).suggestedFilename()).toBe("ai-team-python.zip");
  const runs = await (await page.request.get("/api/control/runs")).json();
  const run = runs.find((item: { scope: string }) => item.scope === "python_code");
  const archive = await page.request.get(`/api/control/runs/${run.id}/artifacts`);
  expect((await archive.body()).subarray(0, 2).toString()).toBe("PK");
  await card.getByRole("button", { name: "Aprovar execução dos testes" }).click();
  const dialog = page.locator("dialog.creation-dialog");
  await expect(dialog).toContainText(run.artifact_digest);
  await dialog.getByRole("button", { name: "Autorizar testes Python", exact: true }).click();
  advance(1);
  await expect(card.getByText("Testes Python: passaram", { exact: true })).toBeVisible({ timeout: 12000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await card.screenshot({ path: "../../artifacts/python-code-390.png" });
});
