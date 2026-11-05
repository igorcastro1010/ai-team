import { test, expect } from "@playwright/test";

test("exportação e reexportação exigem revisão do Markdown e da versão SQL", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const created = await page.request.post("/api/control/projects", {
    headers: { origin: "http://localhost:3100" }, data: { name: `Exportação ${Date.now()}` },
  });
  expect(created.status()).toBe(201);
  const project = (await created.json()).id;
  await page.goto("/memoria");
  await page.getByLabel("Projeto do conhecimento").selectOption(project);
  await expect(page.getByRole("status")).toContainText("Conhecimento atualizado");
  await page.getByLabel("Título da memória").fill("Nota para Obsidian");
  await page.getByLabel("Conteúdo da memória").fill("Decisão original.");
  await page.getByRole("button", { name: "Salvar memória", exact: true }).click();
  const card = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Nota para Obsidian", exact: true }) });
  await expect(card).toContainText("Versão 1");
  await card.getByRole("button", { name: "Exportar Markdown" }).click();
  const review = page.getByRole("region", { name: "Revisão da exportação Markdown" });
  await expect(review).toContainText("Arquivo novo");
  await review.getByRole("button", { name: "Confirmar exportação revisada" }).click();
  await expect(page.getByRole("status")).toContainText("Markdown exportado");
  await card.getByRole("button", { name: "Editar memória" }).click();
  await page.getByLabel("Conteúdo da memória").fill("Decisão revisada.");
  await page.getByRole("button", { name: "Salvar revisão" }).click();
  await expect(card).toContainText("Versão 2");
  await card.getByRole("button", { name: "Exportar Markdown" }).click();
  await expect(review).toContainText("Decisão original.");
  await expect(review).toContainText("Decisão revisada.");
  await review.getByRole("button", { name: "Cancelar exportação" }).click();
  await expect(review).toHaveCount(0);
  await card.getByRole("button", { name: "Exportar Markdown" }).click();
  const published = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/export"));
  await review.getByRole("button", { name: "Confirmar exportação revisada" }).click();
  const payload = (await published).postDataJSON();
  expect(payload.expected_version).toBe(2);
  expect(payload.expected_digest).toMatch(/^[a-f0-9]{64}$/);
  await expect(page.getByRole("status")).toContainText("Markdown exportado");
  await card.getByRole("button", { name: "Exportar Markdown" }).click();
  await expect(review.getByText("Decisão original.", { exact: true })).toHaveCount(0);
  await expect(review.getByText("Decisão revisada.", { exact: true })).toHaveCount(2);
});
