import { expect, test } from "@playwright/test";

test("central mantém autorização desligada e separa preferências dos projetos", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const projects: string[] = [];
  for (const name of ["Modelos A", "Modelos B"]) {
    const response = await page.request.post("/api/control/projects", {
      headers: { origin: "http://localhost:3100" }, data: { name: `${name} ${Date.now()}` },
    });
    expect(response.status()).toBe(201); projects.push((await response.json()).id);
  }
  await page.goto("/modelos");
  await page.getByLabel("Projeto da central de IA").selectOption(projects[0]);
  await expect(page.getByRole("status")).toContainText("Central atualizada");
  const policy = page.getByRole("form", { name: "Preferência de CEO" });
  await expect(policy.getByLabel("Autorizo chamadas gratuitas por 24 horas")).not.toBeChecked();
  await policy.getByLabel("Modo de seleção").selectOption("manual");
  await policy.getByLabel("Provedor e modelo").selectOption("codex");
  await policy.getByRole("button", { name: "Salvar preferência de CEO" }).click();
  await expect(page.getByRole("status")).toContainText("Preferência de CEO salva");
  await expect(policy.getByText("Somente encaminhamento supervisionado")).toBeVisible();
  await page.getByLabel("Pedido para a equipe").fill("Prepare uma proposta textual para este projeto.");
  await page.getByLabel("Autorizo colocar este pedido na fila supervisionada").check();
  await page.getByRole("button", { name: "Enviar para a fila" }).click();
  await expect(page.getByRole("status")).toContainText("Pedido na fila supervisionada");
  const snapshot = await page.request.get(`/api/control/model-center/${projects[0]}`);
  expect(snapshot.status()).toBe(200);
  expect((await snapshot.json()).history).toEqual([]);
  // This suite shares a disposable worker queue with legacy workflow tests.
  // Leave no central request for their contract providers to claim.
  const runs = await (await page.request.get("/api/control/runs")).json();
  const created = runs.find((run: { project_id: string }) => run.project_id === projects[0]);
  expect(created.executor).toBe("central");
  expect((await page.request.post(`/api/control/runs/${created.id}/cancel`, {
    headers: { origin: "http://localhost:3100" },
  })).status()).toBe(200);
  await page.getByRole("button", { name: "Verificar sem inferência" }).click();
  await expect(page.getByRole("status")).toContainText("Verificação enfileirada");
  await page.getByLabel("Projeto da central de IA").selectOption(projects[1]);
  await expect(page.getByRole("status")).toContainText("Central atualizada");
  await expect(policy.getByLabel("Modo de seleção")).toHaveValue("automatic");
  await expect(policy.getByLabel("Provedor e modelo")).toHaveValue("gemini");
  await expect(policy.getByLabel("Autorizo chamadas gratuitas por 24 horas")).not.toBeChecked();
  await expect(page.getByLabel("Pedido para a equipe")).toHaveValue("");
  await page.setViewportSize({ width: 360, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
