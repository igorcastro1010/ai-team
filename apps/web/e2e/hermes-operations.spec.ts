import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("histórico Hermes distingue cancelamento local de confirmação remota", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const response = await page.request.get("/api/control/workspace");
  const workspace = await response.json();
  const attempt = {
    id: "test-attempt", run_id: "test-run", stage: 0, remote_id: "native_real_contract",
    remote_status: "running", local_status: "cancelled", bridge_status: "interrupted",
    stop_status: "uncertain", input_tokens: null, output_tokens: null,
    created_at: 123, updated_at: 123,
  };
  let stops = 0;
  let queries = 0;
  let pages = 0;
  let newArrival = false;
  let workspaceReads = 0;
  await page.route("**/api/control/workspace", route => route.fulfill({ json: {
    ...workspace, hermes: { connection: null, executions: { items: newArrival
      ? [{ ...attempt, id: "new-arrival", remote_id: "new_contract" }] : [attempt], next_cursor: "test-attempt" } },
    testOnlyReadCount: ++workspaceReads,
  } }));
  await page.route("**/api/control/hermes/executions/test-attempt/stop", async route => {
    stops += 1;
    expect(route.request().postDataJSON()).toEqual({ confirm: true });
    attempt.remote_status = "cancelled"; attempt.stop_status = "confirmed"; attempt.updated_at += 1;
    await route.fulfill({ json: attempt });
  });
  await page.route("**/api/control/hermes/executions/test-attempt/refresh", async route => {
    queries += 1; await route.fulfill({ json: attempt });
  });
  await page.route("**/api/control/hermes/executions?before=*", async route => {
    pages += 1;
    await route.fulfill({ json: { items: [{ ...attempt, id: "older", remote_id: "old_contract",
      remote_status: "failed", bridge_status: "failed", stop_status: "not_requested" }], next_cursor: null } });
  });
  await page.goto("/integracoes");
  const card = page.getByRole("article").filter({ hasText: "native_real_contract" });
  await expect(card).toContainText("Tokens de entrada: não informado");
  await expect(card).toContainText("A execução remota pode continuar");
  await card.getByRole("button", { name: "Interromper no Hermes" }).click();
  const dialog = page.getByRole("dialog", { name: "Interromper esta execução no Hermes?" });
  await expect(dialog).toContainText("native_real_contract");
  await dialog.getByRole("button", { name: "Voltar", exact: true }).click();
  expect(stops).toBe(0);
  await card.getByRole("button", { name: "Interromper no Hermes" }).click();
  await dialog.getByRole("button", { name: "Confirmar interrupção remota" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(card).toContainText("Interrupção confirmada pelo Hermes.");
  expect(stops).toBe(1);
  await card.getByRole("button", { name: "Consultar estado remoto" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Estado remoto consultado" })).toBeVisible();
  expect(queries).toBe(1);
  await page.getByRole("button", { name: "Carregar tentativas anteriores" }).click();
  await expect(page.getByRole("article").filter({ hasText: "old_contract" })).toBeVisible();
  expect(pages).toBe(1);
  const readsBeforeInsert = workspaceReads;
  newArrival = true;
  await page.getByRole("button", { name: "Atualizar workspace", exact: true }).click();
  await expect.poll(() => workspaceReads).toBeGreaterThan(readsBeforeInsert);
  await expect(card).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "old_contract" })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "new_contract" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Voltar às tentativas mais recentes" }).click();
  await expect(page.getByRole("article").filter({ hasText: "new_contract" })).toBeVisible();
});

test("novas rotas Hermes continuam privadas e rejeitam destinos arbitrários", async ({ request }) => {
  expect((await request.get("/api/control/hermes/executions")).status()).toBe(401);
  expect((await request.post("/api/control/hermes/executions/arbitrary/stop", {
    data: { confirm: true }, headers: { origin: "https://evil.test" },
  })).status()).toBe(403);
  expect((await request.get("/api/control/hermes/v1/runs/arbitrary")).status()).toBe(404);
});
