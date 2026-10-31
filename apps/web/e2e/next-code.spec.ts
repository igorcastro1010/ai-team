import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

test("Next.js: aprovar projeto e preservar resultado entre build e relatório", async ({ page }) => {
  test.setTimeout(60000);
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const headers = { origin: "http://localhost:3100" };
  await page.request.post("/api/control/projects", { headers, data: { name: "Next.js E2E", mode: "automatic" } });
  await page.goto("/ceo");
  await page.getByLabel("Projeto da solicitação").selectOption({ label: "Next.js E2E" });
  await page.getByLabel("Tipo de entrega").selectOption("nextjs_code");
  await page.getByLabel("O que você quer construir?").fill("Crie uma página Next.js AI TEAM para validar o projeto.");
  await page.getByRole("checkbox", { name: /Autorizo enviar esta solicitação/ }).check();
  await page.getByRole("button", { name: "Enviar ao CEO" }).click();
  await expect(page.getByRole("status")).toContainText("Solicitação registrada");
  const root = path.resolve(__dirname, "../../..");
  const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  function advance(count: number) {
    execFileSync(python, ["-c", `import sys; sys.path.insert(0,'services/api/tests'); from test_next_workflow import NextProvider; from test_code_workflow import Sandbox; from ai_team.worker import Worker; from ai_team.config import Settings; from ai_team.db import Database; s=Settings(); w=Worker(Database(s),s,NextProvider(),sandbox=Sandbox()); [w.once() for _ in range(${count})]`], {
      cwd: root, env: { ...process.env, AI_TEAM_DATABASE_URL: process.env.AI_TEAM_E2E_DB, AI_TEAM_ENVIRONMENT: "test" },
    });
  }
  advance(4);
  const card = page.getByTestId("run-card").filter({ hasText: "Crie uma página Next.js AI TEAM" });
  await expect(card.getByText("Aguarda aprovação", { exact: true })).toBeVisible({ timeout: 12000 });
  await expect(card.getByText("app/globals.css", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await card.getByRole("link", { name: "Baixar projeto Next.js" }).click();
  expect((await download).suggestedFilename()).toBe("ai-team-nextjs.zip");
  await card.getByRole("button", { name: "Aprovar build e testes" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Autorizar validação Next.js", exact: true }).click();
  advance(1);
  await expect(card.getByText("Validação Next.js: passou", { exact: true })).toBeVisible({ timeout: 12000 });
  advance(1);
  await expect(card.getByText("Relatório entregue", { exact: true })).toBeVisible({ timeout: 12000 });
});
